# PH8 PostgreSQL HA / Queue Decision Report

- Run ID: `ph8-ha-queue-tradeoff-sample`
- Generated at: `2026-07-07T00:00:00+00:00`
- Phase: `PH8 PostgreSQL HA / Durable Queue Trade-off ADR`
- Current decision: Maintain direct PostgreSQL transaction + fail-closed/write suspend now; treat PostgreSQL HA and durable queue-first architecture as follow-up availability and V2 contract candidates.

## Decision Matrix

| Option | Availability | Explainability | Complexity | Cost | Local Fit | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Current: Direct PostgreSQL Transaction + Fail-Closed | 2 | 5 | 5 | 5 | 5 | recommended_now |
| PostgreSQL Primary/Standby HA | 4 | 4 | 3 | 3 | 3 | follow_up_candidate |
| Synchronous Replication | 3 | 4 | 2 | 3 | 2 | follow_up_candidate |
| Managed DB HA | 4 | 4 | 4 | 2 | 2 | recommended_later |
| Durable Queue-First Architecture | 5 | 3 | 1 | 2 | 1 | v2_candidate |

## Recommendation

Recommended now:
- Direct PostgreSQL transaction
- Fail-closed 503 + Retry-After when PostgreSQL write path is unavailable
- Write suspend, recovery case, and consistency gate before write resume

Follow-up candidates:
- managed DB HA runbook and failover drill
- stale connection readiness drill
- queue-first API V2 ADR
- consumer idempotency and DLQ replay design
- RPO/RTO split for API accept and ledger posting
