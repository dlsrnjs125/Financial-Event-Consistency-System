# 08. Failure Scenarios

## 1. 장애 시나리오 설계 목적

이 프로젝트는 장애가 발생하지 않는 시스템을 가정하지 않는다.

실제 금융 이벤트 처리 환경에서는 네트워크 지연, 외부 시스템 재시도, Redis 장애, DB Connection Pool 고갈, 배포 실패, Migration 실패 등이 발생할 수 있다.

따라서 이 문서는 장애 상황을 미리 정의하고, 각 상황에서 시스템이 어떻게 동작해야 하는지 기록한다.

---

## 2. 장애 시나리오 목록

| 번호 | 장애 상황 | 핵심 검증 |
|------|-----------|-----------|
| F-001 | Redis Down | Redis 없이도 중복 반영 방지 |
| F-002 | DB Connection Pool 고갈 | 일부 실패 가능, 중복 반영 금지 |
| F-003 | API 서버 재시작 | Transaction rollback 또는 기존 결과 반환 |
| F-004 | Migration 실패 | 배포 차단 |
| F-005 | 잘못된 상태 전이 배포 | CI에서 차단 |
| F-006 | Nginx 전환 실패 | 기존 Blue 유지 또는 rollback |
| F-007 | 같은 Idempotency-Key 다른 Body | 409 Conflict |
| F-008 | Ledger와 Balance 불일치 | Reconciliation 실패 탐지 |
| F-009 | Redis Timeout | fallback metric/log와 DB 기준 처리 |
| F-010 | Duplicate Event Storm | 중복 Ledger/Event 0건 |
| F-011 | Green readiness 실패 | 전환 전 Blue 유지 |
| F-012 | Nginx reload 실패 | backup snippet restore |
| F-013 | Blue-Green 전환 후 smoke 실패 | Blue rollback 후 smoke/verify |
| F-014 | Failure Recovery Runbook Drift | 장애 주입, 복구, 검증 절차가 문서와 어긋나지 않도록 자동 drill |
| F-015 | Alert Rule / Runbook Drift | Prometheus alert rule과 운영 대응 기준이 실제 metric/runbook과 어긋나지 않도록 검증 |

---

## F-001. Redis Down

### 상황

Redis가 중단되어 Lock과 Cache를 사용할 수 없다.

### 재현 방법

```bash
make failure-redis-down
```

### 예상 영향

- Redis Lock 획득 실패
- Idempotency Cache 조회 실패
- 중복 요청이 DB까지 도달할 가능성 증가

### 기대 동작

- API 전체가 중단되면 안 된다.
- PostgreSQL Transaction과 Unique Constraint로 중복 반영을 막아야 한다.
- 동일 `external_event_id`는 `transaction_events`에 1건만 저장되어야 한다.
- 동일 `transaction_event_id`는 `ledger_entries`에 1건만 저장되어야 한다.

### 관측 지표

- `redis_up`
- `financial_redis_lock_acquire_failed_total`
- `financial_events_duplicate_total`
- `financial_ledger_entries_created_total`

### 성공 기준

동일 이벤트 100회 요청 시 `ledger_entries`는 1건만 생성된다.

---

## F-002. DB Connection Pool 고갈

### 상황

동시 요청 증가로 API 서버의 DB Connection Pool이 모두 사용 중인 상태가 된다.

### 재현 방법

```bash
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=0
DB_POOL_TIMEOUT=2
k6 run tests/k6/peak-load.js
```

### 예상 영향

- 응답 지연 증가
- 일부 요청 503 반환
- p95/p99 latency 증가

### 기대 동작

- 처리하지 못한 요청은 명확히 실패해야 한다.
- 중간 처리 상태로 남은 이벤트가 없어야 한다.
- 이미 commit된 거래는 재시도 시 기존 결과를 반환해야 한다.
- 중복 거래 반영은 발생하면 안 된다.

### HTTP 응답 정책

```text
503 Service Unavailable
```

### 관측 지표

- `db_connections_active`
- `db_connection_wait_seconds`
- `financial_db_transaction_duration_seconds`
- `http_5xx_total`

### 성공 기준

일부 요청이 실패하더라도 `account.balance`와 `ledger_entries`의 정합성은 유지된다.

---

## F-003. API 서버 재시작

### 상황

거래 이벤트 처리 중 API 서버 컨테이너가 재시작된다.

### 재현 방법

```bash
make failure-api-restart
```

또는 처리 중 강제 종료를 시뮬레이션한다.

### 예상 영향

- 처리 중이던 요청 연결 종료
- 외부 시스템 재시도 발생
- Transaction commit 전/후 상태에 따라 결과 달라짐

### 기대 동작

| 상태 | 기대 결과 |
|------|-----------|
| Commit 전 종료 | DB rollback |
| Commit 후 응답 전 종료 | 재시도 시 기존 결과 반환 |
| IdempotencyRecord PROCESSING 상태 | 일정 시간 후 재처리 또는 상태 확인 |

### 성공 기준

API 재시작 후 동일 이벤트 재요청 시 중복 ledger가 생성되지 않는다.

---

## F-004. Migration 실패

### 상황

DB Migration이 실패한다.

예시:

- 기존 데이터가 있는데 NOT NULL 컬럼을 default 없이 추가

### 기대 동작

- 배포가 중단되어야 한다.
- Green 전환이 발생하면 안 된다.
- 기존 Blue 버전은 계속 유지되어야 한다.

### 성공 기준

Migration 실패 시 Nginx 트래픽은 기존 Blue에 유지된다.

---

## F-005. 잘못된 상태 전이 배포

### 상황

개발자가 다음과 같은 잘못된 상태 전이를 허용하는 코드를 작성한다.

```text
COMPLETED -> PROCESSING
FAILED -> COMPLETED
SETTLED -> CANCELLED
```

### 기대 동작

- 상태 머신 테스트가 실패해야 한다.
- CI가 실패해야 한다.
- main 브랜치 merge가 차단되어야 한다.

### 성공 기준

잘못된 상태 전이 정책이 포함된 코드는 배포되지 않는다.

---

## F-006. Nginx 전환 실패

### 상황

Blue-Green 배포 중 Nginx upstream 전환이 실패한다.

### 예상 원인

- `nginx.conf` 문법 오류
- Green 컨테이너 health check 실패
- upstream target 오타

### 기대 동작

- `nginx -t` 검증 실패 시 reload하지 않는다.
- 기존 Blue 트래픽은 유지된다.
- Green 전환 실패 로그를 남긴다.

### 재현 및 복구 명령

```bash
make deploy-green
make deploy-switch-green
make deploy-rollback
```

Phase 12에서는 `infra/nginx/conf.d/upstream-active.conf` snippet만 교체하고, config test 실패 시 이전 upstream을 복원한다.

## Phase 10~12 장애 대응 형식

새 장애 시나리오는 다음 항목으로 기록한다.

- 장애 상황:
- 예상 원인:
- 사용자 영향:
- 탐지 방법:
- 대응 방법:
- 재발 방지:
- 확인 명령:

## Phase 12 추가 시나리오 요약

| 장애 | 사용자 영향 | 탐지 방법 | 대응 방법 | 확인 명령 |
|---|---|---|---|---|
| Redis Timeout | 응답 지연 증가 가능, 정합성은 DB 기준 유지 | Redis fallback log/metric | Redis lock/cache 생략 후 DB transaction 처리 | `make phase10-redis-down-check` |
| Duplicate Event Storm | DB 부하 증가 가능 | k6 duplicate, SQL 검증 | unique constraint conflict 후 기존 결과 재조회 | `make k6-duplicate && make k6-verify` |
| PostgreSQL 장애 | 신규 거래 처리 실패 | `/ready` 503, dependency metric | DB 복구, API rollback 효과와 DB 장애 구분 | `make failure-db-down` |
| Green readiness 실패 | 전환 전이므로 사용자 영향 없음 | `make deploy-green` | Green 로그 확인, upstream 전환 중단 | `make deploy-status` |
| Nginx reload 실패 | 실제 트래픽과 상태 파일 drift 위험 | deploy script reload 실패 로그 | backup snippet과 active color 복구 | `make deploy-switch-green` |
| 전환 후 smoke 실패 | 일부 요청 실패 가능 | `make deploy-smoke`, 5xx metric | `make deploy-rollback` 후 `make deploy-verify` | `make phase12-check` |
| rollback 후 정합성 검증 실패 | 금융 정합성 사고 가능 | `verify-consistency.sql` | 추가 트래픽 중단, reconciliation 수행 | `make deploy-verify` |
| Failure recovery runbook drift | 운영 문서와 실제 복구 명령 불일치 | Ops5 report PASS/FAIL | `make ops5-demo`로 장애 주입부터 report까지 재검증 | `make ops5-demo` |

### 성공 기준

Nginx 설정 오류가 있어도 기존 Blue 서비스는 유지된다.

---

## F-007. 같은 Idempotency-Key로 다른 Body 요청

### 상황

동일 Idempotency-Key로 `amount` 또는 `account_no`가 다른 요청이 들어온다.

첫 번째 요청:

```json
{
  "external_event_id": "BANK-001",
  "amount": 10000
}
```

두 번째 요청:

```json
{
  "external_event_id": "BANK-001",
  "amount": 50000
}
```

### 기대 동작

```text
409 Conflict
```

### 성공 기준

같은 Idempotency-Key로 다른 Body가 들어오면 기존 거래를 재사용하지 않고 충돌로 처리한다.

---

## F-008. Ledger와 Balance 불일치

### 상황

`account.balance`와 `ledger_entries` 누적 합계가 일치하지 않는다.

### 예상 원인

- Transaction 경계 누락
- 수동 DB 수정
- 일부 LedgerEntry 누락
- 장애 상황에서 잘못된 재처리

### 기대 동작

- Reconciliation 작업에서 불일치를 탐지한다.
- `financial_reconciliation_failed_total` 메트릭을 증가시킨다.
- 운영자 확인 대상 이벤트로 분리한다.

### 성공 기준

불일치가 발생하면 조용히 넘어가지 않고 명확히 탐지된다.

---

## 3. 장애 대응 공통 원칙

1. 실패한 요청을 성공으로 위장하지 않는다.
2. 처리 여부가 불명확한 경우 Idempotency-Key로 재조회 가능해야 한다.
3. Redis 장애는 성능 저하로 이어질 수 있지만 정합성 장애로 이어지면 안 된다.
4. DB 장애 상황에서는 일부 요청 실패를 허용하되 중복 반영은 허용하지 않는다.
5. 배포 실패 시 기존 정상 버전을 유지한다.
6. 장애 상황은 로그와 메트릭으로 추적 가능해야 한다.

---

## 4. 설계 결론

장애 시나리오 설계의 목적은 장애를 완전히 피하는 것이 아니라, 장애가 발생했을 때 어떤 기능이 degraded 되고 어떤 정합성은 반드시 유지되어야 하는지 명확히 하는 것이다.

이 시스템에서는 Redis, API, Nginx 장애가 발생할 수 있지만 거래 중복 반영은 허용하지 않는다.

최종 정합성은 PostgreSQL Transaction, Unique Constraint, Ledger, 상태 머신 테스트로 방어한다.
