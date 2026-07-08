# PH10 Latency Attribution Report

- Run ID: `ph10-sample-latency-attribution`
- Generated at: `2026-07-07T00:00:00+00:00`
- Scenario: `db_phase_dominant`
- Classification: `internal_postgres_latency`
- Confidence: `HIGH`
- Primary suspect: `postgres`
- Consistency status: `CLEAN`

## Interpretation Boundary

- k6 p95/p99 are symptom evidence, not standalone root-cause proof.
- Attribution compares Nginx timing, FastAPI phase timing, Redis/PostgreSQL, outbound HTTP, blackbox probe, and consistency evidence.
- PH10 implements an analyzer/report, not PH11 latency drill execution.
- Consistency violations remain separate SEV1 candidates and are not downgraded to latency warnings.

## Evidence

- FastAPI handler p95 increased
- PostgreSQL phase is at least 60% of handler time
- Redis and outbound phases are not dominant

## Recommended Next Checks

- check DB pool, lock wait, slow query, and consistency SQL evidence

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
