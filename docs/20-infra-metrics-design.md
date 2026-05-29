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
- nginx-prometheus-exporter는 Ops Phase 2에서 `stub_status`와 내부 접근 제어를 함께 설계한다.

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
    check-required-metrics.sh
```

## 5. 검증 명령어

```bash
make ops1-up
make metrics-check
make required-metrics-check
make grafana-check
make ops1-check
```

성공 기준:

- Prometheus target 중 down 상태가 0개
- api, node-exporter, cadvisor, postgres-exporter, redis-exporter target 존재
- nginx-exporter는 Ops Phase 2 후보로 optional/TODO 표시
- 필수 metric key가 Prometheus API에서 조회됨
- Prometheus config와 alert rule syntax 검증 통과
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
| nginx-exporter | 9113 | Nginx connection/status | Ops Phase 2에서 보강 |

로컬 확인 편의를 위해 Prometheus/Grafana는 `127.0.0.1`에 노출한다.
PostgreSQL/Redis exporter는 host port를 열지 않고 Docker 내부 network에서만 수집한다.
node-exporter와 cAdvisor도 host 접근은 `127.0.0.1`로 제한한다.

cAdvisor는 로컬 Docker container metric 수집을 위해 host filesystem과 Docker runtime 정보를 read-only로 참조한다.
이 구성은 로컬 운영 실습용이며, 운영 환경에서는 접근 권한, 네트워크 노출, 수집 범위를 별도로 제한해야 한다.

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

Nginx 지표는 이번 Ops Phase 1에서 dashboard TODO로 남긴다.
Nginx exporter는 `stub_status` 노출과 `/metrics` 내부 접근 제어가 함께 필요하므로
Ops Phase 2에서 접근 제어와 rate limit 정책을 다룰 때 연결한다.

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

- Prometheus Targets: api, node-exporter, cadvisor, postgres-exporter, redis-exporter 모두 UP
- Grafana Dashboards: API/Infra/PostgreSQL/Redis/Nginx 5개 provision 확인
- Nginx dashboard는 Ops Phase 2 exporter 연동 TODO로 표시
- 실제 Redis down, DB pressure, k6 peak 수치는 후속 장애 재현/측정 단계에서 기록
