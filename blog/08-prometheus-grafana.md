# 8편. Prometheus/Grafana로 거래 이벤트 처리 상태 관측하기

## 들어가며

테스트와 부하 테스트로 정합성을 검증했습니다.

이제 **운영 환경에서 실시간으로 모니터링**해야 합니다.

이 편에서는 Prometheus 메트릭과 Grafana 대시보드를 다룹니다.

---

## Prometheus 메트릭

### API 메트릭
```
http_requests_total{method, endpoint, status}
http_request_duration_seconds{method, endpoint}
http_requests_failed_total{method, endpoint}
```

### 도메인 메트릭
```
transaction_events_received_total
transaction_events_processed_total
transaction_events_duplicated_total
transaction_events_failed_total
invalid_state_transition_total
idempotency_hit_total
idempotency_miss_total
```

### DB 메트릭
```
db_connections_active
db_connections_idle
db_connection_wait_seconds
db_transaction_duration_seconds
db_deadlock_total
```

### Redis 메트릭
```
redis_up
redis_keyspace_hits_total
redis_keyspace_misses_total
redis_memory_used_bytes
redis_lock_acquire_failed_total
```

---

## 구현 (Python + Prometheus Client)

```python
from prometheus_client import Counter, Histogram, Gauge

# Counter: 누적 개수
transaction_events_received = Counter(
    'transaction_events_received_total',
    'Total transaction events received'
)

transaction_events_duplicated = Counter(
    'transaction_events_duplicated_total',
    'Total duplicate transaction events detected'
)

invalid_state_transition = Counter(
    'invalid_state_transition_total',
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

---

## 알람 설정

```yaml
groups:
  - name: financial_events
    rules:
      - alert: DuplicateEventsDetected
        expr: rate(transaction_events_duplicated_total[1m]) > 0
        for: 1m
        annotations:
          summary: "Duplicate events detected"
      
      - alert: InvalidStateTransition
        expr: rate(invalid_state_transition_total[1m]) > 0
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
