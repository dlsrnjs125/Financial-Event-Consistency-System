# Ops Phase 1 Grafana Provisioning Check

- Date: 2026-05-29T19:38:45Z
- Tested Commit: 3831236
- Branch: feature/ops1-infra-metrics-extension
- Result: PASSED

> Note: The tested commit can differ from the final PR commit because evidence reports are generated before being committed.

| File | Expected | Status | Note |
|---|---|---|---|
| `infra/monitoring/grafana/provisioning/datasources/datasource.yml` | datasource provisioning exists | PASS |  |
| `infra/monitoring/grafana/provisioning/dashboards/dashboard.yml` | dashboard provider exists | PASS |  |
| `infra/monitoring/grafana/dashboards/api-dashboard.json` | title and at least one panel | PASS | Financial Event API Dashboard |
| `infra/monitoring/grafana/dashboards/infra-dashboard.json` | title and at least one panel | PASS | Financial Event Infra Dashboard |
| `infra/monitoring/grafana/dashboards/postgres-dashboard.json` | title and at least one panel | PASS | Financial Event PostgreSQL Dashboard |
| `infra/monitoring/grafana/dashboards/redis-dashboard.json` | title and at least one panel | PASS | Financial Event Redis Dashboard |
| `infra/monitoring/grafana/dashboards/nginx-dashboard.json` | title and at least one panel | PASS | Financial Event Nginx Dashboard |
| `http://localhost:3000/api/health` | Grafana API health | PASS | loaded |
| `http://localhost:3000/api/datasources` | Grafana datasource loaded | PASS | loaded |
| `http://localhost:3000/api/search` | Grafana dashboards searchable | PASS | loaded |
