# Ops Phase 3 Nginx Access Control Report

- Date: 2026-05-30
- Scope: public/internal Nginx endpoint separation
- Public base: `http://localhost:8080`
- Internal base: `http://localhost:8081`

## Public Endpoint Policy

Public Nginx is the simulated external entry point for financial clients.
It is configured as an allowlist, not a denylist.

Allowed:

- `GET /health`
- `POST /api/v1/transaction-events` with existing HMAC and idempotency policy

Blocked:

- `GET /ready`
- `GET /metrics`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`
- `GET /nginx_status`
- `GET /admin/*`
- `GET /debug/*`
- non-allowlisted `/api/` paths
- unknown paths

## Internal Endpoint Policy

Internal Nginx is for operators, Prometheus, and local verification scripts.

Allowed:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /nginx_status`

In local Docker Compose it is bound as `127.0.0.1:8081:8081`. In production, this endpoint must stay behind internal network controls such as VPN, security groups, mTLS, basic auth, or allowlists.

## Verification Commands

```bash
make ops3-up
make ops3-nginx-test
make ops3-check-access
make ops3-smoke-public
```

Full replay:

```bash
make ops3-demo
```

Regression commands:

```bash
make ops2-demo
make deploy-smoke
```

## Result Table

| Endpoint | Public 8080 | Internal 8081 | Judgment |
|---|---:|---:|---|
| `GET /health` | 200 | 200 | PASS |
| `GET /ready` | 404 | 200 | PASS |
| `GET /metrics` | 404 | 200 | PASS |
| `GET /docs` | 404 | - | PASS |
| `GET /redoc` | 404 | - | PASS |
| `GET /openapi.json` | 404 | - | PASS |
| `GET /nginx_status` | 404 | - | PASS |
| `GET /admin/debug` | 404 | - | PASS |
| `GET /debug/vars` | 404 | - | PASS |
| `GET /unknown` | 404 | - | PASS |
| `GET /api/v1/transaction-events` | 403 | - | PASS |
| `POST /api/v1/transaction-events without HMAC` | 400 | - | PASS |
| `POST /api/v1/transaction-events with valid HMAC` | 200 | - | PASS |

## Verification Source

| Check | Verification | Expected | Result |
|---|---|---|---|
| Public `/metrics` | `check_nginx_access_control.sh` | 403/404, never 200 | 404 PASS |
| Public `/ready` | `check_nginx_access_control.sh` | 403/404, never 200 | 404 PASS |
| Public `/docs` | `check_nginx_access_control.sh` | 403/404, never 200 | 404 PASS |
| Public `/redoc` | `check_nginx_access_control.sh` | 403/404, never 200 | 404 PASS |
| Public `/openapi.json` | `check_nginx_access_control.sh` | 403/404, never 200 | 404 PASS |
| Public `/50x.html` | `check_nginx_access_control.sh` | 403/404, never 200 | 404 PASS |
| Public non-allowlisted `/api/` path | `check_nginx_access_control.sh` | 403/404, never 200 | 404 PASS |
| Public unknown path | `check_nginx_access_control.sh` | 404 | 404 PASS |
| Public transaction GET | `check_nginx_access_control.sh` | 403/404/405 | 403 PASS |
| Internal `/metrics` | `check_nginx_access_control.sh` | 200 and `financial_http_requests_total` present | 200 PASS |
| Internal `/ready` | `check_nginx_access_control.sh` | 200 | 200 PASS |
| Public transaction API without HMAC | `check_nginx_access_control.sh` | 400/401/403/422 | 400 PASS |
| Public transaction with HMAC | `make ops3-smoke-public` | 200/201/202 and idempotency replay | 200 PASS |

## Prometheus Scrape Path

Prometheus scrapes application metrics through internal Nginx:

```text
nginx:8081/metrics
```

Public `http://localhost:8080/metrics` must remain blocked.

Ops Phase 3 `make ops3-demo` uses the base `docker-compose.yml` Prometheus service. The Ops Phase 1 monitoring overlay follows the same internal scrape principle through `infra/monitoring/prometheus/prometheus.yml`.

## Remaining Limits

- Loopback binding is suitable for local verification only.
- Production internal endpoints need stronger network and identity controls.
- Public `/health` still exposes local Blue-Green identity fields for rehearsal; production can move those fields to internal diagnostics or restricted headers.
- This phase does not add Kubernetes, VPN/NAC, WAF, or mTLS infrastructure.
