# API p99가 느려졌을 때 코드 문제인지 DB 문제인지 어떻게 구분할까?

p99가 튀었다는 말만으로는 아무것도 고칠 수 없다. FastAPI handler가 느린 것인지, PostgreSQL transaction이 밀린 것인지, Redis fallback이 늘어난 것인지, Nginx edge에서 지연이 생긴 것인지 분리해야 한다.

이 글은 "모니터링을 붙였다"가 아니라, 금융 이벤트 정합성 시스템에서 latency와 consistency evidence를 어떻게 함께 보게 만들었는지를 정리한다.

## p99가 높다는 말만으로는 아무것도 고칠 수 없었다

k6 결과에서 p99가 상승하면 가장 쉬운 결론은 "DB가 느리다"다. 하지만 실제로는 다음 후보가 모두 가능하다.

- Nginx request buffering 또는 upstream connection 문제
- FastAPI handler 내부 validation 또는 idempotency 판단 지연
- PostgreSQL lock, transaction, query 지연
- Redis lock/cache 실패 후 DB fallback 증가
- 외부 dependency 또는 client network path 지연
- latency는 낮지만 duplicate ledger count가 깨지는 정합성 문제

그래서 application metric과 infrastructure metric을 같은 방향으로 읽을 수 있어야 했다.

## HTTP latency와 정합성 counter를 같이 남긴 이유

처음부터 OpenTelemetry full tracing이나 Loki 로그 파이프라인을 붙이지 않았다. 범위를 FastAPI custom Prometheus metric과 request id 기반 로그 상관관계로 제한했다.

핵심 metric은 다음과 같다.

```text
financial_http_requests_total{method, route, status_class}
financial_http_request_duration_seconds{method, route}
financial_transaction_events_total{event_type, status, result}
financial_duplicate_external_event_total{event_type}
financial_idempotency_decisions_total{decision, source}
financial_redis_fallback_total{operation, reason}
financial_readiness_dependency_status{dependency}
```

각 metric의 역할은 다르다.

| Metric | 보고 싶은 것 |
| --- | --- |
| `financial_http_requests_total` | status class별 요청 증가와 5xx 여부 |
| `financial_http_request_duration_seconds` | API route별 latency 분포 |
| `financial_transaction_events_total` | event type/status/result 흐름 |
| `financial_duplicate_external_event_total` | 중복 이벤트 방어가 실제로 발생했는지 |
| `financial_idempotency_decisions_total` | STARTED, REPLAY, CONFLICT 같은 판단 분포 |
| `financial_redis_fallback_total` | Redis 장애나 timeout으로 DB fallback이 증가했는지 |
| `financial_readiness_dependency_status` | PostgreSQL/Redis dependency 상태 |

## 애플리케이션 metric에서 인프라 metric으로 확장한 이유

HTTP p99만으로는 API, DB, Redis, host, container, Nginx 중 어디가 병목인지 구분하기 어렵다.

초기 구현은 FastAPI custom metric에 집중했다. 이후 운영 검증에서는 node-exporter, cAdvisor, postgres-exporter, redis-exporter, Grafana dashboard를 붙여 host, container, DB, Redis, gateway 계층까지 관측 범위를 넓혔다.

app metric은 도메인 판단을 보여준다. 예를 들어 idempotency decision, duplicate event, Redis fallback, readiness dependency status는 금융 이벤트 처리 의미를 설명한다. infra exporter는 CPU, memory, connection, lock, command latency처럼 병목 후보를 좁히는 데 필요하다.

다만 Prometheus label에는 `external_event_id`, `account_no`, `idempotency_key`, `trace_id` 같은 high-cardinality 또는 민감 식별자를 넣지 않는다. 관측성을 높인다는 이유로 metric storage를 민감정보 저장소로 만들면 안 된다.

## Nginx, FastAPI, PostgreSQL, Redis를 차례로 좁히는 법

p99가 튀면 다음 순서로 좁힌다.

1. k6 p99와 error rate가 상승했는가
2. Nginx `request_time`과 `upstream_time`이 같이 상승했는가
3. FastAPI handler duration이 상승했는가
4. PostgreSQL transaction/query 지연 후보가 있는가
5. Redis fallback count가 증가했는가
6. duplicate event/ledger 같은 consistency counter가 깨졌는가

예를 들어 Nginx `request_time`은 높지만 `upstream_time`이 낮고 FastAPI handler도 정상이라면 application 내부보다 edge/client path를 먼저 의심한다.

반대로 `upstream_time`, FastAPI handler, PostgreSQL phase가 함께 상승하면 DB transaction이나 pool 후보가 된다.

## HTTP latency만으로는 금융 장애를 설명할 수 없었다

처음에는 `/metrics`에 HTTP latency만 있으면 충분하다고 생각했다. 하지만 금융 이벤트 시스템에서는 "느린 요청"과 "정합성 위험"을 같이 봐야 했다.

그래서 duplicate event, idempotency decision, Redis fallback, readiness dependency 상태를 별도 metric으로 분리했다.

이렇게 해야 다음 두 상황을 다르게 해석할 수 있다.

```text
p99 high
duplicate ledger 0
redis fallback high
=> 가용성/성능 저하, 정합성 방어선은 유지
```

```text
p99 normal
duplicate ledger > 0
=> 성능 문제가 아니라 consistency incident
```

## trace_id는 남기고 raw identifier는 남기지 않았다

metric만으로 개별 요청을 따라가기는 어렵다. 그래서 API 응답과 구조화 로그에는 `trace_id`, `request_id`, masked identifier를 남기되 raw account number나 full idempotency key는 남기지 않았다.

관측성은 더 많이 기록하는 것이 아니라, 장애 분석에 필요한 단서를 민감정보 없이 남기는 작업이었다.

## 이후 운영 관측으로 확장한 것

초기 범위에서는 FastAPI custom metric에 집중했다. 이후 운영 검증에서는 다음 계층을 추가로 관측 대상으로 확장했다.

- node-exporter: host CPU, memory, disk
- cAdvisor: container CPU, memory
- postgres-exporter: connection, lock, transaction
- redis-exporter: memory, clients, command latency
- Grafana dashboard: API, Infra, PostgreSQL, Redis, Nginx 관측

다만 여전히 후속 범위로 남긴 것도 있다.

- OpenTelemetry full distributed tracing
- Loki 기반 log query pipeline
- 장기 metric retention
- 운영 traffic 기준 alert threshold tuning

이들은 구현 부족이 아니라 범위 경계다. 현재 단계에서는 p99 상승을 HTTP metric 하나로 단정하지 않고, 계층별 evidence로 좁히는 기준을 먼저 고정했다.

## 남은 한계

local Docker Compose metric은 운영 시스템의 cardinality, 네트워크 지연, connection pool pressure를 그대로 재현하지 못한다.

그래도 이 구조는 p99 상승을 바로 DB 탓으로 단정하지 않고, Nginx, FastAPI, PostgreSQL, Redis fallback, consistency counter를 차례로 좁히는 기준을 제공한다.
