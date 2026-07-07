# PH7 Partner Secret Rotation & HMAC Hardening

## 1. Goal

PH7 implements a version-based partner HMAC verification contract for external financial event writes.

The goal is to verify `current`, `previous`, `next`, `revoked`, and `disabled` secret states without storing raw secrets, raw signatures, Authorization headers, or raw request bodies in logs, reports, tests, or AI context.

## 2. Problem

Single-secret HMAC verification is brittle during rotation.

If only one secret is accepted, a partner deployment race can reject valid retry traffic. If two secrets are accepted forever, rotation becomes a permanent dual-secret state. PH7 defines a bounded rotation policy and leaves final key retirement to human approval.

## 3. Scope and Non-Scope

Scope:

- version-based HMAC verifier
- `current`, `previous`, `next`, `revoked`, and `disabled` secret-state decisions
- timestamp skew validation
- required nonce validation
- sanitized rotation drill report
- Makefile commands
- unit tests and verifier-level smoke test

Non-scope:

- Vault, KMS, or Secret Manager integration
- actual partner secret replacement operation
- automated production key retirement
- DB column encryption
- mandatory Redis nonce store
- real external partner communication
- AI-driven recovery execution

## 4. Request Authentication Contract

Partner HMAC is opt-in for the financial event write API.

```text
ENABLE_PARTNER_HMAC_AUTH=false
ENABLE_PARTNER_HMAC_AUTH=true
```

Config-based registry entries use pipe separators so ISO timestamps can keep their `:` characters:

```text
PARTNER_HMAC_SECRETS=client_id|key_id|status|dummy_value|previous_valid_until_iso|enabled
```

When enabled, the request must include:

```text
X-Client-Id
X-Key-Id
X-Timestamp
X-Nonce
X-Signature
```

The existing single-secret HMAC path remains available for compatibility when partner rotation auth is disabled.
When partner auth is enabled, `PARTNER_HMAC_SECRETS` must contain at least one valid entry; otherwise the dependency fails fast with a configuration error.

## 5. Canonical Request and Signature

PH7 signs the path without query string and rejects partner HMAC write requests that contain a query string.
Financial event writes are body-contract based in this project, so query parameters are not accepted on this authenticated write path.

```text
{method}
{path}
{timestamp}
{nonce}
{body_sha256}
```

Signature:

```text
hex(hmac_sha256(secret, canonical_request))
```

Verification uses constant-time comparison with `hmac.compare_digest`.

The canonical request itself can reveal request metadata, so reports store only `canonical_request_hash` and `body_hash`.

## 6. Secret Version Lifecycle

| Status | Meaning | Default Verification |
| --- | --- | --- |
| `next` | staged secret before rollout | rejected on write API; accepted only by verifier/drill dry-run |
| `current` | active signing secret | accepted |
| `previous` | old secret during rotation grace window | accepted only inside window |
| `revoked` | immediately blocked secret | rejected |
| `disabled` | disabled client/key state | rejected |

## 7. Rotation Window Policy

`previous` is accepted only until `previous_valid_until`.

After the window expires, the request is rejected with `previous_expired`. This keeps rotation bounded and prevents permanent dual-secret operation.

`next` is accepted only when `allow_next_for_dry_run=true` in verifier-level drill/demo code.
The actual financial event write API always passes `allow_next_for_dry_run=false`, even if the environment has a dry-run flag.
An API-level dry-run must be a separate no-write endpoint before `next` can be exposed through HTTP.

## 8. Replay Defense Boundary

Implemented:

- `X-Timestamp` skew validation
- required `X-Nonce`
- report field `nonce_persistence=follow_up_candidate`

Deferred:

- persistent nonce replay store
- Redis-backed nonce TTL enforcement
- duplicate nonce rejection across API instances

PH7 does not fail open on missing nonce. Missing nonce is rejected because it leaves replay risk.

## 9. Failure Decision Matrix

| Case | Result | Reason |
| --- | --- | --- |
| current secret + valid signature | ACCEPT | active version |
| previous secret + inside rotation window | ACCEPT | grace window |
| previous secret + expired window | REJECT | previous expired |
| next secret without dry-run | REJECT | staged key not active |
| next secret with verifier/drill dry-run | ACCEPT | staged verification only |
| next secret on write API | REJECT | staged key must not write |
| query string on partner write API | REJECT | unsigned request component not allowed |
| revoked secret | REJECT | revoked key |
| disabled client | REJECT | disabled client |
| unknown client | REJECT | unknown client |
| unknown key id | REJECT | unknown key |
| missing nonce | REJECT | replay risk |
| timestamp skew exceeded | REJECT | replay risk |
| invalid signature | REJECT | integrity/auth failure |

## 10. CLI and Makefile

CLI:

```bash
python3 scripts/ph7_hmac_rotation_drill.py demo
python3 scripts/ph7_hmac_rotation_drill.py validate --input reports/security/ph7-hmac-rotation/sample-hmac-rotation-report.json
python3 scripts/ph7_hmac_rotation_drill.py smoke
```

Makefile:

```bash
make ph7-hmac-rotation-demo
make ph7-hmac-rotation-validate
make ph7-hmac-rotation-smoke
make ph7-security-check
```

## 11. Sanitized Evidence Report

Curated sample:

```text
reports/security/ph7-hmac-rotation/sample-hmac-rotation-report.json
reports/security/ph7-hmac-rotation/sample-hmac-rotation-report.md
```

Allowed evidence:

- `client_token`
- `client_status`
- `key_id`
- `key_version`
- `secret_status`
- `request_case`
- `expected_result`
- `actual_result`
- `decision`
- `decision_reason`
- `timestamp_skew_seconds`
- `nonce_present`
- `canonical_request_hash`
- `body_hash`
- `signature_present`
- `signature_algorithm`
- `rotation_window_status`
- `raw_secret_included=false`
- `raw_signature_included=false`
- `raw_body_included=false`

Forbidden evidence:

- raw secret
- raw signature
- Authorization header
- raw request body
- client secret
- access token
- refresh token
- cookie / set-cookie
- database URL

`client_token` is an internal evidence token, not public anonymization. Low-entropy client IDs can still be dictionary-tested, so public sharing should use an additional report salt or HMAC tokenization step.

## 12. Test and Verification Criteria

Unit tests cover:

- current secret success
- previous secret inside window success
- previous secret expired rejection
- revoked secret rejection
- disabled client rejection
- unknown client/key rejection
- missing/invalid signature rejection
- missing nonce rejection
- timestamp skew rejection
- body tampering rejection
- deterministic canonical request
- no raw secret/signature in result object
- `hmac.compare_digest` usage

Operational checks:

```bash
make ph7-hmac-rotation-demo
make ph7-hmac-rotation-validate
make ph7-hmac-rotation-smoke
make ph7-security-check
```

## 13. Troubleshooting Notes

### Raw Signature In Evidence

- 문제: raw signature를 report에 넣으면 evidence 자체가 유출 경로가 된다.
- 원인: 인증 실패 원인을 자세히 남기려다 provided signature를 그대로 저장할 수 있다.
- 해결: report에는 `signature_present`, `body_hash`, `canonical_request_hash`만 남긴다.
- 검증: `ph7_hmac_rotation_drill.py validate`가 raw signature/body/secret 후보를 검사한다.
- README에 넣지 않은 이유: README는 요약과 링크만 유지하고, 보안 evidence 세부 정책은 이 문서에서 관리한다.

### Previous Secret Is Too Permissive

- 문제: `previous` secret을 무기한 허용하면 rotation이 아니라 permanent dual-secret 상태가 된다.
- 원인: grace window 종료 조건이 없으면 old key retirement가 검증되지 않는다.
- 해결: `previous_valid_until` 이후에는 `previous_expired`로 거부한다.
- 검증: `test_previous_secret_outside_window_fails`와 sample report의 `previous_secret_expired_reject`로 확인한다.
- README에 넣지 않은 이유: rotation lifecycle의 세부 정책이므로 docs에 둔다.

### Next Secret Becomes Active Too Early

- 문제: `next` secret을 실제 write API에서 허용하면 아직 배포 승인 전인 key가 실서비스에서 활성화된다.
- 원인: staged verification과 active write verification을 구분하지 않으면 rollout 전 secret이 상태 변경 요청에 사용 가능해진다.
- 해결: write API dependency는 항상 `allow_next_for_dry_run=false`로 verifier를 호출하고, `next` 성공은 drill/demo에서만 검증한다.
- 검증: `test_partner_dependency_never_accepts_next_key_on_write_api`, `test_next_secret_requires_dry_run_flag`, `next_secret_dry_run_success` case로 확인한다.
- README에 넣지 않은 이유: dry-run 경계는 운영 상세 정책이므로 docs에 둔다.

### Timestamp Without Nonce

- 문제: timestamp만 검증하면 같은 window 안의 재전송 위험이 남는다.
- 원인: nonce persistence는 아직 후속 구현 후보지만, nonce 자체를 요구하지 않으면 replay defense 계약이 약해진다.
- 해결: `X-Nonce`를 필수 헤더로 요구하고 missing nonce를 reject한다.
- 검증: `test_missing_nonce_and_timestamp_skew_fail`와 `missing_nonce_reject` case로 확인한다.
- README에 넣지 않은 이유: replay defense boundary는 상세 보안 설계에 가깝다.

### Timing-Safe Signature Compare

- 문제: 일반 문자열 비교는 timing side-channel 가능성을 만든다.
- 원인: signature mismatch 위치에 따라 비교 시간이 달라질 수 있다.
- 해결: `hmac.compare_digest`를 사용한다.
- 검증: `test_partner_verifier_uses_constant_time_compare`가 compare function 호출을 확인한다.
- README에 넣지 않은 이유: 구현 세부 보안 검증은 테스트와 docs에서 관리한다.

## 14. Limits and Next Steps

- Partner secrets are config/in-memory based in PH7.
- Real Vault/KMS/Secret Manager integration is a later production integration step.
- Persistent nonce storage is a follow-up candidate.
- Secret retirement and external partner communication remain human-approved operations.
- PH6 AI-safe context can ingest PH7 reports only after the same raw secret/signature/body exclusion rule is preserved.
