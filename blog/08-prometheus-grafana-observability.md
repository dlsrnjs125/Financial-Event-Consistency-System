# 8편. Prometheus/Grafana로 거래 이벤트 처리 상태 관측하기

## 들어가며

테스트와 부하 테스트로 정합성을 검증했습니다.

이제 **운영 환경에서 실시간으로 모니터링**해야 합니다.

이 편에서는 Prometheus 메트릭과 Grafana 대시보드를 다룹니다.

현재 구현은 FastAPI 애플리케이션의 Prometheus custom metric과
`X-Trace-ID`/`X-Request-ID` 기반 구조화 로그 상관관계 추적을 중심으로 합니다.
W3C `traceparent`/`tracestate` 전파나 OpenTelemetry SDK 기반 분산 추적은 아직 구현 범위가 아니며,
후속 고도화 항목으로 남깁니다.

---

## Prometheus 메트릭

### API 메트릭
```
financial_http_requests_total{method, route, status_class}
financial_http_request_duration_seconds{method, route}
financial_http_errors_total{method, route, status_class}
```

### 도메인 메트릭
```
financial_transaction_events_total{event_type, status, result}
financial_transaction_processing_duration_seconds{event_type}
financial_duplicate_external_event_total{event_type}
financial_invalid_state_transition_total
financial_idempotency_decisions_total{decision, source}
financial_idempotency_conflict_total{source}
```

### DB 메트릭
```
db_connections_active
db_connections_idle
db_connection_wait_seconds
db_transaction_duration_seconds
db_deadlock_total
```

DB connection/lock/deadlock 같은 내부 지표는 PostgreSQL exporter 또는 SQLAlchemy pool gauge가 필요합니다.
현재는 FastAPI API 서버 metric과 도메인 metric을 우선 노출하고, PostgreSQL exporter는 후속 운영 관측 단계에서 추가합니다.

### Redis 메트릭
```
redis_up
redis_keyspace_hits_total
redis_keyspace_misses_total
redis_memory_used_bytes
redis_lock_acquire_failed_total
```

Redis 서버 내부 지표는 Redis exporter가 필요합니다.
현재는 애플리케이션에서 기록하는 Redis lock/cache/fallback 결과 metric을 우선 확인하고, Redis exporter scrape는 Phase 12 이후 운영 관측 보강 항목으로 둡니다.

Phase 10 이후 Redis fallback 관측에는 다음 애플리케이션 metric을 사용합니다.

```
financial_redis_operation_total{operation, result, reason}
financial_redis_operation_failed_total{operation, reason}
financial_redis_fallback_total{operation, reason}
financial_readiness_dependency_status{dependency}
```

---

## 구현 (Python + Prometheus Client)

```python
from prometheus_client import Counter, Histogram, Gauge

# Counter: 누적 개수
financial_events_received = Counter(
    'financial_events_received_total',
    'Total transaction events received'
)

financial_events_duplicate = Counter(
    'financial_events_duplicate_total',
    'Total duplicate transaction events detected'
)

invalid_state_transition = Counter(
    'financial_invalid_state_transition_total',
    'Total invalid state transitions attempted'
)

# Histogram: 시간 분포
request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

# Gauge: 현재값
db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections'
)
```

---

## Grafana 대시보드

### 1. API Overview
```
- Request Rate (req/sec)
- Response Time (p50, p95, p99)
- Error Rate (%)
- 4xx vs 5xx Errors
```

### 2. Transaction Consistency
```
- Events Received
- Events Processed
- Duplicate Events (목표: 0)
- Failed Events
- Invalid State Transitions (목표: 0)
- Idempotency Cache Hit Ratio
```

### 3. Database
```
- Active Connections
- Connection Wait Time
- Transaction Duration
- Deadlock Count (목표: 0)
```

### 4. Redis
```
- Up/Down Status
- Memory Usage
- Cache Hit Ratio
- Lock Acquisition Failure Rate
```

### 대시보드에서 확인할 운영 지표

- p95/p99 latency
- duplicate event count
- invalid state transition count
- idempotency hit ratio
- DB connection usage
- Redis cache hit ratio
- reconciliation failure count

---

## 알람 설정

```yaml
groups:
  - name: financial_events
    rules:
      - alert: DuplicateEventsDetected
        expr: rate(financial_events_duplicate_total[1m]) > 0
        for: 1m
        annotations:
          summary: "Duplicate events detected"
      
      - alert: InvalidStateTransition
        expr: rate(financial_invalid_state_transition_total[1m]) > 0
        for: 1m
        annotations:
          summary: "Invalid state transition attempted"
      
      - alert: DBConnectionPoolExhausted
        expr: db_connections_active > 90
        for: 1m
        annotations:
          summary: "Database connection pool nearly exhausted"
      
      - alert: RedisDown
        expr: redis_up == 0
        for: 30s
        annotations:
          summary: "Redis is down"
```

---

## 로그와 메트릭을 분리한 이유

처음에는 장애 분석에 필요한 값을 metric label에 넣고 싶어질 수 있다. 예를 들어 `event_id`, `idempotency_key`, `trace_id`를 label로 넣으면 Grafana에서 바로 필터링할 수 있어 보인다. 하지만 이 값들은 요청마다 달라지는 고유값이다. Prometheus label에 넣으면 series cardinality가 폭증하고, 모니터링 시스템 자체가 병목이 될 수 있다.

그래서 기준을 이렇게 나눴다.

| 구분 | 넣는 값 | 넣지 않는 값 |
|---|---|---|
| Metric | operation, dependency, result, reason 같은 bounded label | trace_id, event_id, idempotency_key |
| Log | trace_id, request_id, event_id, masked idempotency_key | raw account_no, raw key, signature |
| Dashboard | rate, latency, fallback count, readiness state | 개별 요청 고유값 |

Redis 관련 metric도 같은 원칙으로 정리했다. lock을 못 잡은 상황은 장애가 아니라 중복 요청을 막은 결과일 수 있다. 따라서 Redis connection error/timeout은 `failure/fallback`, lock 미획득은 `rejected/lock_not_acquired`, cache miss는 별도 cache result로 분리했다.

이렇게 나누면 대시보드는 "어떤 종류의 문제가 늘었는지"를 보여주고, 구조화 로그는 "그 요청 하나가 어떤 경로로 처리됐는지"를 추적하는 역할을 맡는다.

## 개발 중 바뀐 관측 기준

관측성 작업을 시작할 때는 "많이 기록하면 나중에 도움이 되지 않을까"라는 유혹이 있었다. 하지만 금융 이벤트 시스템에서는 로그와 메트릭이 많아지는 것보다, 각 신호가 무엇을 의미하는지 분리되는 것이 더 중요했다. 특히 Redis 장애 대응을 구현하면서 이 기준이 명확해졌다.

Redis lock을 얻지 못한 상황은 처음 보기에는 실패처럼 보인다. 하지만 duplicate storm에서는 동일한 idempotency key가 동시에 들어오기 때문에 lock 미획득은 정상적인 중복 요청 방어 결과다. 이것을 `failure`로 기록하면 Grafana에서는 Redis 장애처럼 보이고, 운영자는 실제 장애가 아닌 정상 방어 동작에 반응하게 된다. 그래서 lock 미획득은 `rejected`, 이유는 `lock_not_acquired`로 분리했다.

cache miss도 같은 문제였다. Redis에 정상적으로 질의했지만 값이 없는 경우는 장애가 아니다. idempotency 응답이 아직 cache에 없거나 TTL이 만료된 상태일 수 있다. 그래서 cache get 자체는 `success`, 결과는 `miss`로 해석하도록 나눴다. 반대로 connection error나 timeout은 Redis dependency failure이고, 이 경우에만 fallback metric을 증가시킨다.

이 구분 덕분에 Redis Down duplicate storm을 볼 때도 "Redis가 죽어서 fallback이 발생했다"와 "동일 key 요청이 몰려 lock이 거절됐다"를 따로 볼 수 있다. 두 상황은 대응이 다르다. 전자는 Redis 복구와 fallback 안정성 확인이 필요하고, 후자는 client retry 정책이나 idempotency key 사용 패턴을 봐야 한다.

## 검증 방법

관측성은 화면을 만든다고 끝나지 않는다. 실제 장애 조건을 만들고 metric과 로그가 의도한 의미로 찍히는지 확인해야 했다.

```bash
make local-bg
make failure-redis-down
make k6-redis-down-duplicate-storm
make failure-redis-up
```

Redis를 내린 상태에서 duplicate storm을 실행하면 API는 PostgreSQL 기준 degraded mode로 처리한다. 이때 확인할 것은 단순히 요청이 성공했는지가 아니라, 다음 신호가 서로 맞는지다.

- `/ready`는 PostgreSQL이 정상일 때 `ready` 또는 degraded mode를 유지한다.
- Redis fallback metric은 증가한다.
- lock rejected와 Redis failure는 서로 다른 result/reason으로 기록된다.
- 구조화 로그에는 `trace_id`, `request_id`, `event_id`, masked idempotency key가 남는다.
- Prometheus label에는 `event_id`, `idempotency_key`, `trace_id` 같은 고유값이 들어가지 않는다.

## 남은 한계

현재 구현은 애플리케이션 레벨 custom metric과 구조화 로그에 초점을 둔다. Redis exporter, PostgreSQL exporter, `api-green` scrape target, Nginx upstream별 5xx 관측은 운영 관측을 더 세밀하게 만들기 위한 후속 보강 항목이다. 다만 핵심 기준은 이미 정리했다. 집계가 필요한 값은 metric으로, 개별 요청 추적이 필요한 값은 log로 남긴다.
