# PH3 Incident Analyzer MVP

## 1. PH3 Goal

PH3 adds a deterministic rule-based Incident Analyzer MVP.
It reads a sanitized PH2 incident artifact and generates an operator-facing first classification.

PH3 output is advisory only:

- classification candidate
- severity candidate
- confidence candidate
- primary signals
- observed auto actions
- manual actions required
- recommended runbooks

PH3 does not resolve incidents, approve write resume, execute DB failover, call AI APIs, or create recovery cases.

## 2. PH1/PH2 Connection

PH1 prevents successful financial writes during PostgreSQL write-path failure.
PH2 creates an out-of-band sanitized artifact bundle under `reports/incidents/{incident_id}/`.
PH3 analyzes that PH2 artifact and writes:

```text
reports/incidents/{incident_id}/
  analyzer-result.json
  incident-analysis.md
```

## 3. Scope And Non-Scope

Included:

- `scripts/ph3_incident_analyzer.py`
- deterministic MVP rules
- `analyze` and `validate` commands
- `analyzer-result.json`
- `incident-analysis.md`
- Makefile targets
- unit tests for rule priority and output validation

Excluded:

- `recovery_cases` DB table
- `incident_events` DB table
- automatic recovery execution
- ledger correction SQL
- automatic write resume approval
- AI API calls
- Slack/PagerDuty integration
- live Prometheus query integration
- latency phase instrumentation
- PostgreSQL HA or durable queue

## 4. Analyzer Input And Output

Input:

```text
manifest.json
write-suspend-state.json
health-ready-summary.json
consistency-summary.json
command-results.json
docker-compose-status.txt
sanitized-report.md
```

PH3 does not read `raw/`.
PH3 reuses PH2 artifact validation before classification and treats sensitive validation findings as highest-priority risk.

Output:

```text
analyzer-result.json
incident-analysis.md
```

Both outputs must include:

```text
sensitive_data_included=false
manual_review_required=true
```

## 5. Rule Set

### Rule 1. PostgreSQL Down + Write Suspended

Conditions:

- `manifest.scenario == POSTGRES_DOWN`
- or `write-suspend-state.reason == postgres_unavailable`
- or `write-suspend-state.active == true` with source `postgres_probe`, `runtime`, or `artifact`

Output:

- classification: `POSTGRES_DOWN_WRITE_SUSPENDED`
- severity: `SEV1`
- confidence: `0.9`

### Rule 2. Write Suspended Unknown Dependency

Conditions:

- `write-suspend-state.active == true`
- scenario is `unknown`, `not_collected`, or missing

Output:

- classification: `WRITE_SUSPENDED_UNKNOWN_DEPENDENCY`
- severity: `SEV2`
- confidence: `0.65`

### Rule 3. Sanitization Risk

Conditions:

- `manifest.sensitive_data_included != false`
- or PH2 validation reports sensitive data risk

Output:

- classification: `ARTIFACT_SANITIZATION_RISK`
- severity: `SEV2`
- confidence: `0.8`

### Rule 4. Consistency Issue Candidate

Conditions:

- `duplicate_ledger_count > 0`
- or `duplicate_external_event_count > 0`
- or `duplicate_event_count > 0`
- or `reconciliation_failure_count > 0`

Output:

- classification: `CONSISTENCY_ISSUE_CANDIDATE`
- severity: `SEV1`
- confidence: `0.85`

### Rule 5. Insufficient Evidence

Conditions:

- `manifest.json` missing
- or required PH2 evidence is too sparse

Output:

- classification: `INSUFFICIENT_EVIDENCE`
- severity: `SEV2`
- confidence: `0.4`

### Fallback. Unknown Incident

If no MVP rule matches:

- classification: `UNKNOWN_INCIDENT`
- severity: `SEV3`
- confidence: `0.3`

## 6. Rule Priority

Priority:

```text
1. ARTIFACT_SANITIZATION_RISK
2. CONSISTENCY_ISSUE_CANDIDATE
3. POSTGRES_DOWN_WRITE_SUSPENDED
4. WRITE_SUSPENDED_UNKNOWN_DEPENDENCY
5. INSUFFICIENT_EVIDENCE
6. UNKNOWN_INCIDENT
```

Reason:

- Sensitive artifact risk must block AI or external sharing first.
- Consistency issue candidates can imply financial impact and outrank dependency availability classification.
- PostgreSQL down/write suspend is the next highest operational classification.
- Sparse evidence lowers confidence and prevents recovery decisions from this report alone.

## 7. Severity And Confidence

| Classification | Severity | Confidence |
| --- | --- | --- |
| `ARTIFACT_SANITIZATION_RISK` | SEV2 | 0.8 |
| `CONSISTENCY_ISSUE_CANDIDATE` | SEV1 | 0.85 |
| `POSTGRES_DOWN_WRITE_SUSPENDED` | SEV1 | 0.9 |
| `WRITE_SUSPENDED_UNKNOWN_DEPENDENCY` | SEV2 | 0.65 |
| `INSUFFICIENT_EVIDENCE` | SEV2 | 0.4 |
| `UNKNOWN_INCIDENT` | SEV3 | 0.3 |

Severity and confidence are candidates for operator review.
They do not create recovery cases or approve write resume.

## 8. CLI And Makefile

Analyze an incident:

```bash
python scripts/ph3_incident_analyzer.py analyze \
  --incident-dir reports/incidents/inc-...
```

Analyze latest:

```bash
python scripts/ph3_incident_analyzer.py analyze --latest
```

Validate analyzer output:

```bash
python scripts/ph3_incident_analyzer.py validate --latest
```

Make targets:

```bash
make ph3-incident-analyze
make ph3-incident-analyze-validate
make ph3-db-down-incident-analysis
make ops11-incident-analyze
```

## 9. PH2 Artifact Connection

Recommended local flow:

```bash
make ph2-incident-artifact
make ph2-incident-artifact-validate
make ph3-incident-analyze
make ph3-incident-analyze-validate
```

DB-down drill flow:

```bash
make ph3-db-down-incident-analysis
```

This runs PH2 DB-down artifact creation first, then analyzes and validates the latest artifact.

## 10. Verification Criteria

Checks:

- `analyzer-result.json` exists
- `incident-analysis.md` exists
- `sensitive_data_included=false`
- `manual_review_required=true`
- PostgreSQL down artifact classifies as `POSTGRES_DOWN_WRITE_SUSPENDED`
- sanitization risk outranks consistency issue
- non-zero duplicate/reconciliation counts classify as `CONSISTENCY_ISSUE_CANDIDATE`
- analyzer output contains no raw idempotency key, raw account number, signature, Authorization header, or raw request body

Recommended commands:

```bash
make test-unit
make scripts-check
make security-log-check
make ph3-incident-analyze
make ph3-incident-analyze-validate
```

## 11. Troubleshooting Notes

- If `analyze --latest` fails with no incident directories, run `make ph2-incident-artifact` first.
- If PH2 validation reports sensitive data, PH3 classifies the artifact as `ARTIFACT_SANITIZATION_RISK`.
- If `manifest.json` is missing, PH3 writes `INSUFFICIENT_EVIDENCE` instead of guessing recovery actions.
- If output validation fails, regenerate analyzer output after fixing the PH2 artifact.

## 12. Limitations And Follow-up

Limitations:

- PH3 does not query live Prometheus metrics.
- PH3 does not read `raw/`.
- PH3 does not create recovery cases.
- PH3 does not execute recovery actions.
- PH3 does not approve write resume.
- PH3 does not call AI APIs.

Next step:

```text
PH-Impl 4: Recovery Case / Quarantine / Manual Approval
```
