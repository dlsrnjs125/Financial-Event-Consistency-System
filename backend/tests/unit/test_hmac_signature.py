"""Unit tests for HMAC signature helpers."""

import hmac as stdlib_hmac

from app.security import hmac as hmac_module
from app.security.hmac import (
    build_signature_base_string,
    generate_body_hash,
    generate_hmac_signature,
    verify_hmac_signature,
)


def test_body_hash_uses_raw_bytes_stably():
    assert generate_body_hash(b'{"amount":1000}') == generate_body_hash(
        b'{"amount":1000}'
    )
    assert generate_body_hash(b'{"amount":1000}') != generate_body_hash(
        b'{"amount":2000}'
    )


def test_same_input_generates_same_signature():
    base = build_signature_base_string("post", "/api/v1/transaction-events", "ts", "h")

    assert generate_hmac_signature("secret", base) == generate_hmac_signature(
        "secret", base
    )


def test_signature_verification_fails_when_signed_fields_change():
    body_hash = generate_body_hash(b"{}")
    base = build_signature_base_string(
        "POST", "/api/v1/transaction-events", "2026-05-28T10:00:00+09:00", body_hash
    )
    signature = generate_hmac_signature("secret", base)

    assert verify_hmac_signature("secret", base, signature) is True
    assert (
        verify_hmac_signature(
            "other-secret",
            base,
            signature,
        )
        is False
    )
    assert (
        verify_hmac_signature(
            "secret",
            build_signature_base_string("GET", "/api/v1/transaction-events", "ts", "h"),
            signature,
        )
        is False
    )
    assert (
        verify_hmac_signature(
            "secret",
            build_signature_base_string("POST", "/different", "ts", "h"),
            signature,
        )
        is False
    )
    assert (
        verify_hmac_signature(
            "secret",
            build_signature_base_string(
                "POST", "/api/v1/transaction-events", "other", "h"
            ),
            signature,
        )
        is False
    )
    assert (
        verify_hmac_signature(
            "secret",
            build_signature_base_string(
                "POST", "/api/v1/transaction-events", "ts", "different"
            ),
            signature,
        )
        is False
    )


def test_empty_or_non_hex_signature_fails():
    base = build_signature_base_string("POST", "/path", "ts", "hash")

    assert verify_hmac_signature("secret", base, "") is False
    assert verify_hmac_signature("", base, "a" * 64) is False
    assert verify_hmac_signature("secret", base, "not-a-signature") is False


def test_uppercase_hex_signature_is_accepted():
    base = build_signature_base_string("POST", "/path", "ts", "hash")
    signature = generate_hmac_signature("secret", base)

    assert verify_hmac_signature("secret", base, signature.upper()) is True


def test_sha256_prefixed_signature_is_not_supported():
    base = build_signature_base_string("POST", "/path", "ts", "hash")
    signature = generate_hmac_signature("secret", base)

    assert verify_hmac_signature("secret", base, f"sha256={signature}") is False


def test_signature_base_string_uses_lf_newlines():
    base = build_signature_base_string("post", "/path", "timestamp", "body-hash")

    assert base == "POST\n/path\ntimestamp\nbody-hash"


def test_compare_digest_is_used(monkeypatch):
    called = {"value": False}
    original_compare_digest = stdlib_hmac.compare_digest

    def fake_compare_digest(expected, actual):
        called["value"] = True
        return original_compare_digest(expected, actual)

    monkeypatch.setattr(hmac_module.hmac, "compare_digest", fake_compare_digest)
    base = build_signature_base_string("POST", "/path", "ts", "hash")
    signature = generate_hmac_signature("secret", base)

    assert verify_hmac_signature("secret", base, signature) is True
    assert called["value"] is True
