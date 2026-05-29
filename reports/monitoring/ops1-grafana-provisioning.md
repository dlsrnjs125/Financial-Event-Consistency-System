# Ops Phase 1 Grafana Provisioning Check

- Date: 2026-05-29T19:04:06Z
- Git Commit: 267324e
- Branch: feature/ops1-infra-metrics-extension
- Result: PASSED

| File | Expected | Status | Note |
|---|---|---|---|
| `infra/monitoring/grafana/provisioning/datasources/datasource.yml` | datasource provisioning exists | PASS |  |
| `infra/monitoring/grafana/provisioning/dashboards/dashboard.yml` | dashboard provider exists | PASS |  |
| `infra/monitoring/grafana/dashboards/api-dashboard.json` | title and at least one panel | PASS | Financial Event API Dashboard |
| `infra/monitoring/grafana/dashboards/infra-dashboard.json` | title and at least one panel | PASS | Financial Event Infra Dashboard |
| `infra/monitoring/grafana/dashboards/postgres-dashboard.json` | title and at least one panel | PASS | Financial Event PostgreSQL Dashboard |
| `infra/monitoring/grafana/dashboards/redis-dashboard.json` | title and at least one panel | PASS | Financial Event Redis Dashboard |
| `infra/monitoring/grafana/dashboards/nginx-dashboard.json` | title and at least one panel | PASS | Financial Event Nginx Dashboard |
