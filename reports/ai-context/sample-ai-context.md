# PH6 AI-safe Context Report

## Summary

- Incident ID: inc-sample
- Run ID: ph6-sample
- Classification: STALE_PROCESSING_DETECTED
- Severity: SEV2
- Removed Field Count: 2
- Sensitive Data Included: false

## Boundaries

- AI context is generated from allowlisted fields only.
- Raw account numbers, raw idempotency keys, request bodies, signatures, authorization headers, and secrets are excluded.
- PH6 does not call external AI APIs or execute recovery actions.
