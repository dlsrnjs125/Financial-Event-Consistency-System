# Ops Phase 1 Required Metrics Check

- Date: 2026-05-29T19:04:06Z
- Git Commit: 267324e
- Branch: feature/ops1-infra-metrics-extension
- Result: PASSED

| Metric | Expected | Status | Note |
|---|---|---|---|
| `up` | queryable | PASS | 6 series |
| `process_cpu_seconds_total` | queryable | PASS | 6 series |
| `node_cpu_seconds_total` | queryable | PASS | 96 series |
| `container_cpu_usage_seconds_total` | queryable | PASS | 13 series |
| `pg_up` | queryable | PASS | 1 series |
| `redis_up` | queryable | PASS | 1 series |
