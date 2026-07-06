# Latency Attribution and External Dependency Diagnosis

> "API가 느리다"는 하나의 원인이 아니다.
> 운영자가 먼저 해야 할 일은 장애 원인을 단정하는 것이 아니라, 지연의 책임 구간을 좁히는 것이다.

## 1. 문제 정의

외부 금융 시스템이 "이벤트를 보냈는데 응답이 너무 늦다"고 신고했을 때 p95/p99만 보면 충분하지 않다.
같은 latency라도 원인은 Nginx edge, FastAPI 내부 처리, Redis timeout, PostgreSQL lock, 외부 partner API, client network, retry 설정 중 하나일 수 있다.

확인해야 하는 질문:

- 요청이 우리 Nginx까지 늦게 도착했는가?
- Nginx에서 FastAPI upstream으로 넘기는 데 지연이 있었는가?
- FastAPI 내부 handler 시간이 긴가?
- HMAC 검증, validation, idempotency lookup, Redis, PostgreSQL 중 어디가 느린가?
- PostgreSQL lock, pool, query 문제가 있는가?
- Redis timeout/fallback 때문에 느린가?
- 응답은 빨리 만들었지만 외부 시스템이 늦게 받은 것인가?
- 외부 시스템의 network, TLS, retry, timeout 설정 문제인가?
- 특정 partner/client만 느린가, 전체 API가 느린가?

## 2. 왜 latency attribution이 필요한가

금융 이벤트 처리 시스템에서 timeout은 재시도와 duplicate request를 만든다.
따라서 latency 문제는 단순 성능 문제가 아니라 idempotency, retry storm, DB pressure, 외부 계약 문제로 이어질 수 있다.

Latency attribution의 목표:

- 내부 장애와 외부/네트워크 문제를 분리한다.
- PostgreSQL, Redis, app logic, Nginx, outbound dependency 중 병목 구간을 좁힌다.
- 외부 partner와 같은 request id 기준으로 evidence를 대조한다.
- incident analyzer가 rule 기반으로 1차 분류할 수 있게 한다.
- 민감정보 없이 latency evidence를 남긴다.

## 3. Inbound latency와 Outbound latency 구분

### Inbound

```text
External Financial System
-> Nginx
-> FastAPI
-> Redis/PostgreSQL
-> response
```

Inbound에서는 외부 시스템이 체감한 latency와 우리 Nginx/FastAPI가 측정한 latency가 다를 수 있다.
외부 total latency가 높더라도 Nginx request time과 FastAPI handler time이 정상이라면 partner network, client timeout/retry, response receive path를 의심해야 한다.

### Outbound

```text
Financial Event System
-> external partner API or callback API
```

Outbound에서는 우리 내부 처리 자체는 정상인데 외부 API 응답 지연 때문에 전체 요청이 느려질 수 있다.
금융 확정 처리와 직접 관련 없는 outbound call은 core write path와 분리하거나 timeout/circuit breaker 후보로 관리한다.

## 4. 전체 요청 latency 구간 분해

개념적 분해:

```text
external_client_total_latency
= external_network_to_edge
+ nginx_wait_or_proxy_time
+ app_request_queue_time
+ auth_hmac_validation_time
+ idempotency_lookup_time
+ redis_operation_time
+ postgres_transaction_time
+ business_logic_time
+ response_write_time
+ network_back_to_client
```

모든 구간을 완벽하게 측정할 수 있다고 가정하지 않는다.
측정 가능한 구간과 외부 시스템 협조가 필요한 구간을 분리한다.

| 구간 | 측정 가능 여부 | 측정 위치 | 의미 |
| --- | --- | --- | --- |
| Partner total latency | 제한적 | 외부 시스템 timestamp 필요 | 외부가 체감한 전체 시간 |
| Nginx request time | 가능 | Nginx access log | Nginx가 본 전체 요청 시간 |
| Nginx upstream response time | 가능 | Nginx access log | upstream FastAPI 응답 시간 |
| FastAPI total handler time | 가능 | app middleware metric/log | 애플리케이션 처리 시간 |
| HMAC validation time | 가능 | app internal timer | 인증/검증 비용 |
| Redis operation time | 가능 | app metric/log | Redis lock/cache/fallback 지연 |
| DB pool wait time | 후속 보완 | app/SQLAlchemy instrumentation | connection 획득 지연 |
| DB query/transaction time | 가능/후속 보완 | app timer 또는 DB exporter | query/lock/transaction 지연 |
| Outbound external API time | 가능 | HTTP client instrumentation | 우리 시스템이 외부 API를 부른 경우의 지연 |
| Client receive latency | 직접 측정 불가 | partner timestamp 필요 | 응답 후 네트워크/외부 처리 지연 |

OpenTelemetry는 후속 구현 후보로 둔다.
HTTP server/client span을 도입하면 서비스 내부 처리와 외부 호출 구간을 같은 trace에서 연결할 수 있다.

## 5. 내부 문제 vs 외부 문제 판단 Matrix

| 관측 결과 | 가능성 높은 원인 | 판단 근거 | 자동 조치 | 수동 확인 |
| --- | --- | --- | --- | --- |
| Partner는 느리다고 하지만 FastAPI handler time은 정상 | 외부 네트워크, partner client timeout/retry 문제 | 우리 내부 처리 시간은 정상 | partner evidence bundle 생성 | partner timestamp 요청 |
| Nginx request time은 높고 upstream response time은 낮음 | client upload 지연, network, Nginx edge 구간 | upstream은 빨리 응답 | Nginx access log bundle 생성 | partner network 확인 |
| Nginx upstream response time과 FastAPI handler time이 모두 높음 | 내부 app 처리 지연 | app 자체 처리 시간 증가 | incident analyzer 실행 | 어떤 phase가 느린지 확인 |
| FastAPI handler time 중 PostgreSQL 구간이 높음 | PostgreSQL pool/query/lock 문제 | DB 구간 지연 증가 | DB pressure rule 연결 | lock/query 분석 |
| FastAPI handler time 중 Redis 구간이 높음 | Redis timeout/fallback 문제 | Redis 지연 또는 down | Redis degraded mode 판단 | Redis 복구 |
| FastAPI handler time 중 outbound external API 구간이 높음 | 외부 dependency 지연 | 외부 API 호출 구간이 대부분 | circuit breaker 후보 기록 | 외부사 장애 확인 |
| 모든 route의 p95/p99가 상승 | 내부 리소스 포화 가능성 | route 전반 지연 | global incident 생성 | CPU/DB/network 확인 |
| 특정 route만 지연 | route-specific bottleneck | endpoint 단위 지연 | route runbook 연결 | query/logic 확인 |
| 특정 client/partner만 지연 | partner 요청 패턴/네트워크/페이로드 문제 | client별 편차 | client-level evidence 생성 | partner 계약 확인 |
| blackbox probe도 느림 | 외부 endpoint 또는 네트워크 문제 | probe 지연 | external dependency incident | 외부사 확인 |
| blackbox probe는 정상인데 app outbound call만 느림 | app HTTP client pool/DNS/TLS 설정 문제 | probe와 app 지표 불일치 | app client 설정 점검 | pool/DNS/TLS 확인 |

## 6. 수집해야 할 metrics

Metric 후보:

| Metric | 주요 label | 용도 |
| --- | --- | --- |
| `http_server_request_duration_seconds` | `route_group`, `method`, `status_code`, `result` | FastAPI server latency |
| `nginx_request_duration_seconds` | `route_group`, `status_code` | Nginx가 본 전체 요청 시간 |
| `nginx_upstream_duration_seconds` | `upstream`, `route_group`, `status_code` | upstream 응답 시간 |
| `app_phase_duration_seconds` | `phase`, `route_group`, `result` | app 내부 phase별 latency |
| `db_pool_wait_duration_seconds` | `route_group`, `result` | DB connection 획득 지연 |
| `db_transaction_duration_seconds` | `operation`, `result` | DB transaction/query 지연 |
| `redis_operation_duration_seconds` | `operation`, `result` | Redis lock/cache 지연 |
| `external_http_client_duration_seconds` | `partner_alias`, `endpoint_group`, `method`, `result` | outbound HTTP 지연 |
| `external_dependency_probe_duration_seconds` | `partner_alias`, `probe_type`, `result` | 외부 endpoint probe 지연 |

허용 label:

- `route_group`
- `endpoint_group`
- `partner_alias`
- `method`
- `status_code`
- `result`
- `phase`
- `operation`

금지 label:

- `account_id`
- `event_id`
- `idempotency_key`
- raw URL
- raw account number
- customer identifier
- raw external_event_id

Prometheus label에는 high-cardinality 값과 개인정보를 넣지 않는다.
partner도 원문 client id가 아니라 제한된 enum 형태의 `partner_alias`를 사용한다.

## 7. 구조화 로그 필드

공통 필드:

- `trace_id`
- `request_id`
- `partner_request_id`
- `direction`: `inbound` 또는 `outbound`
- `client_alias` 또는 `partner_alias`
- `route_group`
- `endpoint_group`
- `total_duration_ms`
- `phase_durations_ms`
- `timeout_ms`
- `retry_count`
- `latency_classification`
- `sensitive_data_included`

Inbound 예시:

```json
{
  "timestamp": "2026-07-06T23:10:00+09:00",
  "level": "INFO",
  "trace_id": "trc_xxx",
  "request_id": "req_xxx",
  "partner_request_id": "prt_req_xxx",
  "direction": "inbound",
  "client_alias": "partner_a",
  "route_group": "transaction_events",
  "http_status": 201,
  "total_duration_ms": 142,
  "phase_durations_ms": {
    "hmac_validation": 3,
    "idempotency_lookup": 12,
    "redis": 8,
    "postgres": 91,
    "business_logic": 19,
    "response_build": 2
  },
  "latency_classification": "internal_postgres_latency",
  "retryable": false,
  "sensitive_data_included": false
}
```

Outbound 예시:

```json
{
  "timestamp": "2026-07-06T23:11:00+09:00",
  "level": "WARN",
  "trace_id": "trc_xxx",
  "request_id": "req_xxx",
  "direction": "outbound",
  "partner_alias": "settlement_partner_a",
  "endpoint_group": "settlement_status_callback",
  "method": "POST",
  "timeout_ms": 3000,
  "duration_ms": 2850,
  "retry_count": 1,
  "result": "timeout_near_miss",
  "dns_ms": 12,
  "tcp_connect_ms": 30,
  "tls_ms": 42,
  "ttfb_ms": 2700,
  "response_read_ms": 20,
  "latency_classification": "external_dependency_slow_ttfb",
  "sensitive_data_included": false
}
```

`latency_classification` 후보:

- `internal_postgres_latency`
- `redis_degraded_latency`
- `external_dependency_latency`
- `edge_or_client_network_latency`
- `partner_specific_latency`
- `app_http_client_path_issue`
- `unknown_latency`

## 8. 외부 시스템과의 관측 계약

Inbound 요청에서 외부 시스템이 보내면 좋은 header:

- `X-Partner-Request-Id`
- `X-Partner-Sent-At`
- `Idempotency-Key`
- `X-Signature`
- `X-Signature-Timestamp`

우리 응답 header 후보:

- `X-Request-Id`
- `X-Idempotency-Result`
- `Retry-After`
- `X-Server-Processing-Ms`

`X-Server-Processing-Ms`는 총 server-side processing time 정도만 제공한다.
DB, Redis, validation 등 내부 상세 병목은 외부 header로 노출하지 않고 internal incident evidence에만 남긴다.

Outbound 외부 API 호출에서 남길 값:

- `partner_alias`
- `endpoint_group`
- `timeout_ms`
- `duration_ms`
- `connect_ms`
- `tls_ms`
- `ttfb_ms`
- `response_status`
- `retry_count`
- `final_result`
- `circuit_state`

외부 timestamp는 clock skew, timezone, retry 구현 차이 때문에 참고 신호로만 사용한다.
책임 구간 판단은 Nginx와 application timestamp를 우선하고, `X-Partner-Request-Id`로 양쪽 로그를 대조한다.

## 9. Incident Analyzer rule 확장

| Rule | 조건 | 분류 | Severity | 자동 조치 | 수동 확인 |
| --- | --- | --- | --- | --- | --- |
| LAT-001 | app handler p95 정상 + partner reported latency 높음 | `external_or_network_suspected` | SEV3/SEV2 | partner evidence bundle 생성 | partner timestamp 대조 |
| LAT-002 | nginx request time 높음 + upstream response time 낮음 | `edge_or_client_network_latency` | SEV2 | Nginx log bundle 생성 | network 확인 |
| LAT-003 | app total high + DB phase high | `internal_postgres_latency` | SEV1/SEV2 | DB pressure analyzer 연결 | lock/query 분석 |
| LAT-004 | app total high + Redis phase high | `redis_degraded_latency` | SEV2 | Redis degraded mode 확인 | Redis 복구 |
| LAT-005 | app total high + outbound external HTTP high | `external_dependency_latency` | SEV2 | circuit breaker 후보 기록 | 외부사 장애 확인 |
| LAT-006 | all routes high | `internal_resource_saturation` | SEV1/SEV2 | global incident 생성 | CPU/DB/pool 확인 |
| LAT-007 | one client only high | `partner_specific_latency` | SEV3/SEV2 | client evidence 생성 | partner 계약 확인 |
| LAT-008 | blackbox probe high + app outbound high | `external_endpoint_slow` | SEV2 | external dependency incident 생성 | 외부사 확인 |
| LAT-009 | blackbox probe normal + app outbound high | `app_http_client_path_issue` | SEV2 | app client config 점검 | pool/DNS/TLS 확인 |

## 10. Trade-off

### 10.1 Metrics/Logs만 사용할 것인가, Trace까지 도입할 것인가

- 선택한 정책: 1차는 metrics + structured logs, 후속으로 OpenTelemetry trace 도입.
- 대안: 처음부터 full distributed tracing 도입.
- 선택 이유: 현재 프로젝트는 Docker Compose 기반 포트폴리오이므로 구현 범위를 과도하게 키우지 않기 위함.
- 포기한 것: 요청 단위의 end-to-end span visualization.
- 보완 전략: trace_id/request_id를 먼저 표준화하고, 나중에 OTel Collector/Tempo/Loki로 확장.
- 면접 답변용 한 문장: 처음부터 tracing stack을 붙이기보다, 먼저 phase latency를 구조화 로그와 Prometheus metric으로 분해하고 trace_id를 표준화해 OpenTelemetry 확장 가능성을 열어뒀습니다.

### 10.2 외부 시스템 timestamp를 신뢰할 것인가

- 선택한 정책: 외부 timestamp는 참고 신호로만 사용한다.
- 대안: 외부 timestamp를 기준으로 latency를 계산한다.
- 선택 이유: 외부 시스템 clock skew, timezone, retry 구현 차이로 인해 신뢰하기 어렵다.
- 포기한 것: 외부 체감 latency의 완전한 자동 판단.
- 보완 전략: `X-Partner-Request-Id`로 상호 로그 대조, NTP/clock skew 기준 명시.
- 면접 답변용 한 문장: 외부 timestamp는 장애 분석의 보조 근거로만 쓰고, 우리 시스템의 책임 구간은 Nginx와 application timestamp 기준으로 판단했습니다.

### 10.3 상세 server timing을 외부에 노출할 것인가

- 선택한 정책: `X-Server-Processing-Ms`처럼 제한된 정보만 노출한다.
- 대안: DB/Redis/validation별 상세 시간을 header로 노출한다.
- 선택 이유: 외부 협업에는 유용하지만 내부 구조와 병목 정보가 과도하게 노출될 수 있다.
- 포기한 것: 외부사가 직접 세부 병목을 판단하는 편의성.
- 보완 전략: 내부 상세 phase breakdown은 incident report로만 관리한다.
- 면접 답변용 한 문장: 외부에는 총 server processing time만 제공하고, DB/Redis 같은 내부 세부 구간은 보안상 내부 incident evidence로만 남겼습니다.

### 10.4 Blackbox Probe vs Application Client Metric

- 선택한 정책: 둘 다 사용하되 목적을 분리한다.
- 대안: application metric만 사용한다.
- 선택 이유: app client metric은 실제 요청 지연을 보여주지만, app 내부 pool/DNS/TLS 문제와 외부 endpoint 자체 문제를 분리하기 어렵다.
- 포기한 것: probe 관리 비용 증가.
- 보완 전략: 핵심 외부 endpoint만 probe 대상에 포함한다.
- 면접 답변용 한 문장: 외부 API 지연은 app client metric과 blackbox probe를 함께 비교해, 외부 endpoint 자체 문제인지 우리 app client 경로 문제인지 분리했습니다.

### 10.5 외부 지연 시 동기 대기 vs Circuit Breaker

- 선택한 정책: 금융 확정 처리와 직접 관련 없는 outbound call은 timeout + circuit breaker 후보로 관리한다.
- 대안: 외부 응답이 올 때까지 동기 대기한다.
- 선택 이유: 외부 dependency 지연이 내부 write path 전체를 막으면 장애가 전파된다.
- 포기한 것: 즉시 외부 동기 완료 보장.
- 보완 전략: 후속 queue/outbox 패턴 ADR에서 비동기 전환 후보 검토.
- 면접 답변용 한 문장: 외부 시스템 지연이 내부 정합성 처리까지 전파되지 않도록, 핵심 write path와 부가 outbound dependency를 분리하는 방향으로 설계했습니다.

### 10.6 per-partner metric label vs high-cardinality 위험

- 선택한 정책: 제한된 enum 형태의 `partner_alias`만 label로 허용한다.
- 대안: client id, account id, raw partner id를 label로 사용한다.
- 선택 이유: high-cardinality는 Prometheus 비용과 장애 가능성을 키우고, 개인정보 노출 위험도 만든다.
- 포기한 것: metric만으로 개별 고객/계좌 단위 분석하는 편의성.
- 보완 전략: 상세 분석은 sanitized structured log와 incident artifact에서 수행한다.
- 면접 답변용 한 문장: Prometheus label은 제한된 alias로만 관리하고, 고유 식별자 분석은 sanitized log evidence로 분리했습니다.

### 10.7 full request/response logging vs sanitized structured logging

- 선택한 정책: full request/response body를 남기지 않고 sanitized structured logging을 사용한다.
- 대안: 장애 분석 편의를 위해 raw payload를 저장한다.
- 선택 이유: 금융 데이터, signature, account number가 log artifact에 남으면 보안 사고가 된다.
- 포기한 것: payload 원문 기반의 빠른 디버깅.
- 보완 전략: request_hash, masked/tokenized identifier, schema validation error code, trace_id로 대체한다.
- 면접 답변용 한 문장: 장애 분석보다 민감정보 보호가 우선이므로 raw payload 대신 구조화된 sanitized evidence만 남기도록 설계했습니다.

## 11. 후속 구현 후보

이번 PR에서는 구현하지 않는다.
후속 구현 후보:

- FastAPI middleware 기반 request phase timer
- SQLAlchemy DB query/pool wait timer
- Redis operation timer
- outbound HTTP client wrapper
- Nginx log format 확장
- blackbox exporter 기반 external endpoint probe
- latency incident analyzer
- Grafana latency attribution dashboard
- k6 latency drill scenario

구현하지 않은 항목은 완료된 것처럼 쓰지 않는다.
구체적인 k6 latency drill 시나리오와 evidence 저장 구조는 [42-latency-drill-test-plan.md](42-latency-drill-test-plan.md)에서 관리한다.

## 12. 면접 답변용 요약

단순히 p95/p99가 높다고 내부 장애로 단정하지 않고, Nginx request time, upstream response time, FastAPI phase duration, DB/Redis duration, outbound external call duration, blackbox probe를 함께 비교해 내부 병목인지 외부 dependency 문제인지 구간별로 분리하도록 설계했습니다.
