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

---

## 3. 배포 흐름

1. main 브랜치 merge
2. CI 전체 테스트 실행
3. Docker 이미지 빌드
4. Green 컨테이너 실행
5. Green `/health` 확인
6. Green `/ready` 확인
7. DB Migration 적용
8. Smoke Test 실행
9. Consistency Test 실행
10. Nginx upstream Green으로 전환
11. 배포 후 메트릭 관찰
12. 이상 발생 시 Blue로 rollback

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
| Redis Connection | 연결 가능 또는 fallback 동작 확인 |
| OpenAPI Schema | 응답 스키마 깨짐 없음 |

---

## 5. Nginx upstream 전환

Blue 운영 상태:

```nginx
upstream api_backend {
    server api-blue:8000;
    # server api-green:8000;
}
```

Green 전환:

```nginx
upstream api_backend {
    # server api-blue:8000;
    server api-green:8000;
}
```

전환 전 검증:

```bash
nginx -t
```

검증 성공 후 reload한다.

```bash
nginx -s reload
```

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
| Migration 오류 | 즉시 rollback 또는 전환 중단 |

---

## 7. Rollback 방식

### API Rollback

Nginx upstream을 다시 Blue로 변경한다.

```nginx
upstream api_backend {
    server api-blue:8000;
    # server api-green:8000;
}
```

이후 reload한다.

```bash
nginx -t
nginx -s reload
```

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
