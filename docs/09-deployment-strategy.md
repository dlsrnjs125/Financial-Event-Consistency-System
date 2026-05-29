# 09. Deployment Strategy

## 1. 배포 전략 설계 목적

이 시스템은 금융 거래 이벤트를 처리하기 때문에 배포 과정에서도 정합성이 깨지면 안 된다.

배포 전략의 목적은 다음과 같다.

1. 신규 버전을 운영 트래픽에 노출하기 전에 검증한다.
2. 정합성 테스트를 통과하지 못한 버전은 배포하지 않는다.
3. 배포 후 문제가 발생하면 빠르게 이전 버전으로 되돌릴 수 있어야 한다.
4. DB Migration으로 인한 rollback 위험을 줄인다.
5. 배포 전후 메트릭을 비교할 수 있어야 한다.

---

## 2. Blue-Green 배포 구조

### 구성

```text
api-blue  : 현재 운영 버전
api-green : 신규 배포 버전
nginx     : Blue 또는 Green으로 트래픽 전달
postgres  : 공유 DB
redis     : 공유 Redis
```

구조:

```text
External System
      |
    Nginx
      |
  api-blue 또는 api-green
      |
PostgreSQL / Redis
```

Blue-Green 배포에서는 신규 버전인 Green을 먼저 실행하고 검증한 뒤, Nginx upstream을 Green으로 전환한다.
Phase 12에서는 Docker Compose의 `green-deployment` profile과 Nginx upstream snippet 교체 방식으로 이 흐름을 재현한다.
Compose dependency도 Phase 10 readiness 정책과 맞춘다.
PostgreSQL은 `service_healthy` hard dependency지만, Redis는 degraded dependency이므로 `service_started`만 요구한다.
Redis가 unhealthy여도 API 컨테이너 시작 자체를 막지 않고, 애플리케이션 `/ready`에서 `mode="degraded"`와 `checks.redis="degraded"`로 노출한다.

---

## 3. 배포 흐름

1. main 브랜치 merge
2. CI 전체 테스트 실행
3. Docker 이미지 빌드
4. Green 컨테이너 실행
5. Green `/health` 확인
6. Green `/ready` 확인
7. `migration-smoke`로 적용된 schema/constraint 확인
8. Smoke Test 실행
9. Consistency 검증 또는 검증 명령 안내
10. `nginx -t` 성공 후 Nginx upstream Green으로 전환
11. 전환 후 smoke/readiness 확인
12. 배포 후 메트릭 관찰
13. 이상 발생 시 Blue로 rollback

---

## 4. Green 검증 조건

Green 버전은 트래픽 전환 전에 다음 조건을 통과해야 한다.

| 검증 항목 | 기준 |
|-----------|------|
| Health Check | `/health` 200 OK |
| Readiness Check | `/ready` 200 OK |
| Migration | upgrade 성공 |
| Smoke Test | 기본 API 요청 성공 |
| Idempotency Test | 동일 요청 재전송 시 기존 결과 반환 |
| State Machine Test | 잘못된 상태 전이 차단 |
| DB Connection | 정상 연결 |
| Redis Connection | `ok` 또는 Phase 10 정책의 `degraded` 허용 |
| OpenAPI Schema | 응답 스키마 깨짐 없음 |

---

## 5. Nginx upstream 전환

Phase 12에서는 `nginx.conf` 전체를 `sed`로 수정하지 않는다.
대신 `infra/nginx/conf.d/upstream-active.conf` 파일만 template에서 원자적으로 교체한다.

Blue 운영 상태:

```nginx
upstream api_backend {
    server api-blue:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

Green 전환:

```nginx
upstream api_backend {
    server api-green:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

`api-green`도 컨테이너 내부에서는 Blue와 동일하게 `API_PORT=8000`으로 실행한다.
host에서는 `8001:8000`으로 노출해 `http://localhost:8001`로 직접 검증하고, Nginx는 Docker network의 container port인 `api-green:8000`으로 접근한다.

전환 전 검증:

```bash
docker compose exec -T nginx nginx -t
```

검증 성공 후 reload한다.

```bash
docker compose exec -T nginx nginx -s reload
```

Phase 12 명령:

```bash
make deploy-green
make deploy-switch-green
make deploy-blue-green
```

`make deploy-switch-green`을 단독으로 실행해도 Green `/health`와 `/ready`를 다시 확인한 뒤 전환한다.
`nginx -t`가 실패하면 reload하지 않고 이전 snippet을 복구한다.
`nginx reload`가 실패하는 경우에도 이전 snippet과 active color를 되돌려 실제 트래픽 상태와 표시 상태가 어긋나지 않도록 한다.

`make deploy-smoke`는 실제 거래 이벤트를 생성한다.
운영에 가까운 환경에서는 `SMOKE_ACCOUNT_NO`로 smoke 전용 계좌를 지정하고, smoke 데이터가 정산/분석 지표와 섞이지 않도록 분리한다.
`RUN_MIGRATION_SMOKE=true`일 때 실행되는 `migration-smoke`는 migration을 새로 수행하는 명령이 아니라, 현재 적용된 schema와 unique constraint가 기대와 일치하는지 확인하는 검증 명령이다.

---

## 6. Rollback 조건

다음 조건 중 하나라도 발생하면 rollback한다.

| 조건 | 기준 |
|------|------|
| 5xx error rate 증가 | 5분 동안 5% 초과 |
| p95 latency 증가 | 5분 동안 1초 초과 |
| invalid state transition 발생 | 1건 이상 |
| reconciliation 실패 | 1건 이상 |
| DB connection pool 고갈 | 85% 이상 지속 |
| Redis 장애가 API 장애로 전파 | 5xx 증가 동반 |
| Health Check 실패 | 연속 3회 실패 |
| Migration 오류 | 전환 중단. 이미 배포된 API traffic은 필요 시 Blue로 rollback |

---

## 7. Rollback 방식

### API Traffic Rollback

Nginx upstream을 다시 Blue로 변경한다.

```nginx
upstream api_backend {
    server api-blue:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

이후 reload한다.

```bash
make deploy-rollback
```

rollback은 API traffic rollback이다.
DB schema downgrade는 자동으로 실행하지 않는다.

### Docker Image Rollback

이전 정상 이미지 태그를 사용한다.

```bash
docker compose up -d api-blue
```

이미지 태그 예시:

```text
financial-event-api:2026-05-27-a1b2c3
financial-event-api:2026-05-26-z9y8x7
```

---

## 8. DB Migration Rollback의 한계

API 코드는 이전 버전으로 쉽게 되돌릴 수 있지만 DB Schema는 단순히 되돌리기 어렵다.

특히 다음 Migration은 위험하다.

- 컬럼 삭제
- 테이블 삭제
- NOT NULL 즉시 추가
- 기존 데이터 형식 변경
- 대량 데이터 update
- default가 있는 컬럼을 대용량 테이블에 즉시 추가

따라서 이 프로젝트에서는 DB rollback을 기본 전략으로 삼지 않는다.

대신 backward-compatible migration을 우선한다.
Phase 12 rollback script도 이 원칙에 따라 Nginx upstream만 Blue로 되돌린다.
`migration-smoke`는 rollback이나 upgrade를 수행하는 명령이 아니라, 현재 적용된 schema와 금융 정합성에 필요한 unique constraint가 기대와 일치하는지 확인하는 smoke 검증이다.

---

## 9. Backward-Compatible Migration 원칙

### 원칙 1. 기존 컬럼을 즉시 삭제하지 않는다.

나쁜 예:

```text
기존 코드가 사용하는 컬럼을 신규 배포에서 바로 삭제
```

좋은 예:

```text
새 컬럼 추가 -> 코드 변경 -> 안정화 -> 오래된 컬럼 제거
```

### 원칙 2. Expand -> Backfill -> Contract 전략을 사용한다.

1단계. Expand

새 컬럼을 nullable로 추가한다.

```sql
ALTER TABLE transaction_events
ADD COLUMN idempotency_key VARCHAR(255);
```

2단계. Backfill

기존 데이터를 보정한다.

```sql
UPDATE transaction_events
SET idempotency_key = external_event_id
WHERE idempotency_key IS NULL;
```

3단계. Contract

데이터 보정 후 제약조건을 추가한다.

```sql
ALTER TABLE transaction_events
ALTER COLUMN idempotency_key SET NOT NULL;

CREATE UNIQUE INDEX ux_transaction_events_idempotency_key
ON transaction_events(idempotency_key);
```

---

## 10. 배포 후 관찰 지표

배포 이후 최소 5~10분 동안 다음 지표를 확인한다.

- `http_5xx_total`
- `http_request_duration_seconds` p95/p99
- `financial_events_failed_total`
- `financial_events_duplicate_total`
- `financial_invalid_state_transition_total`
- `financial_reconciliation_failed_total`
- `db_connections_active`
- `financial_db_transaction_duration_seconds`
- `redis_up`
- `financial_redis_lock_acquire_failed_total`
- `financial_redis_fallback_total`
- `financial_readiness_dependency_status`
- active upstream: `make deploy-status`

현재 Prometheus scrape 대상은 FastAPI API 중심이다.
Nginx active upstream과 container 상태는 Phase 12 script 출력과 Docker Compose 상태로 확인한다.
`api-green`, Redis exporter, PostgreSQL exporter scrape는 후속 운영 관측 보강 항목이다.

---

## 11. 배포 전략의 한계

Docker Compose 기반 Blue-Green 배포는 실제 Kubernetes 기반 운영 환경과 다르다.

제한점:

- 자동 스케일링 없음
- Pod readiness/liveness probe 없음
- Kubernetes Service 기반 트래픽 전환 없음
- Canary 배포 없음
- Secret Manager 연동 제한

하지만 이 프로젝트의 목적은 완전한 운영 플랫폼 구축이 아니라, 배포 전 검증과 rollback 흐름을 재현 가능한 방식으로 설계하는 것이다.

---

## 12. 설계 결론

이 프로젝트의 배포 전략은 빠른 배포보다 안전한 검증과 rollback 가능성에 초점을 둔다.

Green 버전은 운영 트래픽을 받기 전에 Health Check, Readiness Check, Migration, Smoke Test, Consistency Test를 통과해야 한다.

DB Migration은 단순 rollback이 어렵기 때문에 backward-compatible하게 설계하고, 문제가 발생하면 API 트래픽을 기존 Blue로 되돌리는 방식을 우선한다.

## 13. Phase 12 실행 명령

```bash
make local-bg
make deploy-status
make deploy-green
make deploy-smoke
make deploy-switch-green
make deploy-smoke
make deploy-rollback
make deploy-verify
```

전체 시뮬레이션:

```bash
make phase12-check
```

rollback 검증:

```bash
make phase12-rollback-check
```

Green 검증 실패나 Nginx config test 실패 시 upstream은 전환하지 않는다.
전환 후 smoke/readiness 검증이 실패하면 `AUTO_ROLLBACK=true` 기본 정책에 따라 `scripts/rollback.sh`를 호출해 Blue로 되돌린다.

## 14. Ops Phase 2 실행 명령

Ops Phase 2에서는 Phase 12에서 만든 Blue-Green 전환 구조를 운영자가 더 직접적으로 실행할 수 있도록 별도 진입점을 제공한다.
기존 `deploy-*` 명령은 유지하고, `ops2-*` 명령은 Blue 시작, Green 검증, traffic switch, rollback을 단계별로 재현하는 데 사용한다.

| 명령 | 역할 |
|---|---|
| `make ops2-start-blue` | PostgreSQL, Redis, Blue API, Nginx 실행 |
| `make ops2-start-green` | `green-deployment` profile로 Green 실행 후 `/health`, `/ready`, Nginx 내부 접근 검증 |
| `make ops2-check-blue` | Nginx 기준 `/health`, `/ready` 확인 |
| `make ops2-check-green` | Green 직접 endpoint 기준 `/health`, `/ready` 확인 |
| `make ops2-check-routed-blue` | active color, active snippet, Nginx loaded config가 Blue를 가리키는지 확인 |
| `make ops2-check-routed-green` | active color, active snippet, Nginx loaded config가 Green을 가리키는지 확인 |
| `make ops2-smoke-green` | Green 대상으로 HMAC POST, idempotency replay, validation failure smoke 실행 |
| `make ops2-smoke-routed` | Nginx `BASE_URL` 경유로 HMAC POST, idempotency replay, validation failure smoke 실행 |
| `make ops2-switch-green` | `scripts/switch_traffic.sh green`으로 Nginx upstream을 Green으로 전환 |
| `make ops2-switch-blue` | `scripts/switch_traffic.sh blue`로 Nginx upstream을 Blue로 전환 |
| `make ops2-rollback` | `scripts/rollback_to_blue.sh`로 Blue rollback 후 health/readiness 확인 |
| `make ops2-status` | Blue/Green/Nginx 상태와 active upstream 출력 |
| `make ops2-cleanup` | Blue rollback 후 Green 컨테이너 중지 |
| `make ops2-demo` | Blue 시작부터 Green 전환, Blue rollback까지 한 번에 재현 |

직접 실행 흐름:

```bash
make ops2-start-blue
make ops2-check-routed-blue
make ops2-start-green
make ops2-check-green
make ops2-smoke-green
make ops2-switch-green
make ops2-check-routed-green
make ops2-smoke-routed
make ops2-rollback
make ops2-check-routed-blue
```

`scripts/switch_traffic.sh`는 `blue` 또는 `green`만 인자로 허용한다.
전환 전 현재 active upstream을 출력하고, snippet 교체 후 `nginx -t`가 성공할 때만 reload한다.
`nginx -t` 또는 reload가 실패하면 이전 snippet과 active color 상태를 복구한다.
전환 후에는 `scripts/check_active_upstream.sh`가 `.active-color`, active upstream snippet, Nginx 컨테이너에 로드된 config를 함께 확인한다.
이 검증은 설정과 로드된 Nginx 상태를 확인하는 방어선이며, 실제 요청 경로 검증은 `make ops2-smoke-routed`로 Nginx 경유 거래 smoke를 다시 실행해 보완한다.

`scripts/deploy_green.sh`는 Green 컨테이너를 시작하고 `http://localhost:8001/health`, `http://localhost:8001/ready`, Nginx 컨테이너 내부 `api-green:8000/health` 접근을 확인한다.
Green이 준비되지 않으면 non-zero exit로 실패하고, `STOP_GREEN_ON_FAILURE=true`일 때 Green 컨테이너를 중지한다.
`make ops2-start-green`은 Blue 운영 상태가 전제이므로 `ops2-start-blue`를 먼저 실행한다.

`scripts/rollback_to_blue.sh --stop-green`은 Blue rollback 이후 Green 컨테이너까지 중지한다.
기본 rollback은 traffic rollback만 수행하며 DB schema downgrade는 실행하지 않는다.
