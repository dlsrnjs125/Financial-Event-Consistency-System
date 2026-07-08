# PH10 Latency Attribution Report

- Run ID: `ph11-db_lock_contention-sample`
- Generated at: `2026-07-08T00:00:00+00:00`
- Scenario: `db_lock_contention`
- Classification: `internal_postgres_lock_contention`
- Confidence: `MEDIUM`
- Primary suspect: `postgres_lock_wait`
- Consistency status: `CLEAN`

## Interpretation Boundary

- k6 p95/p99 are symptom evidence, not standalone root-cause proof.
- Attribution compares Nginx timing, FastAPI phase timing, Redis/PostgreSQL, outbound HTTP, blackbox probe, and consistency evidence.
- PH10 implements an analyzer/report, not PH11 latency drill execution.
- Consistency violations remain separate SEV1 candidates and are not downgraded to latency warnings.

## Evidence

- DB lock wait is a large share of FastAPI handler time

## Recommended Next Checks

- inspect lock holder queries and transaction duration

## Manual Confirmation Required

- operator must confirm with dashboard, logs, and runbook evidence
- do not treat deterministic classification as final root cause
- if consistency_status is VIOLATION_DETECTED, follow consistency incident flow first

## Follow-up Candidates

- PH11 k6 latency scenarios and fault injection
- mock partner service
- Toxiproxy or netem latency profile
- OpenTelemetry trace expansion
- Grafana latency attribution dashboard
