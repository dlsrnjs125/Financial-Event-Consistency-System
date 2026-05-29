# Ops Phase 1 - Infra Metrics Extension

## 1. 해결하려는 운영 문제

기존 `/metrics` 중심의 애플리케이션 metric만으로는 장애 원인이 API 로직인지,
DB connection 고갈인지, Redis 장애인지, 서버 리소스 부족인지 구분하기 어렵다.

Ops Phase 1은 관측 범위를 API에서 Linux host, container, PostgreSQL, Redis, Nginx 계층으로 확장한다.

## 2. 구현 범위

추가 exporter:

- node-exporter
- cAdvisor
- postgres-exporter
- redis-exporter
- nginx-prometheus-exporter

Dashboard:

- API dashboard
- Infra dashboard
- PostgreSQL dashboard
- Redis dashboard
- Nginx dashboard

Alert Rule:

- API p99 latency
- Redis down but API alive
- PostgreSQL connection pressure
- Nginx 5xx spike
- disk pressure
- financial consistency violation

## 3. 제외 범위

- Cloud provider managed monitoring은 제외한다.
- exporter 인증/TLS 구성은 초기 로컬 설계 범위에서 제외한다.
- 장기 metric retention과 remote write는 제외한다.
- OpenTelemetry metric exporter는 Prometheus custom metric과 혼동하지 않도록 제외한다.

## 4. 파일/디렉터리 변경 계획

```text
infra/
  monitoring/
    prometheus/
      prometheus.yml
      alert-rules.yml
      recording-rules.yml
    grafana/
      provisioning/
        datasources/
          datasource.yml
        dashboards/
          dashboard.yml
      dashboards/
        api-dashboard.json
        infra-dashboard.json
        postgres-dashboard.json
        redis-dashboard.json
        nginx-dashboard.json

docker-compose.monitoring.yml

scripts/
  monitoring/
    check-prometheus-targets.sh
    check-grafana-dashboards.sh
    check-alert-rules.sh
```

## 5. 검증 명령어

```bash
make infra-up
make metrics-check
make alert-rule-check
make dashboard-check
```

성공 기준:

- Prometheus target 중 down 상태가 0개
- api, node-exporter, cadvisor, postgres-exporter, redis-exporter, nginx-exporter target 존재
- 필수 metric key가 Prometheus API에서 조회됨
- alert rule syntax 검증 통과
- Grafana dashboard 5개 provision 확인

실패 기준:

- target down 1개 이상
- 필수 metric key 누락
- Prometheus API 호출 실패
- dashboard provision 누락

## 6. 완료 기준과 README에 남길 결과

### Cardinality 정책

Prometheus label에는 다음 값을 넣지 않는다.

- account_no
- raw idempotency_key
- raw external_event_id
- event_id
- request_id
- 동적 ID가 포함된 request path

고유 요청 추적은 metric label이 아니라 구조화 로그와 trace/request context에서 처리한다.

### Prometheus Target

| Target | Port | 목적 | 실패 시 의미 |
|---|---:|---|---|
| api | 8000 | FastAPI custom metric | 애플리케이션 metric 수집 실패 |
| node-exporter | 9100 | Host CPU/Memory/Disk | 서버 리소스 관측 불가 |
| cAdvisor | 8080 | Container CPU/Memory | 컨테이너 병목 추적 불가 |
| postgres-exporter | 9187 | DB connection/lock | DB 병목 추적 불가 |
| redis-exporter | 9121 | Redis memory/eviction | Redis 장애 원인 추적 불가 |
| nginx-exporter | 9113 | Nginx connection/status | Proxy 계층 장애 추적 불가 |

### 필수 지표

API:

- `http_requests_total`
- `http_request_duration_seconds_bucket`
- `financial_redis_fallback_total`
- `financial_db_transaction_retry_total`
- `financial_idempotency_hit_total`

PostgreSQL:

- `pg_up`
- `pg_stat_activity_count`
- `pg_locks_count`
- `pg_stat_database_xact_commit`
- `pg_stat_database_xact_rollback`
- `pg_stat_database_deadlocks`

Redis:

- `redis_up`
- `redis_connected_clients`
- `redis_memory_used_bytes`
- `redis_evicted_keys_total`
- `redis_commands_duration_seconds_total`

Nginx:

- `nginx_up`
- `nginx_connections_active`
- `nginx_http_requests_total`
- `upstream_response_time`
- `rate_limit_rejected_total`

Container/Host:

- `container_cpu_usage_seconds_total`
- `container_memory_usage_bytes`
- `container_oom_events_total`
- `node_filesystem_avail_bytes`
- `node_load1`

### Alert Rule 초안

```yaml
groups:
  - name: financial-event-infra-alerts
    rules:
      - alert: ApiHighP99Latency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API p99 latency is high"
          runbook: "docs/runbooks/high-latency-p99.md"

      - alert: RedisDownButApiAlive
        expr: redis_up == 0 and up{job="api"} == 1
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Redis is down, API should enter degraded mode"
          runbook: "docs/runbooks/redis-down.md"

      - alert: PostgresConnectionPressure
        expr: pg_stat_activity_count > 80
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL connection pressure detected"
          runbook: "docs/runbooks/postgres-connection-exhausted.md"

      - alert: FinancialConsistencyViolation
        expr: financial_consistency_violation_total > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Financial consistency violation detected"
          runbook: "docs/runbooks/consistency-violation.md"
```

README에는 다음 결과를 남긴다.

- Prometheus Targets: api, node-exporter, cadvisor, postgres-exporter, redis-exporter, nginx-exporter 모두 UP
- Grafana Dashboards: API/Infra/PostgreSQL/Redis/Nginx 5개 provision 확인
- Redis down 상태에서 `redis_up=0`, `financial_redis_fallback_total` 증가 확인
- DB connection pressure 상황에서 alert rule firing 확인
- k6 peak test 중 API p99와 DB/Redis/Nginx 지표를 함께 캡처
