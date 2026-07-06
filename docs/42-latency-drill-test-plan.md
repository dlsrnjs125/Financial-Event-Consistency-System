# Latency Drill Test Plan

> k6는 latency 증상을 재현하는 도구다.
> 원인 귀속은 Nginx timing, FastAPI phase metric/log, Redis/PostgreSQL metric, external dependency metric, consistency SQL을 함께 보고 판단한다.

## 1. 목적

이 문서는 k6 부하 테스트와 장애 주입을 통해 latency 증가를 재현하고, 관측 evidence를 비교해 지연 원인 구간을 분류하는 테스트 계획을 정의한다.

목표:

- 기존 k6 normal/peak/duplicate/redis-down 시나리오를 Latency Attribution Drill의 baseline으로 재사용한다.
- DB pool pressure, DB lock contention, Redis delay/down, external dependency slow response, Nginx edge/client network 지연을 분리한다.
- latency 증가 중에도 duplicate ledger, duplicate external event, reconciliation failure가 발생하지 않는지 확인한다.
- 실제 구현 전에는 target과 script를 완료된 것처럼 쓰지 않고 후속 후보로만 관리한다.

## 2. k6만으로 가능한 것과 불가능한 것

k6로 가능한 것:

- client-side end-to-end latency 측정
- TTFB 성격의 `http_req_waiting` 측정
- connection, blocked, sending, receiving time 측정
- `http_req_failed`, checks, status 분포 측정
- 정상/peak/duplicate/redis-down 조건에서 사용자 체감 latency 비교

k6만으로 알 수 없는 것:

- HMAC 검증이 느린지
- idempotency lookup이 느린지
- Redis lock/cache가 느린지
- PostgreSQL transaction이 느린지
- DB connection pool wait이 긴지
- PostgreSQL lock wait이 긴지
- outbound external API call이 느린지
- Nginx upstream 연결이 느린지

따라서 k6는 latency 증상을 재현하는 도구로 사용한다.
원인 귀속은 Nginx log, FastAPI phase metric/log, Prometheus metric, consistency SQL 결과와 함께 판단한다.

## 3. 테스트 원칙

- latency drill은 정합성 검증과 분리하지 않는다.
- `http_req_failed`는 409 같은 허용 응답 정책과 함께 해석한다.
- Prometheus label에는 high-cardinality 값과 민감 식별자를 넣지 않는다.
- 장애 주입은 production path에 test-only 로직을 섞기보다 Toxiproxy, network delay, mock service, controlled DB lock 같은 외부 장치를 우선 검토한다.
- 구현되지 않은 metric은 "후속 후보"로 표시한다.

## 4. 공통 측정 지표

### k6

- `http_req_duration`
- `http_req_waiting`
- `http_req_blocked`
- `http_req_connecting`
- `http_req_sending`
- `http_req_receiving`
- `http_req_failed`
- checks

### Nginx

- `request_time`
- `upstream_response_time`
- `upstream_connect_time`
- `upstream_header_time`

### FastAPI

- `financial_http_request_duration_seconds`
- `financial_transaction_processing_duration_seconds`
- `app_phase_duration_seconds` 후보

### Redis

- `financial_redis_operation_total`
- `financial_redis_operation_failed_total`
- `financial_redis_fallback_total`
- `redis_operation_duration_seconds` 후보

### PostgreSQL

- `financial_db_transaction_retry_total`
- `db_pool_wait_duration_seconds` 후보
- `db_transaction_duration_seconds` 후보
- lock wait metric 후보

### External dependency

- `external_http_client_duration_seconds` 후보
- `external_dependency_probe_duration_seconds` 후보

### Consistency

- duplicate ledger count
- duplicate external event count
- reconciliation failure count
- invalid state transition count

금지 label:

- `account_id`
- `event_id`
- `idempotency_key`
- `trace_id`
- `request_id`
- raw URL
- raw account number
- customer identifier

허용 label:

- `route_group`
- `endpoint_group`
- `partner_alias`
- `method`
- `status_code`
- `result`
- `phase`
- `operation`

## 5. 공통 evidence 저장 구조

권장 저장 구조:

```text
reports/latency/{run_id}/
- k6-summary.json
- prometheus-snapshot.json
- nginx-timing-sample.log
- app-phase-metrics.txt
- consistency-check.txt
- latency-analysis.md
```

`latency-analysis.md` 포함 항목:

- scenario
- k6 p95/p99
- server handler p95/p99
- dependency phase p95/p99
- error rate
- consistency result
- latency classification
- evidence
- follow-up

예시:

```markdown
# Latency Drill Report

## Scenario
DB lock contention

## Summary
- k6 p95:
- k6 p99:
- server handler p95:
- postgres phase p95:
- redis phase p95:
- error rate:
- duplicate processing:
- reconciliation failure:

## Classification
internal_postgres_latency

## Evidence
- k6 p99 increased while DB phase duration increased.
- Redis metrics stayed normal.
- Duplicate ledger count remained 0.

## Follow-up
- Keep transaction scope short.
- Add DB lock wait metric.
```

## 6. LAT-001 Baseline Latency Drill

- 목적: 정상 상태의 latency 기준선을 만든다.
- 재현 방법: 기존 `tests/k6/normal-load.js`, `tests/k6/peak-load.js`를 활용한다.
- 실행 후보 명령:
  - `make k6-latency-baseline`
  - `make latency-report`
- 기대되는 k6 결과:
  - `http_req_duration` p50/p95/p99 기준선 기록
  - `http_req_waiting` p95/p99 기준선 기록
  - error rate 기준선 기록
- 기대되는 서버 metric/log:
  - Redis/DB/reconciliation 관련 이상 metric 없음
  - readiness dependency 정상
- latency classification: `baseline_normal_latency`
- 정합성 검증:
  - duplicate ledger count 0
  - duplicate external event count 0
  - reconciliation failure count 0
- 자동화 가능 범위: k6 summary와 Prometheus snapshot 수집.
- 수동 판단 필요 범위: baseline threshold 채택.
- Trade-off: 너무 낮은 local 기준선은 production SLO가 아니므로 환경 정보를 함께 기록한다.
- 후속 구현 후보: baseline report generator.

## 7. LAT-002 PostgreSQL Pool Pressure Drill

- 목적: DB connection pool wait이 증가하는 상황을 재현한다.
- 재현 방법: DB pool size를 작게 설정하거나 peak VU를 높여 pool pressure를 만든다.
- 실행 후보 명령:
  - `make latency-drill-db-pool`
  - `make k6-latency-db-pool`
  - `make latency-analyze`
- 기대되는 k6 결과:
  - p95/p99 증가
  - 일부 `503` 또는 timeout 가능
- 기대되는 서버 metric/log:
  - DB retry/error 증가 가능
  - readiness 또는 app log에서 DB pressure evidence 확인
  - `db_pool_wait_duration_seconds`는 후속 instrumentation 후보
- latency classification: `internal_postgres_pool_pressure`
- 정합성 검증:
  - 실패 요청이 있어도 duplicate ledger 0
  - reconciliation failure 0
- 자동화 가능 범위: k6 summary, readiness, app log, consistency SQL 수집.
- 수동 판단 필요 범위: pool size 변경 여부, query/transaction tuning 여부.
- Trade-off: pool wait metric이 없으면 p99 증가와 DB error는 정황 증거일 뿐 원인 확정에는 부족하다.
- 후속 구현 후보: SQLAlchemy pool wait timer.

## 8. LAT-003 PostgreSQL Lock Contention Drill

- 목적: 특정 row lock contention으로 transaction 지연이 증가하는 상황을 재현한다.
- 재현 방법: 특정 account row 또는 transaction 대상 row에 lock을 유지한 상태에서 같은 account 요청을 집중시킨다.
- 실행 후보 명령:
  - `make latency-drill-db-lock`
  - `make k6-latency-db-lock`
  - `make latency-analyze`
- 기대되는 k6 결과:
  - p95/p99 증가
  - timeout 또는 503 가능
- 기대되는 서버 metric/log:
  - DB transaction phase duration 증가
  - Redis phase 정상
  - lock wait metric은 후속 후보
- latency classification: `internal_postgres_lock_contention`
- 정합성 검증:
  - duplicate processing 0
  - reconciliation failure 0
  - invalid state transition 0
- 자동화 가능 범위: lock holder evidence, k6 summary, DB phase metric, consistency SQL 수집.
- 수동 판단 필요 범위: lock 발생 query와 transaction scope 검토.
- Trade-off: lock을 강제로 유지하는 drill은 production과 다를 수 있으나 병목 분류 rule 검증에는 유용하다.
- 후속 구현 후보: controlled lock holder script.

## 9. LAT-004 Redis Delay / Redis Down Drill

- 목적: Redis가 완전히 down된 경우와 느려진 경우를 분리한다.
- 재현 방법: 기존 Redis down 테스트를 유지하고, Redis delay injection 후보를 별도 설계한다.
- 실행 후보 명령:
  - `make latency-drill-redis-delay`
  - `make k6-latency-redis-delay`
  - `make k6-redis-down`
  - `make latency-analyze`
- Redis delay 재현 후보:
  - A안: Toxiproxy로 Redis latency 주입
  - B안: docker network/netem으로 Redis network delay 주입
  - C안: test-only Redis client wrapper에서 delay 주입
- 기대되는 k6 결과:
  - Redis delay에서는 p95/p99 증가 가능
  - Redis down에서는 fallback path와 일부 availability degradation 관측 가능
- 기대되는 서버 metric/log:
  - Redis operation duration 증가 후보
  - Redis fallback 증가
  - PostgreSQL 부하 전이 가능
- latency classification:
  - `redis_degraded_latency`
  - `redis_unavailable_fallback`
- 정합성 검증:
  - Redis 장애 중에도 duplicate ledger 0
  - duplicate external event 0
- 자동화 가능 범위: Redis down은 기존 흐름 재사용, delay는 후속 fault injection 필요.
- 수동 판단 필요 범위: Redis 복구, fallback 지속 허용 여부.
- Trade-off: down 테스트는 단순하지만 timeout/slow Redis의 현실성을 충분히 설명하지 못한다.
- 후속 구현 후보: Toxiproxy 기반 Redis delay profile.

## 10. LAT-005 External Dependency Slow Response Drill

- 목적: 외부 partner API 또는 callback API 지연이 내부 API latency로 보이는 상황을 재현한다.
- 재현 방법: mock partner service를 추가해 delay, timeout, 500, slow TTFB를 시뮬레이션한다.
- 구성 후보:
  - `GET /health`
  - `POST /callback`
  - `DELAY_MS` 환경변수 또는 query param으로 응답 지연
  - timeout, 500, slow TTFB 시뮬레이션
- 실행 후보 명령:
  - `make mock-partner-up`
  - `make latency-drill-external-slow`
  - `make k6-latency-external-slow`
  - `make latency-analyze`
- 기대되는 k6 결과:
  - API 응답 latency 증가 가능
  - timeout 비율 증가 가능
- 기대되는 서버 metric/log:
  - `external_http_client_duration_seconds` 증가
  - DB/Redis phase 정상
  - blackbox probe와 app outbound metric 비교 가능
- latency classification:
  - `external_dependency_latency`
  - `external_endpoint_slow`
  - `app_http_client_path_issue`
- 정합성 검증:
  - 원장 write path가 외부 callback과 분리되어 있다면 duplicate/reconciliation 0
  - 동기 외부 호출이 필수이면 timeout/circuit breaker 기준 기록
- 자동화 가능 범위: mock partner와 HTTP client wrapper 구현 후 가능.
- 수동 판단 필요 범위: 외부사 장애 확인, circuit breaker 적용 승인.
- Trade-off: mock partner는 현실 외부사 장애를 완전히 대체하지 않지만 반복 가능한 evidence를 만든다.
- 후속 구현 후보: mock partner compose service, outbound HTTP client wrapper.

## 11. LAT-006 Nginx Edge / Client Network Latency Drill

- 목적: k6에서 느리게 보이지만 FastAPI 내부는 정상인 경우 edge/client/network 구간을 분리한다.
- 재현 방법: Nginx `request_time`과 `upstream_response_time`을 비교한다.
- 필요한 Nginx log field:
  - `$request_time`
  - `$upstream_response_time`
  - `$upstream_connect_time`
  - `$upstream_header_time`
  - `$request_length`
  - `$bytes_sent`
  - `$request_id`
- 실행 후보 명령:
  - `make latency-drill-nginx-edge`
  - `make k6-latency-edge`
  - `make latency-analyze`
- 기대되는 k6 결과:
  - client-side latency 증가
- 기대되는 서버 metric/log:
  - Nginx request time 증가
  - Nginx upstream response time은 상대적으로 낮음
  - FastAPI handler time 정상
- latency classification: `edge_or_client_network_latency`
- 정합성 검증:
  - duplicate ledger 0
  - retry storm 발생 시 idempotency conflict 정책 확인
- 자동화 가능 범위: Nginx log format 확장 후 analyzer 가능.
- 수동 판단 필요 범위: partner network, k6 실행 환경, edge 설정 확인.
- Trade-off: local k6 환경의 network 지연은 실제 partner network와 다를 수 있다.
- 후속 구현 후보: Nginx timing log parser.

## 12. Latency Classification Matrix

| 테스트 결과 | 원인 후보 | Classification |
| --- | --- | --- |
| k6 p99 증가 + FastAPI phase 정상 + Nginx upstream 정상 | external client/network/k6 환경 문제 | `external_or_network_suspected` |
| k6 p99 증가 + Nginx upstream 증가 + FastAPI handler 증가 | 내부 API 처리 지연 | `internal_application_latency` |
| FastAPI handler 중 DB phase 증가 | PostgreSQL 병목 | `internal_postgres_latency` |
| FastAPI handler 중 Redis phase 증가 | Redis 지연/timeout | `redis_degraded_latency` |
| FastAPI handler 중 outbound HTTP phase 증가 | 외부 dependency 지연 | `external_dependency_latency` |
| 모든 route p95/p99 증가 | 내부 리소스 포화 | `internal_resource_saturation` |
| 특정 route만 증가 | endpoint별 병목 | `route_specific_bottleneck` |
| 특정 client/partner만 증가 | partner별 payload/retry/network 문제 | `partner_specific_latency` |
| blackbox probe도 증가 | 외부 endpoint 자체 지연 가능성 | `external_endpoint_slow` |
| blackbox probe 정상 + app outbound만 증가 | app HTTP client/DNS/pool 문제 | `app_http_client_path_issue` |

## 13. Makefile Target 후보

이번 PR에서는 실제 target을 구현하지 않는다.

```bash
make k6-latency-baseline
make latency-drill-db-pool
make latency-drill-db-lock
make latency-drill-redis-delay
make latency-drill-external-slow
make latency-drill-nginx-edge
make latency-analyze
make latency-report
```

## 14. Trade-off

### 14.1 k6 단독 판단 vs 서버 metric/log와 상관분석

- 선택한 정책: k6는 증상 재현에 사용하고, 원인 귀속은 server metric/log와 상관분석한다.
- 대안: k6 latency 결과만으로 원인을 판단한다.
- 선택 이유: k6는 내부 phase 지연을 직접 알 수 없다.
- 포기한 것: 테스트 결과 해석의 단순성.
- 보완 전략: k6 summary, Nginx timing, app phase metric, consistency SQL을 같은 report에 묶는다.
- 면접 답변용 한 문장: k6로 latency 증상을 만들고, 원인은 Nginx/FastAPI/DB/Redis metric을 함께 봐서 귀속하도록 설계했습니다.

### 14.2 실제 외부 시스템 호출 vs mock partner service

- 선택한 정책: 반복 가능한 drill은 mock partner service로 시작한다.
- 대안: 실제 외부 시스템 sandbox를 호출한다.
- 선택 이유: 외부 sandbox는 지연/timeout을 통제하기 어렵고 재현성이 낮다.
- 포기한 것: 실제 외부 네트워크와 완전히 같은 조건.
- 보완 전략: production-like 검증은 후속 통합 환경에서 별도 수행한다.
- 면접 답변용 한 문장: 외부 장애는 먼저 mock partner로 재현성을 확보하고, 실제 외부사는 통합 환경 evidence로 보완했습니다.

### 14.3 Redis down 테스트 vs Redis delay 테스트

- 선택한 정책: Redis down과 Redis delay를 분리한다.
- 대안: Redis down 테스트만 수행한다.
- 선택 이유: 실제 운영에서는 Redis가 완전히 죽기보다 느려지는 경우도 많다.
- 포기한 것: 장애 주입 단순성.
- 보완 전략: Toxiproxy 또는 netem 기반 delay profile을 후속 후보로 둔다.
- 면접 답변용 한 문장: Redis down은 fallback 검증이고, Redis delay는 tail latency 전파를 보기 위한 별도 drill로 분리했습니다.

### 14.4 DB down 테스트 vs DB lock/pool pressure 테스트

- 선택한 정책: DB down, pool pressure, lock contention을 분리한다.
- 대안: DB down만 장애로 다룬다.
- 선택 이유: DB가 살아 있어도 pool wait이나 lock wait 때문에 latency가 급증할 수 있다.
- 포기한 것: 시나리오 수의 단순성.
- 보완 전략: 각 시나리오별 classification과 evidence를 따로 둔다.
- 면접 답변용 한 문장: DB 장애를 down 하나로 보지 않고, pool pressure와 lock contention까지 분리해 latency 원인을 좁히도록 했습니다.

### 14.5 test-only fault injection vs 실제 장애만 재현

- 선택한 정책: 반복 가능한 fault injection을 사용하되 production path에 섞지 않는다.
- 대안: 실제 장애만 기다리거나 수동으로 재현한다.
- 선택 이유: drill은 반복 가능해야 하고 CI/로컬에서 evidence를 남길 수 있어야 한다.
- 포기한 것: 실제 장애와 완전히 같은 환경.
- 보완 전략: fault injection 범위와 한계를 report에 명시한다.
- 면접 답변용 한 문장: 장애 주입은 테스트 경계에 두고, production logic에는 넣지 않아 재현성과 안전성을 함께 잡았습니다.

### 14.6 phase metric 추가 vs full distributed tracing 도입

- 선택한 정책: phase metric과 structured log를 먼저 추가하고, tracing은 후속 확장으로 둔다.
- 대안: 처음부터 full distributed tracing을 도입한다.
- 선택 이유: 현재 프로젝트 범위에서는 metric/log 기반 원인 귀속이 더 작고 명확하다.
- 포기한 것: trace span 기반 시각화.
- 보완 전략: trace_id/request_id를 표준화해 OpenTelemetry 확장 가능성을 열어둔다.
- 면접 답변용 한 문장: 먼저 phase metric으로 병목 구간을 숫자로 나누고, 이후 OpenTelemetry로 end-to-end trace를 붙일 수 있게 설계했습니다.

## 15. 후속 구현 후보

- FastAPI middleware 기반 request phase timer
- SQLAlchemy DB query/pool wait timer
- Redis operation timer
- outbound HTTP client wrapper
- Nginx timing log format 확장
- Toxiproxy 기반 Redis delay profile
- controlled DB lock holder script
- mock partner service
- blackbox exporter 기반 external endpoint probe
- latency incident analyzer
- Grafana latency attribution dashboard
- k6 latency drill scenarios
- `reports/latency/{run_id}/latency-analysis.md` generator

## 16. 면접 답변용 요약

k6 하나로 DB나 외부 시스템이 원인이라고 단정하지 않았습니다.
k6는 latency 증상을 재현하는 도구로 쓰고, Nginx timing, FastAPI phase metric, Redis/PostgreSQL metric, external HTTP client metric, consistency SQL을 함께 비교해 `internal_postgres_latency`, `redis_degraded_latency`, `external_dependency_latency`, `edge_or_client_network_latency` 같은 원인 후보로 분류하도록 설계했습니다.
