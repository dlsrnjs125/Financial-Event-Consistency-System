"""Unit tests for PH7 partner HMAC secret rotation."""

import hmac as stdlib_hmac
from datetime import UTC, datetime, timedelta

from app.security import partner_hmac as partner_hmac_module
from app.security.partner_hmac import (
    PartnerSecret,
    PartnerSecretRegistry,
    SecretStatus,
    build_partner_canonical_request,
    generate_partner_hmac_signature,
    verify_partner_hmac_request,
)

NOW = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
PATH = "/api/v1/transaction-events"
BODY = b'{"amount":1000,"currency":"KRW"}'
TIMESTAMP = NOW.isoformat()
NONCE = "nonce-001"
CLIENT_ID = "bank-a"


def registry() -> PartnerSecretRegistry:
    return PartnerSecretRegistry(
        [
            PartnerSecret(
                client_id=CLIENT_ID,
                key_id="key-current",
                secret="demo-current-value",
                status=SecretStatus.CURRENT,
            ),
            PartnerSecret(
                client_id=CLIENT_ID,
                key_id="key-previous",
                secret="demo-previous-value",
                status=SecretStatus.PREVIOUS,
                previous_valid_until=NOW + timedelta(minutes=5),
            ),
            PartnerSecret(
                client_id=CLIENT_ID,
                key_id="key-previous-expired",
                secret="demo-expired-previous-value",
                status=SecretStatus.PREVIOUS,
                previous_valid_until=NOW - timedelta(seconds=1),
            ),
            PartnerSecret(
                client_id=CLIENT_ID,
                key_id="key-revoked",
                secret="demo-revoked-value",
                status=SecretStatus.REVOKED,
            ),
            PartnerSecret(
                client_id=CLIENT_ID,
                key_id="key-next",
                secret="demo-next-value",
                status=SecretStatus.NEXT,
            ),
            PartnerSecret(
                client_id="bank-disabled",
                key_id="key-current",
                secret="demo-disabled-value",
                status=SecretStatus.DISABLED,
                client_enabled=False,
            ),
        ]
    )


def signed_result(
    *,
    key_id: str = "key-current",
    secret: str = "demo-current-value",
    client_id: str = CLIENT_ID,
    timestamp: str = TIMESTAMP,
    nonce: str = NONCE,
    body: bytes = BODY,
    signature: str | None = None,
    allow_next_for_dry_run: bool = False,
):
    canonical = build_partner_canonical_request(
        "POST",
        PATH,
        timestamp,
        nonce,
        body,
    )
    return verify_partner_hmac_request(
        registry=registry(),
        method="POST",
        path=PATH,
        timestamp=timestamp,
        nonce=nonce,
        raw_body=body,
        client_id=client_id,
        key_id=key_id,
        signature=(
            generate_partner_hmac_signature(secret, canonical)
            if signature is None
            else signature
        ),
        now=NOW,
        allowed_skew_seconds=300,
        allow_next_for_dry_run=allow_next_for_dry_run,
    )


def test_current_secret_request_succeeds():
    result = signed_result()

    assert result.accepted is True
    assert result.decision_reason == "current_secret"


def test_registry_from_config_supports_pipe_delimited_previous_window():
    raw_config = (
        "bank-a|key-previous|previous|demo-previous-value|"
        "2026-07-07T00:05:00+00:00|true"
    )

    parsed_registry = PartnerSecretRegistry.from_config(raw_config)
    secret = parsed_registry.get("bank-a", "key-previous")

    assert secret is not None
    assert secret.status == SecretStatus.PREVIOUS
    assert secret.previous_valid_until == NOW + timedelta(minutes=5)


def test_previous_secret_inside_window_succeeds():
    result = signed_result(key_id="key-previous", secret="demo-previous-value")

    assert result.accepted is True
    assert result.decision_reason == "previous_grace_window"
    assert result.rotation_window_status == "active"


def test_previous_secret_outside_window_fails():
    result = signed_result(
        key_id="key-previous-expired",
        secret="demo-expired-previous-value",
    )

    assert result.accepted is False
    assert result.decision_reason == "previous_expired"
    assert result.rotation_window_status == "expired"


def test_revoked_secret_fails():
    result = signed_result(key_id="key-revoked", secret="demo-revoked-value")

    assert result.accepted is False
    assert result.decision_reason == "revoked_key"


def test_disabled_client_fails():
    result = signed_result(
        key_id="key-current",
        secret="demo-disabled-value",
        client_id="bank-disabled",
    )

    assert result.accepted is False
    assert result.decision_reason == "disabled_client"


def test_unknown_client_and_unknown_key_fail():
    unknown_client = signed_result(client_id="unknown-client")
    unknown_key = signed_result(key_id="unknown-key")

    assert unknown_client.accepted is False
    assert unknown_client.decision_reason == "unknown_client"
    assert unknown_key.accepted is False
    assert unknown_key.decision_reason == "unknown_key"


def test_missing_and_invalid_signature_fail():
    missing = signed_result(signature="")
    invalid = signed_result(signature="f" * 64)

    assert missing.accepted is False
    assert missing.decision_reason == "missing_signature"
    assert invalid.accepted is False
    assert invalid.decision_reason == "invalid_signature"


def test_missing_nonce_and_timestamp_skew_fail():
    missing_nonce = signed_result(nonce="")
    old_timestamp = (NOW - timedelta(minutes=10)).isoformat()
    skewed = signed_result(timestamp=old_timestamp)

    assert missing_nonce.accepted is False
    assert missing_nonce.decision_reason == "missing_nonce"
    assert skewed.accepted is False
    assert skewed.decision_reason == "timestamp_skew_exceeded"


def test_body_hash_mutation_fails_signature_verification():
    canonical = build_partner_canonical_request("POST", PATH, TIMESTAMP, NONCE, BODY)
    signature = generate_partner_hmac_signature("demo-current-value", canonical)

    result = signed_result(
        body=b'{"amount":2000,"currency":"KRW"}', signature=signature
    )

    assert result.accepted is False
    assert result.decision_reason == "invalid_signature"


def test_next_secret_requires_dry_run_flag():
    blocked = signed_result(key_id="key-next", secret="demo-next-value")
    allowed = signed_result(
        key_id="key-next",
        secret="demo-next-value",
        allow_next_for_dry_run=True,
    )

    assert blocked.accepted is False
    assert blocked.decision_reason == "next_not_allowed"
    assert allowed.accepted is True
    assert allowed.decision_reason == "next_dry_run"


def test_canonical_request_is_deterministic_and_uses_raw_body_hash():
    first = build_partner_canonical_request("post", PATH, TIMESTAMP, NONCE, BODY)
    second = build_partner_canonical_request("POST", PATH, TIMESTAMP, NONCE, BODY)
    reordered_body = b'{"currency":"KRW","amount":1000}'
    different = build_partner_canonical_request(
        "POST", PATH, TIMESTAMP, NONCE, reordered_body
    )

    assert first == second
    assert first != different
    assert first.splitlines()[:4] == ["POST", PATH, TIMESTAMP, NONCE]


def test_result_does_not_include_raw_secret_or_signature():
    raw_signature = generate_partner_hmac_signature(
        "demo-current-value",
        build_partner_canonical_request("POST", PATH, TIMESTAMP, NONCE, BODY),
    )

    report = signed_result(signature=raw_signature).to_report_dict()
    rendered = repr(report)

    assert "demo-current-value" not in rendered
    assert raw_signature not in rendered
    assert report["raw_secret_included"] is False
    assert report["raw_signature_included"] is False
    assert report["raw_body_included"] is False


def test_partner_verifier_uses_constant_time_compare(monkeypatch):
    called = {"value": False}
    original_compare_digest = stdlib_hmac.compare_digest

    def fake_compare_digest(expected, actual):
        called["value"] = True
        return original_compare_digest(expected, actual)

    monkeypatch.setattr(partner_hmac_module.hmac, "compare_digest", fake_compare_digest)

    assert signed_result().accepted is True
    assert called["value"] is True
