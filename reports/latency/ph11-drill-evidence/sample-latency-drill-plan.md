# PH11 Latency Drill Evidence Runner

- Run ID: `ph11-latency-drill-evidence-runner-sample`
- Generated at: `2026-07-08T00:00:00+00:00`
- Phase: `PH11 Latency Drill Test Plan & Safe Evidence Runner`
- Current status: Implemented as a safe catalog, synthetic evidence generator, PH10 analyzer integration, and validator. Default demo does not execute DB lock holders, Redis down/delay, Nginx delay, mock partner, Toxiproxy, netem, or production fault injection.
- Drill count: `6`

## Scope

- LAT-001~LAT-006 latency drill catalog
- safe sample evidence generation
- PH10 analyzer input generation and expected/actual comparison
- consistency evidence boundary validation
- manual/opt-in boundary for destructive or environment-changing drills

## Drill Catalog

| Drill | Name | Safe Demo | Manual Required | Expected PH10 | Actual PH10 |
| --- | --- | --- | --- | --- | --- |
| `LAT-001` | Baseline Latency Drill | true | false | `baseline_normal_latency` | `baseline_normal_latency` |
| `LAT-002` | PostgreSQL Pool Pressure Drill | false | true | `internal_postgres_pool_pressure` | `internal_postgres_pool_pressure` |
| `LAT-003` | PostgreSQL Lock Contention Drill | false | true | `internal_postgres_lock_contention` | `internal_postgres_lock_contention` |
| `LAT-004` | Redis Delay / Redis Down Drill | false | true | `redis_degraded_latency` | `redis_degraded_latency` |
| `LAT-005` | External Dependency Slow Response Drill | false | true | `external_endpoint_slow` | `external_endpoint_slow` |
| `LAT-006` | Nginx Edge / Client Network Latency Drill | false | true | `edge_or_client_network_latency` | `edge_or_client_network_latency` |

## PH10 Analyzer Link

- Script: `scripts/ph10_latency_attribution.py`
- Input contract: `reports/latency/ph11-drill-evidence/sample-ph10-input-evidence.json`
- Policy: Each drill records expected_ph10_classification, recomputes the PH10 analyzer output from ph10_input_scenario, and validates it against stored actual_ph10_classification.

## Safe Demo / Manual Boundary

- Safe demo scenarios:
  - `baseline`
  - `db_pool_pressure`
  - `db_lock_contention`
  - `redis_degraded`
  - `redis_unavailable`
  - `external_endpoint_slow`
  - `app_http_client_path_issue`
  - `nginx_edge_latency`
  - `insufficient_evidence`
- Manual drill candidates:
  - DB pool pressure with altered pool size
  - controlled DB lock holder
  - Redis down or Redis delay with network tooling
  - mock partner slow endpoint
  - Nginx edge/client network latency profile

## Consistency Policy

- Any non-zero consistency counter is treated as a consistency incident candidate before latency classification.
- Required sample consistency counters stay at zero.

## Sensitive Data Policy

- Plain financial identifiers, retry identifiers, payload contents, auth material, signing material, and endpoint values are prohibited.
- Metric labels are limited to bounded route, endpoint, partner, method, status, result, phase, and operation fields.

## Follow-up Candidates

- Toxiproxy or netem latency profiles
- OpenTelemetry full tracing
- Grafana latency attribution dashboard
- mock partner service compose profile
- controlled DB lock holder script
