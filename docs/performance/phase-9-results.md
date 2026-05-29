# Phase 9 Performance Results

이 문서는 Phase 9 k6 부하 테스트 실행 결과를 기록하는 작업 문서다.
2026-05-29 KST 기준 로컬 Docker Compose 환경에서 짧은 비교 실험을 실행했다.
운영 벤치마크가 아니라 Phase 9 설계 판단을 위한 재현 가능한 로컬 측정값이다.

## 실행 환경

| 항목 | 값 |
|------|----|
| 날짜 | 2026-05-29 KST |
| Git commit hash | 측정 기준 HEAD `0efc752`, 결과 기록 커밋은 PR 최신 commit 참조 |
| 실행 환경 | Local Docker Compose + Docker k6 |
| OS / CPU / Memory | Darwin 25.3.0 x86_64 / CPU, Memory는 로컬 장비 설정 의존 |
| Docker Compose 사용 여부 | `docker-compose.yml` + `docker-compose.perf.yml` |
| API worker 수 | Uvicorn 단일 프로세스 |
| DB pool size | compose 기본 10/5, 비교 실험은 5/0, 10/5, 20/10 |
| Redis 사용 여부 | enabled, Redis down 실험에서는 `docker compose pause redis` |
| BASE_URL | `http://localhost:8080` |
| CLIENT_ID | `bank-a` |
| HMAC_ENABLED | `true` |
| k6 version | `k6 v2.0.0+dirty` Docker image |

## 로컬 Sanity 실행 메모

아래 값은 Phase 9 스크립트가 처음 실제 실행되는지 확인하기 위한 로컬 sanity run 결과다.
정식 비교 실험 수치는 같은 환경을 고정한 뒤 아래 결과 표에 별도로 기록했다.

| 날짜 | 시나리오 | 조건 | p95 | p99 | RPS | error rate | unexpected response rate | server error rate | ledger 중복 |
|------|----------|------|-----|-----|-----|------------|--------------------------|-------------------|-------------|
| 2026-05-29 | smoke | Docker k6, 1 VU, 3 iterations | 89.51ms | 106.68ms | 1.87 req/s | 0.00% | 0.00% | 0.00% | 해당 없음 |
| 2026-05-29 | duplicate storm | Docker k6, 10 VUs, 5s | 19.90ms | 89.46ms | 162.63 req/s | 0.00% | 0.00% | 0.00% | 0건 |

초기 duplicate storm 검증 중 Nginx `limit_req zone="general"`이 503을 반환해 앱/Redis/DB 경로 측정을 가렸다.
기본 Nginx 설정은 운영형 rate limit을 유지하고, Phase 9 로컬 실험에서는 `docker-compose.perf.yml`과 `infra/nginx/nginx.perf.conf`를 사용해 duplicate storm이 애플리케이션까지 도달하도록 분리했다.

`unexpected_response_rate`와 `server_error_rate`는 HTTP 응답 정책 기준의 k6 지표다.
실제 duplicate processing rate는 HTTP status가 아니라 PostgreSQL 검증 쿼리의 ledger 중복 생성 여부로 판단한다.

## 실행 명령

| 시나리오 | 명령 | 결과 기록 |
|----------|------|-----------|
| smoke | Docker k6, `tests/k6/smoke-test.js` | 통과 |
| normal load | Docker k6, `tests/k6/normal-load.js` | 통과 |
| peak load | Docker k6, `tests/k6/peak-load.js` | p95 threshold 실패, 5xx/중복 없음 |
| duplicate storm | Docker k6, `tests/k6/duplicate-storm.js` | 통과 |
| redis down | Redis pause 후 Docker k6, `tests/k6/redis-down-test.js` | threshold 실패, PostgreSQL 중복 없음 |
| PostgreSQL 정합성 검증 | `make k6-verify` | ledger/external_event 중복 0건 |
| Redis Cache off | `IDEMPOTENCY_CACHE_ENABLED=false` + duplicate storm | 통과 |
| Redis Cache on | `IDEMPOTENCY_CACHE_ENABLED=true` + duplicate storm | 통과 |
| Redis Lock off | `REDIS_LOCK_ENABLED=false` + duplicate storm | server error 발생 |
| Redis Lock on | `REDIS_LOCK_ENABLED=true` + duplicate storm | 통과 |
| DB Pool 5 | `DB_POOL_SIZE=5 DB_MAX_OVERFLOW=0` + peak load | p95 threshold 실패, 5xx/중복 없음 |
| DB Pool 10 | `DB_POOL_SIZE=10 DB_MAX_OVERFLOW=5` + peak load | p95/p99 threshold 실패, 5xx/중복 없음 |
| DB Pool 20 | `DB_POOL_SIZE=20 DB_MAX_OVERFLOW=10` + peak load | p95/p99 threshold 실패, 5xx/중복 없음 |

## Smoke 결과

| p50 | p95 | p99 | RPS | error rate | HMAC failures | 비고 |
|-----|-----|-----|-----|------------|---------------|------|
| 13.93ms | 83.65ms | 99.27ms | 1.89 req/s | 0.00% | 0 | `/health` + POST 3회, HMAC enabled |

## Normal Load 결과

| VUs | duration | p50 | p95 | p99 | RPS | error rate | transaction duration | DB connection usage |
|-----|----------|-----|-----|-----|-----|------------|----------------------|---------------------|
| 20 | 5s ramp-up, 15s steady, 5s ramp-down | 44.68ms | 181.18ms | 261.73ms | 60.77 req/s | 0.00% | avg 63.21ms | 미수집 |

## Peak Load 결과

| VUs | duration | p50 | p95 | p99 | RPS | error rate | 5xx rate | DB connection usage |
|-----|----------|-----|-----|-----|-----|------------|----------|---------------------|
| 50 | 5s ramp-up, 15s steady, 5s ramp-down | 793.88ms | 1369.66ms | 1490ms | 55.11 req/s | 0.00% | 0.00% | 미수집 |

Peak load는 p95 목표 800ms를 초과했지만, 5xx와 unexpected response는 발생하지 않았다.
즉 기능 정합성은 유지되나 현재 로컬 단일 API 프로세스 구성에서는 peak latency 튜닝이 필요하다.

## Duplicate Storm 결과

| VUs | duration | p50 | p95 | p99 | 200 | 202 | 409 | error rate | unexpected response rate | ledger 중복 |
|-----|----------|-----|-----|-----|-----|-----|-----|------------|---------------------------|-------------|
| 50 | 15s | 32.17ms | 70.57ms | 96.81ms | 6891 | 1689 | 0 | 0.00% | 0.00% | 0건 |

정합성 확인:

```bash
make k6-verify
```

`tests/k6/sql/verify-consistency.sql`의 쿼리를 실행해 동일 `external_event_id` 또는 동일 `transaction_event_id`에 대해 중복 반영이 발생하지 않았는지 확인한다.

## Redis Down 결과

| VUs | duration | p50 | p95 | p99 | RPS | error rate | redis unavailable | unexpected response rate | ledger 중복 |
|-----|----------|-----|-----|-----|-----|------------|-------------------|---------------------------|-------------|
| 30 | 15s | 614.89ms | 722.21ms | 3490ms | 38.21 req/s | 6.86% | 5xx/failure로 관측 | 2.34% | 0건 |

Redis Down 실행 절차:

```bash
make k6-redis-down-check
make k6-verify
```

Redis 장애 중에도 PostgreSQL 기준 ledger 중복 생성은 0건이어야 한다.
이번 로컬 실행에서는 중복은 0건이었지만 5xx가 14건 발생했다.
따라서 Phase 9 시점의 결론은 "최종 정합성은 유지됐지만 Redis 장애 중 API 가용성은 보완 필요"였다.
이 항목은 Phase 10에서 Redis fallback hardening과 DB unique conflict retry를 추가해 보완했다.
최신 Redis Down duplicate storm 결과는 [Phase 10 Failure Recovery](../phase-10-failure-recovery.md)에 기록한다.

| 검증 관점 | 결과 | 판단 |
|-----------|------|------|
| 최종 정합성 | ledger 중복 0건, external_event 중복 0건 | 통과 |
| API 가용성 | 5xx 14건, error rate 6.86% | Phase 9 기준 미달, Phase 10에서 보완 |
| Redis fallback 품질 | 일부 요청 실패 및 p99 3490ms | Phase 10에서 Redis fallback hardening 적용 |

## Redis Cache 사용 전/후 비교

| 조건 | p50 | p95 | p99 | RPS | error rate | cache hit ratio | DB lookup/transaction 지표 | ledger 중복 |
|------|-----|-----|-----|-----|------------|-----------------|----------------------------|---------------------------|
| Cache off | 61.49ms | 128.88ms | 171.62ms | 403.08 req/s | 0.00% | 해당 없음, cache disabled | 6086 requests / 4851 completed / 1235 processing | 0건 |
| Cache on | 40.32ms | 84.37ms | 119.44ms | 511.15 req/s | 1.34% k6 default, 0.00% unexpected | same-key storm에서는 409 허용 응답 때문에 ratio 해석 불가 | 7713 requests / 6416 completed / 1194 processing / 103 conflicts | 0건 |

Cache on은 duplicate storm에서 p95가 약 34.5% 감소했고 RPS는 약 26.8% 증가했다.
다만 k6의 기본 `http_req_failed`는 409를 실패로 분류하므로, duplicate 시나리오 판단에는 `unexpected_response_rate`와 PostgreSQL 검증 결과를 함께 사용한다.
정식 duplicate storm run은 409가 0건이었지만 Cache on 비교 run에서는 409가 103건 발생했다.
같은 Idempotency-Key와 같은 canonical body에서는 일반적으로 200 replay 또는 202 already-processing이 더 자연스럽기 때문에, 이 409는 API 정책 또는 동시성 race 후속 분석 대상으로 남긴다.

## Redis Lock 사용 전/후 비교

| 조건 | p50 | p95 | p99 | RPS | error rate | lock rejected | DB transaction count | ledger 중복 |
|------|-----|-----|-----|-----|------------|---------------|----------------------|---------------------------|
| DB unique only | 33.99ms | 98.85ms | 178.68ms | 517.34 req/s | 0.33% | 해당 없음, lock disabled | 7814 requests / 7788 completed / 26 failures | 0건 |
| Redis Lock + DB unique | 36.53ms | 70.15ms | 102.86ms | 534.36 req/s | 0.00% | 549 processing responses | 8074 requests / 7525 completed / 549 processing | 0건 |

Lock off는 처리량이 높아 보였지만 5xx 26건이 발생했다.
금융 이벤트 시스템의 판단 기준에서는 Redis Lock + PostgreSQL unique 조합이 tail latency와 안정성 모두 더 낫다.
Lock off에서 발생한 5xx는 동일 `external_event_id` 동시 insert/update 경합, idempotency record terminal 상태 전환 경합, 또는 DB unique conflict 처리 경로의 예외 전파 가능성이 있다.
Phase 10에서는 DB unique conflict rollback 후 read/retry 경로와 Redis fallback 구조화 로그를 추가해 이 계열의 장애를 재현하고 추적할 수 있게 했다.

## DB Pool Size 비교

| DB_POOL_SIZE | DB_MAX_OVERFLOW | p50 | p95 | p99 | RPS | error rate | DB connection usage | transaction duration |
|--------------|-----------------|-----|-----|-----|-----|------------|---------------------|----------------------|
| 5 | 0 | 266.95ms | 1060.49ms | 1100ms | 71.82 req/s | 0.00% | 미수집 | avg 463.59ms |
| 10 | 5 | 435.93ms | 1293.26ms | 1530ms | 68.18 req/s | 0.00% | 미수집 | avg 493.26ms |
| 20 | 10 | 167.10ms | 2478.11ms | 2780ms | 52.35 req/s | 0.00% | 미수집 | avg 674.78ms |

이 로컬 단기 실행에서는 pool size를 키울수록 p95/p99가 개선되지 않았다.
단일 API 프로세스와 로컬 Docker Desktop I/O 조건에서는 DB connection을 늘리는 것보다 트랜잭션 범위, row lock 대기, 컨테이너 리소스 제한을 함께 봐야 한다.
현재 애플리케이션 메트릭에는 SQLAlchemy pool checked-out/overflow 사용량이 직접 export되지 않아 DB connection usage는 실제 수치로 기록하지 못했다.
PostgreSQL exporter 또는 SQLAlchemy pool gauge 추가가 필요하지만, 이는 Phase 9 결과의 후속 관측 보완 항목으로 남긴다.
Phase 11에서는 배포 Gate를 우선 고도화했으므로 `api-green`, Redis exporter, PostgreSQL exporter 기반 인프라 내부 지표는 Phase 12 이후 운영 관측 보강 항목으로 남긴다.

## Transaction 범위 비교

Phase 9에서는 비즈니스 로직, DB 모델, 상태 머신, 트랜잭션 처리 로직을 임의로 바꾸지 않는 제약을 우선했다.
현재 코드에는 transaction boundary를 안전하게 on/off 비교할 환경변수나 compose override가 없으므로, 트랜잭션 범위 자체를 바꾸는 비교 실험은 실행하지 않았다.
대신 normal/peak/duplicate/redis-down 및 Redis Cache/Lock/DB Pool 조건에서 `financial_transaction_processing_duration_seconds`와 k6 `transaction_api_duration_ms`를 관찰 대상으로 삼았다.

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
| Redis Cache 유지 여부 | 유지. duplicate storm에서 p95 128.88ms -> 84.37ms, RPS 403.08 -> 511.15로 개선 |
| Redis Lock 유지 여부 | 유지. Lock off는 5xx 26건, Lock on은 5xx 0건 및 p95 70.15ms |
| 권장 DB pool size | 기본 10/5를 보수적 로컬 기본값으로 유지. 단기 peak run에서는 5/0이 가장 안정적이었으므로 운영값은 별도 장시간 측정 필요 |
| 병목 원인 | peak load p95 초과, Phase 9 Redis down 중 5xx, DB pool 확대 시 tail latency 악화 |
| Phase 10 보완 결과 | Redis 장애 fallback, DB unique conflict retry, Redis Down duplicate storm 5xx 0건과 중복 반영 0건 확인 |
| 후속 관측 보완 필요 항목 | DB connection 사용량 exporter 또는 SQLAlchemy pool gauge |

## 최종 정합성 검증

마지막 측정 후 `make k6-verify` 결과:

| 검증 항목 | 결과 |
|-----------|------|
| duplicated_ledger_event_count | 0 |
| duplicated_external_event_count | 0 |
| 동일 external_event_id 중복 row | 0 rows |
| 동일 transaction_event_id ledger 중복 row | 0 rows |
