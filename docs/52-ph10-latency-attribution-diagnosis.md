# PH10 Latency Attribution / External Dependency Diagnosis

## 1. Goal

PH10 adds a deterministic latency attribution analyzer that turns sanitized latency evidence into an operator-readable diagnosis report.

The goal is not to prove a final root cause from one metric. The goal is to separate symptom evidence from supporting evidence so an incident responder can quickly decide which dashboard, log, or runbook check should come next.

## 2. Why PH10 Exists

k6 p95 or p99 latency is useful because it shows what a client feels. It is not enough to prove whether the root cause is PostgreSQL, Redis, FastAPI, Nginx, an outbound partner dependency, or a client network path.

PH10 compares multiple evidence groups:

- k6 p95/p99 and error rate
- Nginx request and upstream timing
- FastAPI handler timing
- application phase timing for HMAC, idempotency, Redis, PostgreSQL, business logic, and outbound HTTP
- blackbox probe timing for external endpoints
- consistency counters such as duplicate ledger, duplicate external event, reconciliation failure, and invalid state transition counts

The analyzer returns a candidate classification and recommended next checks. It never replaces operator confirmation.

## 3. Scope

PH10 includes:

- `scripts/ph10_latency_attribution.py`
- deterministic classification rules
- sanitized sample input evidence
- sanitized JSON and Markdown reports
- report validation for required fields, safe classification boundaries, metric label policy, and sensitive data patterns
- Makefile targets for demo, validation, rule listing, and PH10 safety check

PH10 does not include:

- PH11 k6 latency drill execution
- fault injection with Toxiproxy or netem
- mock partner service latency profiles
- production network fault injection
- OpenTelemetry full tracing
- AI root-cause confirmation or automatic recovery

## 4. Commands

Generate the curated sample evidence and report:

```bash
make ph10-latency-attribution-demo
```

Validate the sample report:

```bash
make ph10-latency-attribution-validate
```

List deterministic classification rules:

```bash
make ph10-latency-attribution-list-rules
```

Run PH10 validation plus shared safety checks:

```bash
make ph10-latency-check
```

Analyze a custom sanitized evidence file:

```bash
python3 scripts/ph10_latency_attribution.py analyze \
  --input reports/latency/ph10-attribution/sample-input-evidence.json \
  --output-dir reports/latency/ph10-attribution
```

## 5. Artifact Structure

PH10 writes curated evidence under:

```text
reports/latency/ph10-attribution/
```

The sample artifact set contains:

- `sample-input-evidence.json`
- `sample-latency-attribution-report.json`
- `sample-latency-attribution-report.md`

The input evidence intentionally uses bounded fields such as `route_group`, `method`, and `status_code_family`. It does not include raw account numbers, raw retry keys, authorization material, signatures, raw request bodies, or raw endpoint URLs.

## 6. Classification Rules

The first PH10 rule set supports these candidate classifications:

- `baseline_normal_latency`
- `internal_application_latency`
- `internal_postgres_latency`
- `internal_postgres_pool_pressure`
- `internal_postgres_lock_contention`
- `redis_degraded_latency`
- `redis_unavailable_fallback`
- `external_dependency_latency`
- `external_endpoint_slow`
- `app_http_client_path_issue`
- `edge_or_client_network_latency`
- `partner_specific_latency`
- `route_specific_latency_candidate`
- `insufficient_evidence`

The rules intentionally require supporting signals. For example, a PostgreSQL classification requires FastAPI handler timing plus PostgreSQL phase timing. A k6 percentile spike by itself is treated as symptom evidence.
The partner and route-specific classifications are LOW confidence scope-narrowing candidates, not final root-cause claims.

## 7. Consistency Boundary

Latency and consistency are related but not equivalent.

If consistency counters show duplicate ledger rows, duplicate external events, reconciliation failures, or invalid state transitions, PH10 preserves `VIOLATION_DETECTED`. That condition must be handled as a consistency incident candidate, not downgraded to a normal latency warning.

## 8. Sensitive Data Policy

PH10 reports are safe to review and share because they use bounded labels and phase summaries.

Allowed examples:

- `route_group`
- `endpoint_group`
- `partner_alias`
- `method`
- `status_code_family`
- `phase`
- latency percentiles and consistency counts

Prohibited examples:

- plain financial identifiers
- plain retry identifiers
- request payload contents
- authorization headers
- signing material
- plain endpoint values
- database connection strings

The validator checks for sensitive text patterns and forbidden metric labels.

## 9. PH11 Boundary

PH11 remains the place for actual latency drills and fault injection. PH10 can consume PH11 evidence later, but this phase does not claim that latency drills have been executed.

PH11 now reuses the PH10 analyzer through `scripts/ph11_latency_drill_runner.py`.
PH10 remains the candidate-classification layer, while PH11 generates drill evidence, compares expected and actual PH10 classifications, and keeps destructive fault injection outside the default demo.

Follow-up candidates include:

- k6 latency baseline and regression scenarios
- PostgreSQL pool pressure and lock contention drills
- Redis delay/down drills
- external endpoint slow response drills
- internal resource saturation evidence with CPU, memory, worker, and queue depth signals
- mock partner service
- Toxiproxy or netem latency profiles
- OpenTelemetry trace expansion

## 10. Troubleshooting

### k6 Percentile Spike Looks Like a Root Cause

- Problem: A high p95 or p99 can be misread as proof that PostgreSQL, Redis, or an external dependency caused the issue.
- Cause: k6 measures the client-visible symptom and does not include internal phase attribution.
- Solution: PH10 requires supporting Nginx, FastAPI phase, Redis, PostgreSQL, outbound, or blackbox evidence before assigning a dependency-specific classification.
- Verification: `test_k6_only_root_cause_claim_fails_validation` rejects k6-only root-cause claims.
- README exclusion: README only links the PH10 command and doc; the full rule explanation lives here.

### Consistency Violation Hidden Behind Latency

- Problem: Duplicate ledger or reconciliation failures can be buried in a latency incident report.
- Cause: Performance incidents and consistency incidents are often investigated together during retry storms.
- Solution: PH10 keeps a separate `consistency_status` and never treats a consistency violation as clean latency noise.
- Verification: `test_consistency_violation_cannot_be_reported_clean` rejects a clean report when violation counters exist.
- README exclusion: The consistency escalation detail belongs in this document and the incident runbooks.

### Raw Identifiers In Metric Labels

- Problem: A convenient metric label such as account, event, retry key, or request id can leak sensitive data.
- Cause: High-cardinality labels are tempting when debugging one incident, but they are unsafe and expensive.
- Solution: PH10 allows bounded labels such as route group, endpoint group, partner alias, method, status code, result, phase, and operation.
- Verification: `test_forbidden_metric_label_fails_validation` rejects forbidden label names.
- README exclusion: README keeps the high-level privacy statement only.

### External Endpoint vs App HTTP Client Path

- Problem: Slow outbound HTTP can be caused by the provider endpoint or by the local HTTP client path.
- Cause: App outbound timing alone cannot separate provider slowness from DNS, TLS, pool, timeout, or retry behavior.
- Solution: PH10 compares app outbound timing with blackbox probe timing and returns either `external_endpoint_slow` or `app_http_client_path_issue`.
- Verification: dedicated unit tests cover both classifications.
- README exclusion: This branching logic is too detailed for the root README.

### PH11 Drill Evidence Claimed Too Early

- Problem: A report can accidentally imply that PH11 k6 latency drills or fault injection were already completed.
- Cause: PH10 and PH11 both discuss latency, but PH10 is the analyzer/reporting step.
- Solution: PH10 validator rejects PH11 completed-claim text and the Markdown report states the boundary explicitly.
- Verification: `test_ph11_completed_claim_fails_validation` checks this boundary.
- README exclusion: README references PH10 as an analyzer only and leaves PH11 execution details for `42-latency-drill-test-plan.md`.
