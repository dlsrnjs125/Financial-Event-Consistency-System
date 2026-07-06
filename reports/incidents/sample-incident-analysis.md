# Incident Analysis Draft

## Summary

- Classification: POSTGRES_DOWN_WRITE_SUSPENDED
- Severity Candidate: SEV1
- Confidence Candidate: 0.9
- Manual Review Required: true
- Sensitive Data Included: false

## Primary Signals

- classification=POSTGRES_DOWN_WRITE_SUSPENDED
- scenario=POSTGRES_DOWN
- write_suspend_state.active=true
- write_suspend_state.reason=postgres_unavailable
- ready_status=not_collected
- consistency_result=captured
- sensitive_data_included=false

## Why This Classification

Scenario and write-suspend evidence point to PostgreSQL write path unavailability.

## Observed Auto Actions

- sanitized_artifact_created
- ph2_validation_checked
- write_suspend_state_captured
- count_only_consistency_summary_captured

## Manual Actions Required

- confirm PostgreSQL recovery
- review consistency gate
- approve write resume
- decide whether recovery case creation is required in PH4

## Recommended Runbooks

- docs/runbooks/postgres-down.md
- docs/runbooks/write-suspend-resume.md

## Limits

- PH3 does not execute recovery actions
- PH3 does not approve write resume
- PH3 does not query live Prometheus metrics
- PH3 does not call AI APIs

## Follow-up

- PH4 Recovery Case / Quarantine
