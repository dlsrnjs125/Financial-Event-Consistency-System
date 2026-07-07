# PH5 Stale PROCESSING Detector and Reconciliation

## 1. PH5 Goal

PH5 detects stale `PROCESSING` idempotency records and count-only consistency issues after a failure window.
It links findings to PH4 recovery cases and writes sanitized evidence under `reports/reconciliation/{run_id}/`.

PH5 does not complete or fail stale records automatically, update account balances, create compensation ledger entries, resume writes, call AI APIs, or execute recovery actions.

## 2. PH1 To PH4 Connection

- PH1 blocks new financial writes when PostgreSQL write path is unavailable.
- PH2 captures out-of-band incident evidence.
- PH3 classifies sanitized incident artifacts.
- PH4 creates recovery cases and quarantine records under manual approval guard.
- PH5 runs after DB recovery to find unresolved stale or consistency candidates and connect them to recovery cases.

## 3. Scope And Non-Scope

Included:

- stale `PROCESSING` detector
- count-only reconciliation
- recovery case creation through PH4 service
- optional global quarantine for high-risk reconciliation issue types
- sanitized report artifact generation and validation
- CLI and Makefile targets

Excluded:

- automatic stale completion or failure
- balance correction
- compensation ledger generation
- recovery action execution
- write resume approval
- AI, Slack/PagerDuty, HA/failover, durable queue, latency instrumentation

## 4. Stale PROCESSING Detector

Candidate condition:

```text
idempotency_records.status = PROCESSING
and (
  locked_until is expired
  or updated_at is older than threshold
)
```

The default threshold is 5 minutes and can be overridden by CLI.
PH5 stores only safe identifiers such as `idempotency_record_id` and `idempotency_key_hash`.

Mapping:

- `case_type=STALE_PROCESSING`
- `classification=STALE_PROCESSING_DETECTED`
- `approval_required=true`
- `source_key=ph5:stale:{idempotency_record_id}`

If a matching transaction event and ledger entry exist, PH5 proposes `MARK_COMPLETED` only as a manual-review candidate.
Otherwise it proposes `MARK_FAILED_RETRYABLE`.

## 5. Reconciliation Job

PH5 count-only checks:

- duplicate ledger count
- duplicate external event count
- completed idempotency without transaction event count
- transaction event without ledger count
- ledger without transaction event count
- account balance mismatch count
- stale PROCESSING count

PH5 does not read raw request bodies and does not output raw account numbers or raw idempotency keys.

## 6. Recovery Case Linking

Reconciliation issue mapping:

| Issue | Recovery Case Type | Proposed Action |
| --- | --- | --- |
| duplicate ledger | `DUPLICATE_LEDGER` | `KEEP_QUARANTINED` |
| account balance mismatch | `BALANCE_MISMATCH` | `KEEP_QUARANTINED` |
| completed idempotency without transaction event | `ORPHAN_IDEMPOTENCY` | `NOOP_REVIEW_ONLY` |
| transaction event without ledger | `FAILOVER_IN_DOUBT` | `KEEP_QUARANTINED` |
| ledger without transaction event | `CONSISTENCY_ISSUE_CANDIDATE` | `KEEP_QUARANTINED` |

PH4 `source_key` uniqueness prevents duplicate recovery case creation on rerun.

## 7. Report Artifact Structure

```text
reports/reconciliation/{run_id}/
  reconciliation-summary.json
  stale-processing-summary.json
  recovery-case-links.json
  consistency-counts.json
  ph5-report.md
```

Runtime `run-*` directories are ignored by git.
Curated examples live in `reports/reconciliation/`.

## 8. CLI And Makefile

```bash
python3 scripts/ph5_reconciliation.py detect-stale --threshold-minutes 5
python3 scripts/ph5_reconciliation.py reconcile --threshold-minutes 5
python3 scripts/ph5_reconciliation.py run --threshold-minutes 5
python3 scripts/ph5_reconciliation.py validate --latest
```

Makefile:

```bash
make ph5-detect-stale-processing
make ph5-reconcile
make ph5-reconciliation-run
make ph5-reconciliation-validate
```

## 9. Verification Criteria

- stale `PROCESSING` records are detected
- fresh `PROCESSING` records are excluded
- `COMPLETED` and `FAILED` records are excluded from stale detection
- recovery case creation is idempotent by source key
- count-only reconciliation emits issue counts
- report artifacts validate
- report artifacts do not contain raw sensitive values

## 10. Troubleshooting Notes

### DB Unavailable

PH5 requires PostgreSQL because it reconciles DB-backed state.
If the DB is unavailable, run PH1 write suspend and PH2/PH3 incident artifact/analyzer flow first.

### Existing Nonzero Account Balance

PH5 balance mismatch uses `account.balance != sum(ledger_entries.amount)`.
If accounts can start with an opening balance outside ledger history, model an opening ledger entry or review the mismatch manually before taking action.

### Repeated Runs Create No Duplicate Cases

Repeated PH5 runs reuse PH4 recovery cases by `source_key`.
This is expected and keeps recovery review idempotent.

## 11. Limits And Next Steps

PH5 is detection and evidence only.
Execution of recovery actions, compensation ledger creation, automatic stale resolution, and AI-safe context generation are future scopes.
