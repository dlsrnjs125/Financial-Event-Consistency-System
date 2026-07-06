# PH4 Recovery Case, Quarantine, and Manual Approval

## Goal

PH4 turns PH3 analyzer output into an operator-reviewable recovery case and optional quarantine record.

Automation stops at:

- creating a recovery case
- linking sanitized evidence
- quarantining an affected target when the analyzer reports a consistency risk candidate
- waiting for manual approval before any recovery action can move to execution

PH4 does not create compensation ledger entries, update balances directly, resume writes, call AI APIs, or notify Slack/PagerDuty.

## Data Model

PH4 adds:

- `recovery_cases`
- `quarantine_records`

`recovery_cases.source_key` is unique and acts as the duplicate guard for repeated analyzer ingestion. The source key format is:

```text
{source_incident_id}:{case_type}:{target_type}:{target_id}:{external_event_id_or_unknown}
```

Sensitive raw values are not stored. Raw account numbers, raw `Idempotency-Key` values, request bodies, HMAC signatures, authorization headers, and secrets remain prohibited.

## Lifecycle

Recovery case statuses:

```text
OPEN -> AUTO_ANALYZED -> WAITING_APPROVAL -> APPROVED -> EXECUTING -> EXECUTED -> CLOSED
```

Failure and rejection paths:

```text
WAITING_APPROVAL -> REJECTED -> CLOSED
EXECUTING -> EXECUTION_FAILED -> WAITING_APPROVAL
```

Execution guard:

- only `APPROVED` can move to `EXECUTING`
- `approved_by` is required before execution
- `EXECUTING` assigns a stable `action_attempt_id`
- `EXECUTED`, `REJECTED`, and `CLOSED` cannot be executed again

## Quarantine Guard

The transaction write path checks account quarantine after account lookup and row lock.

Current limitation:

- account quarantine is enforced after resolving `account_no` to internal `account.id`
- client/event/global quarantine records are managed as operational evidence and future extension points
- PH1 global write suspend remains the first guard for system-wide PostgreSQL risk

When an account is actively quarantined, the write path returns a domain failure with `TargetQuarantined` and does not include raw account identifiers in the response.

## CLI

```bash
python3 scripts/ph4_recovery_case.py create-from-analysis --latest
python3 scripts/ph4_recovery_case.py list-cases
python3 scripts/ph4_recovery_case.py approve --case-id rc-... --approved-by operator-a --reason "reviewed"
python3 scripts/ph4_recovery_case.py quarantine --target-type ACCOUNT --target-id 123 --reason "manual review"
python3 scripts/ph4_recovery_case.py release-quarantine --quarantine-id qr-... --released-by operator-a --reason "review complete"
```

Makefile shortcuts:

```bash
make ph4-recovery-case-from-latest
make ph4-recovery-cases
make ph4-quarantines
```

## API

PH4 exposes read-only endpoints:

```text
GET /api/v1/recovery-cases
GET /api/v1/recovery-cases/{case_id}
GET /api/v1/quarantines
GET /api/v1/quarantines/{quarantine_id}
```

Approval, rejection, and quarantine release stay CLI-only in this phase.

## Troubleshooting

### Analyzer Result Rejected

If `sensitive_data_included` is not `false`, PH4 refuses to create a recovery case. Regenerate the PH2/PH3 artifact after removing unsafe evidence.

### Duplicate Create Returns Existing Case

Repeated `create-from-analysis` calls for the same source key return the existing case. This is expected and protects against duplicate recovery work.

### Quarantine Blocks Writes

An active `ACCOUNT` quarantine blocks new transaction writes for that internal account id. Release it only after manual review and reconciliation evidence are complete.
