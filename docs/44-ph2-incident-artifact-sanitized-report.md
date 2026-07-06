# PH2 Incident Artifact and Sanitized Report

## 1. PH2 Goal

PH2 adds an out-of-band incident artifact bundle for PostgreSQL down and write-suspend scenarios.
When PostgreSQL is unavailable, the system cannot immediately write `incident_events` or `recovery_cases` into the DB, so the first evidence must be stored outside PostgreSQL.

PH2 produces:

- `reports/incidents/{incident_id}/manifest.json`
- `sanitized-report.md`
- sanitized write-suspend state
- count-only consistency summary
- command result summary
- minimal Docker Compose status

## 2. PH1 Connection

PH1 prevents successful financial writes during PostgreSQL write-path failure by returning `503` with `Retry-After`.
PH2 builds on that by creating a sanitized artifact bundle that operators can inspect after a PH1 DB-down drill.

Use:

```bash
make ph2-db-down-incident-artifact
```

This target runs the PH1 DB-down drill, creates a PH2 incident artifact with the PH1 `RUN_ID`, and validates the latest artifact.

## 3. Scope And Non-Scope

Included:

- `scripts/ph2_incident_artifact.py`
- `create`, `sanitize`, and `validate` CLI commands
- allowlist-based sanitizer
- artifact manifest and sanitized report skeleton
- Makefile targets
- unit tests for sanitizer, manifest creation, validation, and latest selection

Excluded:

- `incident_events` DB table
- `recovery_cases` DB table
- full Incident Analyzer rule engine
- AI API calls
- latency attribution instrumentation
- PostgreSQL HA or durable queue
- raw log collection

## 4. Out-of-band Artifact Structure

Default path:

```text
reports/incidents/{incident_id}/
  manifest.json
  sanitized-report.md
  write-suspend-state.json
  health-ready-summary.json
  docker-compose-status.txt
  consistency-summary.json
  command-results.json
  raw/
    README.md
```

`raw/` is intentionally empty by default.
Real `inc-*` directories are ignored by git; commit only reviewed samples and templates.

## 5. Manifest Schema

Required fields:

```json
{
  "incident_id": "inc-20260706-153000-postgres-down",
  "scenario": "POSTGRES_DOWN",
  "severity_candidate": "SEV1",
  "confidence_candidate": 0.8,
  "created_at": "2026-07-06T15:30:00+09:00",
  "created_by": "ph2_incident_artifact",
  "source": "local_drill",
  "run_id": "ph1-db-down-20260706-153000",
  "sanitized": true,
  "sensitive_data_included": false,
  "manual_review_required": true,
  "evidence_files": [],
  "manual_required": []
}
```

`severity_candidate` and `confidence_candidate` are draft values for operator review.
PH2 does not make final severity decisions.

## 6. Sanitized Report Format

`sanitized-report.md` follows this structure:

- Incident metadata
- Summary
- Primary signals
- Auto actions captured
- Manual actions required
- Evidence files
- Sanitization statement
- Follow-up PH steps

Unknown values are written as `unknown` or `not_collected`.
The report must always state `Sensitive Data Included: false`.

## 7. Sanitization Policy

PH2 uses an allowlist, not a denylist.
Only explicitly allowed keys can enter JSON report artifacts.

Allowed examples:

- `incident_id`
- `scenario`
- `severity_candidate`
- `confidence_candidate`
- `created_at`
- `run_id`
- `source`
- `service_name`
- `container_name`
- `health_status`
- `ready_status`
- `http_status`
- `error_code`
- `retryable`
- `retry_after_seconds`
- `dependency`
- `result`
- `count`
- `duration_ms`
- `command_name`
- `exit_code`

Removed or redacted examples:

- raw account number
- raw idempotency key
- raw request or response body
- HMAC signature
- Authorization header
- client secret
- DB password
- raw `DATABASE_URL`
- cookie
- access token
- refresh token
- private key

PH2 does not store idempotency key hashes or suffixes by default.

## 8. CLI And Makefile

Create a standalone artifact:

```bash
python scripts/ph2_incident_artifact.py create \
  --scenario POSTGRES_DOWN \
  --source manual
```

Sanitize a JSON payload:

```bash
python scripts/ph2_incident_artifact.py sanitize \
  --input /tmp/input.json \
  --output /tmp/sanitized.json
```

Validate an artifact:

```bash
python scripts/ph2_incident_artifact.py validate \
  --incident-dir reports/incidents/inc-...
```

Validate the latest artifact:

```bash
make ph2-incident-artifact-validate
```

Make targets:

```bash
make ph2-incident-artifact
make ph2-incident-artifact-validate
make ph2-db-down-incident-artifact
make ops10-incident-artifact
```

## 9. PH1 DB-down Drill Connection

`make ph2-db-down-incident-artifact` keeps PH1 verification intact and then creates the PH2 bundle.
PH2 reads the PH1 report only for count-only summaries such as duplicate event and ledger counts.
It does not copy raw request bodies, raw headers, or PH1 response bodies into the incident bundle.

## 10. Verification Criteria

Checks:

- `manifest.json` has required fields
- `sanitized-report.md` exists
- `sensitive_data_included=false`
- manifest and report incident IDs match
- allowlisted fields survive sanitization
- sensitive keys are removed
- validation passes for a normal artifact
- validation fails when sensitive keys or synthetic sensitive values are inserted
- latest validation selects the newest `inc-*` directory

Recommended commands:

```bash
make test-unit
make scripts-check
make security-log-check
make ph2-incident-artifact
make ph2-incident-artifact-validate
```

Docker-dependent drill:

```bash
make ph2-db-down-incident-artifact
```

## 11. Troubleshooting Notes

- If `validate --latest` fails with no incident directories, run `make ph2-incident-artifact` first.
- If validation reports a sensitive key, inspect generated JSON files and remove the raw field at the source.
- If Docker Compose status is `not_collected`, Docker was unavailable or the stack was not running. This does not invalidate the standalone artifact.
- Real `reports/incidents/inc-*` directories are local runtime evidence and should not be committed.

## 12. Limitations And Follow-up

Limitations:

- PH2 does not classify incidents beyond draft severity/confidence candidates.
- PH2 does not backfill PostgreSQL `incident_events` or `recovery_cases`.
- PH2 does not collect raw logs by default.
- PH2 does not call AI APIs.

Next step:

```text
PH-Impl 3: Incident Analyzer MVP
```
