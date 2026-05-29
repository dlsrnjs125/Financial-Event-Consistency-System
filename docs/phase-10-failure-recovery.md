# Phase 10 - Failure Recovery & Redis Fallback Hardening

## 1. 목적

Phase 10은 Phase 9 성능 측정에서 확인된 Redis Down duplicate storm의 일부 5xx 문제를 보완하는 단계다.
Redis를 최종 정합성 저장소가 아니라 중복 요청 완화와 응답 캐시를 위한 성능 최적화 계층으로 정의하고, Redis 장애 시 PostgreSQL transaction, unique constraint, idempotency record를 기준으로 degraded mode 처리를 수행한다.

목표는 장애 상황을 반복 재현하고, 장애 발생 중에도 동일 금융 이벤트와 동일 idempotency request가 중복 반영되지 않는지 검증 가능하게 만드는 것이다.

## 2. 장애 시나리오

### 2.1 Redis Down

- 장애 상황: Redis 컨테이너가 중지되어 lock/cache get/set/release 작업이 실패한다.
- 예상 원인: Redis 프로세스 장애, 네트워크 단절, 컨테이너 중지, Redis 재시작.
- 사용자 영향: 캐시 재사용과 Redis lock 기반 중복 완화가 사라져 응답 시간이 증가할 수 있다.
- 정합성 위험: duplicate storm 중 PostgreSQL unique constraint 경합이 증가한다.
- 탐지 방법: `financial_redis_fallback_total`, `financial_redis_operation_failed_total`, `/ready`의 Redis failed, structured log의 `redis_*_fallback`.
- 대응 전략: Redis 작업 실패를 warning log/metric으로 기록하고 DB transaction, idempotency record, unique constraint 기준으로 처리한다.
- 복구 후 검증 방법: `make failure-redis-up`, `make k6-verify`, `/metrics`에서 fallback metric 확인.
- README에 기록할 요약 문장: Redis Down 중에도 PostgreSQL 기준 중복 Ledger 반영은 0건이어야 하며, Redis 실패는 fallback metric/log로 추적한다.

### 2.2 Redis Timeout

- 장애 상황: Redis 연결은 존재하지만 socket timeout으로 lock/cache 작업이 제한 시간 내 완료되지 않는다.
- 예상 원인: Redis 부하, 네트워크 지연, max connection 고갈, 컨테이너 CPU starvation.
- 사용자 영향: 일부 요청이 Redis timeout 지연만큼 느려질 수 있다.
- 정합성 위험: Redis lock이 적용되지 않아 DB 경합이 증가한다.
- 탐지 방법: `financial_redis_operation_failed_total{reason="timeout"}`, `financial_redis_fallback_total{reason="timeout"}`.
- 대응 전략: Redis timeout은 PostgreSQL fallback 대상이며, DB 오류와 구분해 처리한다.
- 복구 후 검증 방법: timeout 설정을 복구한 뒤 Redis cache hit/lock acquired metric이 정상 증가하는지 확인한다.
- README에 기록할 요약 문장: Redis timeout은 단독 5xx 사유가 아니며 DB 기준 degraded mode로 계속 처리한다.

### 2.3 Duplicate Event Storm

- 장애 상황: 동일 `Idempotency-Key`와 동일 body 또는 동일 `external_event_id`가 여러 VU에서 동시에 들어온다.
- 예상 원인: 외부 금융사의 재시도 폭주, webhook retry, 네트워크 timeout 후 client-side 재전송.
- 사용자 영향: 일부 요청은 기존 응답 replay, 202 processing, 또는 현재 정책에 따른 409 conflict를 받을 수 있다.
- 정합성 위험: 동일 이벤트가 Ledger에 여러 번 반영될 수 있다.
- 탐지 방법: `financial_idempotency_duplicate_total`, `financial_duplicate_external_event_total`, `financial_db_transaction_retry_total`.
- 대응 전략: Redis lock이 없거나 실패해도 PostgreSQL unique constraint 충돌 시 rollback 후 한 번 재시도해 기존 idempotency/event 결과를 읽는다.
- 복구 후 검증 방법: `make k6-redis-down-duplicate-storm` 실행 후 `make k6-verify`로 중복 Ledger 0건을 확인한다.
- README에 기록할 요약 문장: duplicate storm의 최종 성공 기준은 HTTP 응답만이 아니라 PostgreSQL 중복 반영 0건이다.

### 2.4 PostgreSQL Connection Failure

- 장애 상황: PostgreSQL 컨테이너가 중지되거나 DB 연결 풀이 고갈된다.
- 예상 원인: DB 프로세스 장애, 네트워크 단절, pool timeout, migration 또는 운영 작업 실패.
- 사용자 영향: `/ready`가 503을 반환하고 거래 이벤트 처리는 실패할 수 있다.
- 정합성 위험: DB transaction을 시작할 수 없으므로 새 거래 반영이 불가능하다.
- 탐지 방법: `/ready`, `financial_readiness_dependency_status{dependency="postgres"}`, API 5xx/503.
- 대응 전략: Redis fallback과 구분한다. PostgreSQL은 Source of Truth이므로 DB 장애 시 성공 처리하지 않는다.
- 복구 후 검증 방법: `docker compose start postgres`, `/ready`, `make k6-verify` 확인.
- README에 기록할 요약 문장: PostgreSQL 장애는 정합성 기준 저장소 장애이므로 Redis 장애와 달리 정상 처리로 간주하지 않는다.

### 2.5 API Server Restart During Processing

- 장애 상황: 거래 처리 중 API 컨테이너가 재시작된다.
- 예상 원인: 배포, 컨테이너 재시작, 프로세스 crash, host maintenance.
- 사용자 영향: 처리 중 요청은 client timeout 또는 5xx가 될 수 있고, client 재시도가 필요하다.
- 정합성 위험: transaction 경계 밖 부수효과가 있으면 중복 반영될 수 있다.
- 탐지 방법: API container restart count, request log의 trace_id/request_id 단절, `financial_http_errors_total`.
- 대응 전략: balance 변경과 Ledger 생성은 DB transaction 안에서 원자적으로 처리하고, client 재시도는 idempotency record와 unique constraint로 방어한다.
- 복구 후 검증 방법: `make failure-api-restart` 후 동일 idempotency request를 재전송하고 `make k6-verify`를 실행한다.
- README에 기록할 요약 문장: API 재시작 후 client 재시도는 idempotency key와 PostgreSQL unique constraint로 중복 반영을 방어한다.

## 3. Redis Fallback 정책

### Redis 정상 시 요청 흐름

1. API가 `Idempotency-Key`와 HMAC signature를 검증한다.
2. Redis lock을 획득해 동일 key의 동시 DB 진입을 완화한다.
3. Redis completed response cache hit이면 DB 처리 없이 완료 응답을 replay한다.
4. cache miss이면 PostgreSQL idempotency record를 확인하거나 생성한다.
5. TransactionEvent, LedgerEntry, Account.balance, IdempotencyRecord를 DB transaction 안에서 처리한다.
6. 완료 응답을 Redis cache에 저장하고 Redis lock을 해제한다.

### Redis 장애 시 요청 흐름

1. Redis lock/cache 작업 실패를 `warning` log와 Prometheus metric으로 기록한다.
2. Redis lock/cache를 생략하고 PostgreSQL transaction으로 진입한다.
3. 동일 idempotency key 또는 external event 경합에서 unique conflict가 발생하면 rollback 후 한 번 재시도한다.
4. 재시도 시 기존 idempotency record 또는 transaction event를 읽어 replay/processing/duplicate 응답을 반환한다.
5. PostgreSQL에서도 처리할 수 없는 오류만 5xx 계열 오류로 둔다.

### PostgreSQL을 최종 정합성 기준으로 삼는 이유

PostgreSQL은 transaction, row lock, unique constraint, durable storage를 제공한다.
Redis는 빠른 lock/cache 계층이지만 장애, eviction, timeout, 재시작 가능성이 있으므로 금융 이벤트의 최종 반영 여부를 판단하는 저장소가 될 수 없다.

### Redis fallback에서 포기한 것

- Redis cache hit 기반 빠른 replay
- Redis lock 기반 duplicate storm DB 부하 완화
- Redis 정상 시 기대하는 낮은 p95/p99 latency

### 보완 전략

- PostgreSQL unique constraint를 최종 duplicate defense로 유지한다.
- DB unique conflict는 rollback 후 read/retry로 기존 결과를 재구성한다.
- Redis fallback metric/log를 남겨 장애 빈도와 영향 범위를 관측한다.
- k6 Redis Down duplicate storm과 `make k6-verify`를 함께 실행해 정합성과 가용성을 분리해 판단한다.

## 4. 검증 결과 기록 양식

| Scenario | Expected | Actual | Duplicate Ledger Count | 5xx Count | p95 | Result |
|---|---|---|---:|---:|---:|---|
| Redis Down duplicate storm | fallback 처리, 중복 Ledger 0건 | 5013 requests, 200/409 only, 5xx 0건 | 0 | 0 | 651.15ms | PASS |
| Redis Timeout | fallback 처리, Redis timeout metric 기록 | TBD | TBD | TBD | TBD | TBD |
| Duplicate Event Storm | replay/processing/conflict 응답, 중복 Ledger 0건 | TBD | TBD | TBD | TBD | TBD |
| PostgreSQL Connection Failure | readiness 503, 거래 성공 처리 없음 | TBD | TBD | TBD | TBD | TBD |
| API Restart During Processing | 재시도 시 idempotency/unique constraint로 방어 | TBD | TBD | TBD | TBD | TBD |

2026-05-29 KST 로컬 Docker Compose 환경에서 `api-blue` 재시작 후 Redis를 중지하고 `grafana/k6` 컨테이너로 `tests/k6/redis_down_duplicate_storm.js`를 실행했다.
결과는 5013 requests, p95 651.15ms, p99 2.28s, `server_error_rate` 0.00%, `unexpected_response_rate` 0.00%였고, PostgreSQL 검증에서 duplicated ledger/event count는 모두 0이었다.
`http_req_failed` 1.71%는 k6가 409 Conflict를 failed response로 집계한 값이며, Phase 10 시나리오의 허용 응답 집합에는 409가 포함된다.

수동 검증 명령:

```bash
make local-perf-bg
make failure-redis-down
make k6-redis-down-duplicate-storm
make k6-verify
make failure-redis-up
```

Prometheus 확인 지표:

```text
financial_redis_operation_total
financial_redis_operation_failed_total
financial_redis_fallback_total
financial_idempotency_duplicate_total
financial_transaction_event_processed_total
financial_transaction_event_failed_total
financial_transaction_event_conflict_total
financial_db_transaction_retry_total
financial_readiness_dependency_status
```
