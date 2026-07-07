# PH6 AI-safe Context Sanitizer

## 1. Goal

PH6 creates AI-safe operational context from PH2 incident artifacts, PH3 analyzer output, PH4 recovery case evidence, and PH5 reconciliation reports.

The sanitizer uses an allowlist-first policy. Unknown fields are removed by default, and denylist checks remain only as a backup safety net.

PH6 does not call external AI APIs, execute recovery actions, update account balances, create compensation ledger entries, approve write resume, or run secret rotation.

## 2. PH2~PH5 Connection

- PH2 creates out-of-band sanitized incident artifacts.
- PH3 turns PH2 artifacts into deterministic analyzer results.
- PH4 links analyzer results to recovery cases and quarantine records under manual approval.
- PH5 detects stale `PROCESSING` and count-only reconciliation issues.
- PH6 converts these evidence sources into a smaller AI-safe context before any external analysis or AI-assisted summary.

## 3. Scope And Non-Scope

Included:

- `backend/app/security/ai_context_sanitizer.py`
- allowlist-based nested dict/list sanitizer
- redaction summary with field paths and reasons only
- sensitive key and value pattern validation
- `scripts/ph6_ai_context.py`
- curated sample artifacts under `reports/ai-context/`
- Makefile targets and unit tests

Excluded:

- OpenAI, Claude, Gemini, or other external AI API calls
- automatic recovery execution
- compensation ledger creation
- account balance correction
- write resume approval
- Slack/PagerDuty integration
- KMS, Vault Transit, DB encryption, or partner secret rotation implementation

## 4. Data Classification

| Level | Examples | PH6 Policy |
| --- | --- | --- |
| Level 0 | raw account number, raw idempotency key, raw request body, Authorization, HMAC signature, client secret | prohibited |
| Level 1 | masked account number, masked idempotency key, masked client id | conditionally allowed only for operator traceability |
| Level 2 | account_token, event_token, idempotency_key_hash, request_hash | allowed when needed |
| Level 3 | consistency counts, metric summaries, severity/classification/status | preferred |

PH6 context should mostly contain Level 2~3 data.

## 5. Allowlist Sanitizing Policy

Allowed examples:

- `incident_id`
- `run_id`
- `classification`
- `severity`
- `confidence`
- `status`
- `case_type`
- `target_type`
- `account_token`
- `event_token`
- `idempotency_key_hash`
- `masked_target_id`
- `request_hash`
- `consistency_counts`
- `metric_summary`
- `manual_action_candidates`
- `approval_required`
- `runbook_reference`
- `evidence_paths`

Unknown fields are removed with `reason=not_in_allowlist`.
Sensitive field names are removed with `reason=sensitive_field_name`.
Allowed field names with unsafe values are removed with `reason=sensitive_value_pattern`.

The redaction summary never stores removed raw values.

## 6. Prohibited Fields And Patterns

Prohibited fields include:

- `account_no`
- `raw_account_no`
- `idempotency_key`
- `raw_idempotency_key`
- `request_body`
- `raw_request_body`
- `response_body`
- `authorization`
- `hmac_signature`
- `signature`
- `client_secret`
- `secret`
- `password`
- `token`
- `access_token`
- `refresh_token`
- `api_key`
- `db_url`
- `database_url`
- `connection_string`
- `cookie`
- `set_cookie`

Allowed exceptions are explicit and narrow: `account_token`, `event_token`, `idempotency_key_hash`, and `request_hash`.

Sensitive value patterns include authorization-like strings, HMAC/signature strings, raw account number patterns, database connection strings, raw JSON body strings, and long opaque secret candidates outside approved token/hash fields.

## 7. CLI And Makefile

CLI:

```bash
python3 scripts/ph6_ai_context.py demo
python3 scripts/ph6_ai_context.py validate --input reports/ai-context/sample-ai-context.json
python3 scripts/ph6_ai_context.py sanitize --input reports/incidents/sample-analyzer-result.json
python3 scripts/ph6_ai_context.py sanitize-latest --source incidents
python3 scripts/ph6_ai_context.py sanitize-latest --source recovery-cases
python3 scripts/ph6_ai_context.py sanitize-latest --source reconciliation
```

Makefile:

```bash
make ph6-ai-context-demo
make ph6-ai-context-validate
make ph6-ai-context-sanitize-latest
make ph6-ai-context-sanitize-latest-recovery-case
```

## 8. Report Artifact Structure

Runtime artifacts:

```text
reports/ai-context/{run_id}/
  context.json
  context.md
```

Curated samples:

```text
reports/ai-context/README.md
reports/ai-context/sample-ai-context.json
reports/ai-context/sample-ai-context.md
```

Runtime `run-*` directories are ignored by git.

## 9. Verification Criteria

- allowlisted fields are preserved
- unknown fields are removed
- nested dict/list sensitive fields are removed
- raw values do not appear in redaction summary
- `account_token`, `event_token`, `idempotency_key_hash`, and `request_hash` are allowed
- raw account number, raw idempotency key, Authorization, signature, secret, and raw body fields are rejected
- `demo` generates deterministic AI-safe context
- `validate` fails nonzero if a prohibited field or sensitive pattern remains

## 10. Troubleshooting Notes

### Denylist-only Sanitizing Is Not Enough

- Problem: new fields can be added to incident or reconciliation artifacts.
- Cause: a denylist-only sanitizer can miss newly introduced sensitive fields.
- Fix: PH6 outputs only allowlisted keys and treats unknown fields as `not_in_allowlist`.
- Verification: `test_unknown_fields_are_removed` checks that unlisted fields are removed.

### Token Is Too Broad As A Deny Rule

- Problem: blocking every field containing `token` removes safe pseudonymous identifiers such as `account_token` and `event_token`.
- Cause: denylist regex cannot distinguish safe pseudonymous identifiers from access tokens by name alone.
- Fix: PH6 evaluates the allowlist first and explicitly allows `account_token`, `event_token`, `idempotency_key_hash`, and `request_hash`.
- Verification: `test_tokens_and_hashes_are_allowed` confirms safe token/hash fields are preserved.

### Nested Structures Can Hide Unsafe Fields

- Problem: incident and reconciliation artifacts can contain lists of signals or nested count summaries.
- Cause: shallow sanitizing can leave unsafe fields inside nested dict/list values.
- Fix: PH6 recursively sanitizes nested dict/list structures.
- Verification: `test_nested_sensitive_fields_are_removed_without_dropping_safe_siblings` confirms nested sensitive fields are removed while safe siblings remain.

### Redaction Summary Can Leak Data

- Problem: a redaction summary can become another leak path if it records removed raw values.
- Cause: removed values may include request bodies, credentials, signatures, or raw identifiers.
- Fix: PH6 stores only field paths and reasons in `redaction_summary`.
- Verification: `test_redaction_summary_does_not_include_raw_values` checks that raw values are absent from the summary.

### Runtime Artifacts Should Not Be Committed

- Problem: generated runtime context files can be environment-specific.
- Cause: `demo` and `sanitize-latest` write timestamped `run-*` directories.
- Fix: `reports/ai-context/run-*/` is ignored and only curated samples are committed.
- Verification: `git status --ignored --short reports/ai-context` shows runtime directories as ignored.

## 11. Limits And Next Steps

PH6 is a context preparation layer, not an AI integration.
The next hardening step is partner secret rotation and HMAC hardening design/implementation.
