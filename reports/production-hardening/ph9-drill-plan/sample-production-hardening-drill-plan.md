# PH9 Production Hardening Drill Plan

- Run ID: `ph9-production-hardening-drill-plan-sample`
- Generated at: `2026-07-07T00:00:00+00:00`
- Phase: `PH9 Production Hardening Drill Plan & Evidence Runner`
- Current status: Implemented as a safe catalog/report/validator. Destructive drills, write resume, failover promote, financial correction, partner key retirement, and AI recovery adoption remain human-approved.
- Drill count: 8

## Scope

- PH1~PH8 hardening drill catalog
- safe evidence report generation
- validation of automation and manual approval boundaries
- PH10/PH11 latency work linked only as follow-up candidates

## Drill Catalog

| Phase | Drill ID | Name | Safe Auto Run | Manual Run | Evidence |
| --- | --- | --- | --- | --- | --- |
| PH1 | `ph1-postgres-write-suspend-db-down` | PostgreSQL Write Suspend / DB Down Drill | false | true | write suspend mode, Retry-After response |
| PH2 | `ph2-incident-artifact-sanitized-report` | Incident Artifact / Sanitized Report Drill | true | false | incident artifact, sanitized report |
| PH3 | `ph3-incident-analyzer-mvp` | Incident Analyzer MVP Drill | true | false | analyzer output, classification |
| PH4 | `ph4-recovery-case-quarantine-manual-approval` | Recovery Case / Quarantine / Manual Approval Drill | false | true | recovery case report, quarantine record |
| PH5 | `ph5-stale-processing-reconciliation` | Stale PROCESSING Reconciliation Drill | false | true | stale processing count, reconciliation summary |
| PH6 | `ph6-ai-safe-context-sanitizer` | AI-safe Context Sanitizer Drill | true | false | sanitized context JSON, sanitized context Markdown |
| PH7 | `ph7-partner-hmac-rotation` | Partner HMAC Rotation Drill | true | false | HMAC rotation report, next dry-run rejection on write API |
| PH8 | `ph8-postgres-ha-queue-decision-evidence` | PostgreSQL HA / Durable Queue Decision Evidence | true | false | decision matrix report, validator result |

## Automation Boundary

- generate deterministic drill catalog
- validate required evidence and safety boundaries
- create sanitized JSON and Markdown reports
- run safe validators and read-only evidence checks
- leave state-changing drills as manual-run candidates

## Manual Approval Boundary

- PostgreSQL failover promote
- write resume after DB recovery or failover
- ledger correction or compensation
- customer or partner impact confirmation
- partner secret rotation approval
- queue replay or DLQ redrive
- AI-assisted recovery proposal adoption

## Follow-up Candidates

- PH10: Latency attribution instrumentation (follow_up_candidate)
- PH11: Latency drill test plan execution (follow_up_candidate)

## Validation Summary

- Sensitive data included: false
- Destructive commands allowed: false
- PH10/PH11 latency drills completed in PH9: false
