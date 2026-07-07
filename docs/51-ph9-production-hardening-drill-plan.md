# PH9 Production Hardening Drill Plan

## 1. Goal

PH9 ties the PH1~PH8 production hardening outputs into a reproducible drill catalog and evidence report.

It does not add a new recovery automation path. It makes the existing safety work easier to review by showing which checks are safe to run automatically, which commands require local/manual setup, and which decisions must remain human-approved.

## 2. Why PH9 Exists

PH1~PH8 added write suspension, out-of-band incident artifacts, deterministic analyzer output, recovery cases, stale processing reconciliation, AI-safe context, HMAC rotation evidence, and PostgreSQL HA / queue trade-off evidence.

Those pieces are useful individually, but production hardening also needs an operator-facing drill plan:

- What can be generated safely?
- What requires Docker, database state, or manual setup?
- What must never be approved by automation?
- Which follow-up latency drills are only candidates?

PH9 answers those questions with a deterministic JSON/Markdown report and validator.

## 3. Scope and Non-Scope

Scope:

- PH1~PH8 drill catalog
- safe report generation
- validator for required drill coverage
- validator for automation/manual approval boundaries
- sanitized evidence report
- PH10/PH11 latency work linked only as follow-up candidates

Non-scope:

- PostgreSQL failover promote automation
- write resume auto-approval
- financial ledger correction automation
- partner key retirement approval
- queue middleware provisioning
- HA cluster provisioning
- latency attribution instrumentation implementation
- k6 latency drill implementation
- AI-assisted recovery execution

## 4. Drill Catalog

The generated catalog is written to:

```text
reports/production-hardening/ph9-drill-plan/sample-production-hardening-drill-plan.json
reports/production-hardening/ph9-drill-plan/sample-production-hardening-drill-plan.md
```

Included drills:

| Phase | Drill | Boundary |
| --- | --- | --- |
| PH1 | PostgreSQL Write Suspend / DB Down Drill | DB down and write resume remain manual-run boundaries |
| PH2 | Incident Artifact / Sanitized Report Drill | safe artifact generation and validation |
| PH3 | Incident Analyzer MVP Drill | classification candidate only, no recovery execution |
| PH4 | Recovery Case / Quarantine / Manual Approval Drill | execution and quarantine release stay approval-gated |
| PH5 | Stale PROCESSING Reconciliation Drill | count-only detection, no automatic completion/failure |
| PH6 | AI-safe Context Sanitizer Drill | context generation only, no external AI call or recovery action |
| PH7 | Partner HMAC Rotation Drill | staged verification only, final rotation approval remains manual |
| PH8 | PostgreSQL HA / Durable Queue Decision Evidence | architecture evidence only, no HA/queue provisioning |

## 5. Automation Boundary

PH9 automation is limited to:

- generating the drill catalog
- generating sample JSON/Markdown evidence
- validating required PH1~PH8 coverage
- validating linked documents, success criteria, and sensitive data policy
- checking that destructive/manual commands are not placed in auto-run command lists
- checking that PH10/PH11 latency work remains follow-up only

PH9 does not stop containers, pause PostgreSQL, approve write resume, execute recovery cases, mutate balances, redrive queues, retire partner keys, or call AI APIs.

## 6. Manual Approval Boundary

The following remain human-approved:

- PostgreSQL failover promote
- write resume after DB recovery or failover
- ledger correction or compensation
- affected customer or partner impact confirmation
- partner secret rotation approval
- queue replay or DLQ redrive
- AI-assisted recovery proposal adoption

This boundary matches the project rule that automation may detect, block, collect evidence, and propose candidates, but must not create financial state changes without operator approval.

## 7. Evidence Report Structure

Top-level fields:

```text
run_id
generated_at
phase
scope
current_status
drill_count
drills
manual_approval_boundaries
automation_boundaries
follow_up_candidates
validation_summary
```

Each drill includes:

```text
phase
drill_id
name
goal
linked_docs
safe_to_auto_run
manual_run_required
requires_docker
requires_k6
requires_database
commands
expected_evidence
safety_boundary
manual_approval_required_for
success_criteria
failure_signals
sensitive_data_policy
status
```

The `commands` field is restricted to existing Makefile targets and must not contain destructive or manual approval actions. More invasive drill commands are listed as candidates, not as default auto-run commands.

Candidate commands are not default auto-run commands. Operators must read the linked drill document and confirm the manual boundary before running them.

Generated Markdown reports also include safety notes:

- PH9 does not run destructive drills by default.
- PH10/PH11 latency work is listed only as follow-up candidates.
- AI-safe context generation does not authorize recovery execution.
- Queue-first architecture must split `ACCEPTED` and `COMPLETED`.

## 8. CLI and Makefile

CLI:

```bash
python3 scripts/ph9_production_hardening_drill.py demo
python3 scripts/ph9_production_hardening_drill.py validate --input reports/production-hardening/ph9-drill-plan/sample-production-hardening-drill-plan.json
python3 scripts/ph9_production_hardening_drill.py list
```

Makefile:

```bash
make ph9-hardening-drill-demo
make ph9-hardening-drill-validate
make ph9-hardening-drill-list
make ph9-hardening-check
```

`ph9-hardening-check` runs the PH9 validator with `security-log-check` and `scripts-check`.

## 9. Validation Rules

The validator fails when:

- required top-level fields are missing
- any PH1~PH8 drill is missing
- PH10/PH11 latency work is included as a completed drill
- a safe auto-run drill includes manual approval actions
- destructive/manual commands are listed in `commands`
- a command does not map to an existing Makefile target
- `linked_docs`, `success_criteria`, or `sensitive_data_policy` is empty
- sensitive runtime values or unsafe field patterns are present
- queue-first is described as guaranteeing ledger completion
- HA is described as replacing the consistency gate
- AI is described as an automatic recovery executor

## 10. Relationship with PH10/PH11 Latency Work

PH9 is not latency attribution implementation.

PH10/PH11 remain follow-up candidates:

- PH10: latency attribution instrumentation and external dependency diagnosis
- PH11: latency drill execution plan and report generator

k6 remains a latency symptom reproduction tool. Root-cause attribution must compare k6 output with Nginx timing, FastAPI phase metrics, PostgreSQL/Redis metrics, external dependency metrics, and sanitized logs.

## 11. Troubleshooting Notes

### Over-Automating Every Drill

- 문제: every drill looks runnable when listed under a single catalog.
- 원인: DB down, write resume, recovery approval, and failover actions have different risk levels.
- 해결: PH9 splits `commands`, candidate commands, safe auto-run flags, and manual approval boundaries.
- 검증: validator fails when destructive/manual actions appear in default `commands`.
- README에 넣지 않은 이유: detailed drill policy belongs in this PH9 document.

### Nonexistent Makefile Targets Look Like Evidence

- 문제: a report can imply a command is runnable even when the target does not exist.
- 원인: free-form command strings are easy to mistype or overstate.
- 해결: validator checks that every `commands` entry maps to an existing Makefile target.
- 검증: unit tests tamper commands and expect validation errors.
- README에 넣지 않은 이유: README should list only representative commands.

### PH10/PH11 Latency Work Looks Completed Too Early

- 문제: latency attribution candidates can be mistaken for PH9 implementation.
- 원인: PH9 references docs/41 and docs/42 to preserve continuity.
- 해결: PH10/PH11 are stored only in `follow_up_candidates`, not `drills`.
- 검증: validator fails if PH10 or PH11 appears as a completed drill.
- README에 넣지 않은 이유: roadmap docs carry detailed phase boundaries.

### AI-safe Context Is Confused With AI Recovery Execution

- 문제: AI-safe evidence could be read as permission for AI to execute recovery.
- 원인: context generation and recovery approval are often discussed together.
- 해결: PH9 states that AI may receive sanitized context but cannot approve financial state changes.
- 검증: validator rejects phrases that describe AI as an automatic recovery executor.
- README에 넣지 않은 이유: README keeps only the high-level human approval rule.

### Queue-first Candidate Is Treated As Completed Architecture

- 문제: durable enqueue can be misread as ledger completion.
- 원인: queue-first improves accept availability, but changes API response meaning.
- 해결: PH9 inherits PH8's `ACCEPTED` / `COMPLETED` split and keeps queue-first as follow-up architecture work.
- 검증: validator rejects queue-first completion guarantee claims.
- README에 넣지 않은 이유: the ADR and PH8/PH9 docs hold the detailed contract discussion.

### README Becomes Too Large

- 문제: adding the full drill catalog to README makes the portfolio entry hard to scan.
- 원인: PH9 aggregates many prior hardening phases.
- 해결: README gets only one summary sentence, a docs link, and representative commands.
- 검증: the full catalog is generated under `reports/production-hardening/ph9-drill-plan/`.
- README에 넣지 않은 이유: the generated report is the canonical catalog.

## 12. Limits and Next Steps

Limits:

- PH9 does not execute destructive drills by default.
- PH9 does not replace operator judgment.
- PH9 does not implement latency attribution instrumentation.
- PH9 does not implement k6 latency drill scenarios.
- PH9 does not provision HA databases or durable queues.

Next steps:

- PH10 latency attribution instrumentation
- PH11 latency drill execution and evidence report
- managed DB HA runbook candidate
- queue-first V2 API contract ADR
