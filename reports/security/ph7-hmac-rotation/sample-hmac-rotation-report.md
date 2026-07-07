# PH7 HMAC Rotation Drill Report

- Run ID: `ph7-hmac-rotation-sample`
- Generated at: `2026-07-07T00:00:00+00:00`
- Sensitive data included: `False`
- Nonce persistence: `follow_up_candidate`

| Case | Result | Reason | Secret Status | Window |
| --- | --- | --- | --- | --- |
| current_secret_success | ACCEPT | current_secret | current | not_applicable |
| previous_secret_inside_window_success | ACCEPT | previous_grace_window | previous | active |
| previous_secret_expired_reject | REJECT | previous_expired | previous | expired |
| revoked_secret_reject | REJECT | revoked_key | revoked | not_applicable |
| disabled_client_reject | REJECT | disabled_client | disabled | not_applicable |
| timestamp_skew_reject | REJECT | timestamp_skew_exceeded | unknown | not_applicable |
| missing_nonce_reject | REJECT | missing_nonce | unknown | not_applicable |
| invalid_signature_reject | REJECT | invalid_signature | current | not_applicable |
| next_secret_dry_run_success | ACCEPT | next_dry_run | next | dry_run_only |

Raw secret, raw signature, Authorization header, and raw request body are not included.
