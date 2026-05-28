# Phase 9 Performance Results

이 문서는 Phase 9 k6 부하 테스트 실행 결과를 기록하는 작업 문서다.
아직 로컬에서 측정하지 않은 값은 `TBD`로 둔다.
임의 수치를 채우지 않고, 실행 환경과 git commit hash를 함께 기록한 뒤 비교한다.

## 실행 환경

| 항목 | 값 |
|------|----|
| 날짜 | TBD |
| Git commit hash | TBD |
| 실행 환경 | TBD |
| OS / CPU / Memory | TBD |
| Docker Compose 사용 여부 | TBD |
| API worker 수 | TBD |
| DB pool size | TBD |
| Redis 사용 여부 | TBD |
| BASE_URL | `http://localhost:8080` |
| CLIENT_ID | `bank-a` |
| HMAC_ENABLED | `true` |
| k6 version | TBD |

## 로컬 Sanity 실행 메모

아래 값은 Phase 9 스크립트가 실제 실행되는지 확인하기 위한 로컬 sanity run 결과다.
정식 비교 실험 수치는 같은 환경을 고정한 뒤 별도로 반복 측정해 아래 결과 표에 기록한다.

| 날짜 | 시나리오 | 조건 | p95 | p99 | RPS | error rate | unexpected response rate | server error rate | ledger 중복 |
|------|----------|------|-----|-----|-----|------------|--------------------------|-------------------|-------------|
| 2026-05-29 | smoke | Docker k6, 1 VU, 3 iterations | 89.51ms | 106.68ms | 1.87 req/s | 0.00% | 0.00% | 0.00% | N/A |
| 2026-05-29 | duplicate storm | Docker k6, 10 VUs, 5s | 19.90ms | 89.46ms | 162.63 req/s | 0.00% | 0.00% | 0.00% | 0건 |

초기 duplicate storm 검증 중 Nginx `limit_req zone="general"`이 503을 반환해 앱/Redis/DB 경로 측정을 가렸다.
기본 Nginx 설정은 운영형 rate limit을 유지하고, Phase 9 로컬 실험에서는 `docker-compose.perf.yml`과 `infra/nginx/nginx.perf.conf`를 사용해 duplicate storm이 애플리케이션까지 도달하도록 분리했다.

`unexpected_response_rate`와 `server_error_rate`는 HTTP 응답 정책 기준의 k6 지표다.
실제 duplicate processing rate는 HTTP status가 아니라 PostgreSQL 검증 쿼리의 ledger 중복 생성 여부로 판단한다.

## 실행 명령

| 시나리오 | 명령 | 결과 기록 |
|----------|------|-----------|
| smoke | `make k6-smoke` | TBD |
| normal load | `make k6-normal` | TBD |
| peak load | `make k6-peak` | TBD |
| duplicate storm | `make k6-duplicate` | TBD |
| redis down | `make k6-redis-down-check` | TBD |
| PostgreSQL 정합성 검증 | `make k6-verify` | TBD |
| Redis Cache off | `make perf-cache-off` | TBD |
| Redis Cache on | `make perf-cache-on` | TBD |
| Redis Lock off | `make perf-lock-off` | TBD |
| Redis Lock on | `make perf-lock-on` | TBD |
| DB Pool 5 | `make perf-db-pool-5` | TBD |
| DB Pool 10 | `make perf-db-pool-10` | TBD |
| DB Pool 20 | `make perf-db-pool-20` | TBD |

## Smoke 결과

| p50 | p95 | p99 | RPS | error rate | HMAC failures | 비고 |
|-----|-----|-----|-----|------------|---------------|------|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Normal Load 결과

| VUs | duration | p50 | p95 | p99 | RPS | error rate | transaction duration | DB connection usage |
|-----|----------|-----|-----|-----|-----|------------|----------------------|---------------------|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Peak Load 결과

| VUs | duration | p50 | p95 | p99 | RPS | error rate | 5xx rate | DB connection usage |
|-----|----------|-----|-----|-----|-----|------------|----------|---------------------|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Duplicate Storm 결과

| VUs | duration | p50 | p95 | p99 | 200 | 202 | 409 | error rate | unexpected response rate | ledger 중복 |
|-----|----------|-----|-----|-----|-----|-----|-----|------------|---------------------------|-------------|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

정합성 확인:

```bash
make k6-verify
```

`tests/k6/sql/verify-consistency.sql`의 쿼리를 실행해 동일 `external_event_id` 또는 동일 `transaction_event_id`에 대해 중복 반영이 발생하지 않았는지 확인한다.

## Redis Down 결과

| VUs | duration | p50 | p95 | p99 | RPS | error rate | redis unavailable | unexpected response rate | ledger 중복 |
|-----|----------|-----|-----|-----|-----|------------|-------------------|---------------------------|-------------|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Redis Down 실행 절차:

```bash
make k6-redis-down-check
make k6-verify
```

Redis 장애 중에도 PostgreSQL 기준 ledger 중복 생성은 0건이어야 한다.

## Redis Cache 사용 전/후 비교

| 조건 | p50 | p95 | p99 | RPS | error rate | cache hit ratio | DB lookup/transaction 지표 | ledger 중복 |
|------|-----|-----|-----|-----|------------|-----------------|----------------------------|---------------------------|
| Cache off | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Cache on | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Redis Lock 사용 전/후 비교

| 조건 | p50 | p95 | p99 | RPS | error rate | lock rejected | DB transaction count | ledger 중복 |
|------|-----|-----|-----|-----|------------|---------------|----------------------|---------------------------|
| DB unique only | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Redis Lock + DB unique | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## DB Pool Size 비교

| DB_POOL_SIZE | DB_MAX_OVERFLOW | p50 | p95 | p99 | RPS | error rate | DB connection usage | transaction duration |
|--------------|-----------------|-----|-----|-----|-----|------------|---------------------|----------------------|
| 5 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 10 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 20 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## 판단 기준

| 지표 | 기준 |
|------|------|
| PostgreSQL duplicate processing rate | 0% |
| ledger 중복 생성 | 0건 |
| unexpected response rate | 0% |
| server error rate | 0% |
| p95 latency | 목표 300ms 이하, peak/redis-down은 실험 조건과 함께 해석 |
| p99 latency | 목표 1000ms 이하, 꼬리 지연 원인 기록 |
| error rate | 1% 이하를 기본 목표로 하되 peak 조건은 5xx와 4xx를 분리 |
| cache hit ratio | 중복 요청 조건에서 80% 이상 목표 |
| DB connection usage | 80% 이하 목표 |

## 결론

| 항목 | 판단 |
|------|------|
| Redis Cache 유지 여부 | TBD |
| Redis Lock 유지 여부 | TBD |
| 권장 DB pool size | TBD |
| 병목 원인 | TBD |
| 후속 Phase 10 장애 재현 필요 항목 | TBD |
