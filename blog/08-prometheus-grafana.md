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
현재는 애플리케이션에서 기록하는 Redis lock/cache/fallback 결과 metric을 우선 확인하고, Redis exporter scrape는 Phase 11 이후 운영 관측 보강 항목으로 둡니다.

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

## 다음 편에서

9편에서는 Docker Compose로 장애 재현 환경을 구성합니다.
