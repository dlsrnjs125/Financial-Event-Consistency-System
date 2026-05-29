# Ops Phase 1 Required Metrics Check

- Date: 2026-05-29T19:38:45Z
- Tested Commit: 3831236
- Branch: feature/ops1-infra-metrics-extension
- Result: PASSED

> Note: The tested commit can differ from the final PR commit because evidence reports are generated before being committed.

| Query | Expected | Status | Note |
|---|---|---|---|
| `up{job="api"} == 1` | queryable | PASS | 1 series |
| `up{job="node-exporter"} == 1` | queryable | PASS | 1 series |
| `up{job="cadvisor"} == 1` | queryable | PASS | 1 series |
| `up{job="postgres-exporter"} == 1` | queryable | PASS | 1 series |
| `up{job="redis-exporter"} == 1` | queryable | PASS | 1 series |
| `pg_up == 1` | queryable | PASS | 1 series |
| `redis_up == 1` | queryable | PASS | 1 series |
| `financial_http_requests_total` | queryable | PASS | 3 series |
| `node_cpu_seconds_total` | queryable | PASS | 96 series |
| `container_cpu_usage_seconds_total` | queryable | PASS | 13 series |
| `financial_readiness_dependency_status` | exposed by API /metrics | PASS | metric definition present |
| `financial_redis_fallback_total` | exposed by API /metrics | PASS | metric definition present |
