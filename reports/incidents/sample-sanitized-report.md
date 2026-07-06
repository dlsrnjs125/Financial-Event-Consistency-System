# Incident Report Draft

## Incident Metadata

- Incident ID: inc-20260706-153000-postgres-down
- Scenario: POSTGRES_DOWN
- Severity Candidate: SEV1
- Confidence Candidate: 0.8
- Source: sample
- Run ID: ph1-db-down-sample
- Created At: 2026-07-06T15:30:00+09:00
- Manual Review Required: true
- Sensitive Data Included: false

## Summary

PostgreSQL write path was unavailable or write traffic was suspended.
Financial write requests were expected to fail closed with 503 + Retry-After.

## Primary Signals

- readiness: not_collected
- write_suspended: captured_if_state_file_exists
- retry_after_present: unknown
- consistency_check: not_collected

## Sanitization

- raw account number: not included
- raw idempotency key: not included
- HMAC signature: not included
- Authorization header: not included
- raw request body: not included
- sensitive_data_included: false
