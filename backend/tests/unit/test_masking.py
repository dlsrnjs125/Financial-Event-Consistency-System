"""Unit tests for security masking helpers."""

from app.security.masking import (
    mask_account_no,
    mask_idempotency_key,
    mask_signature,
    redact_secret,
)


def test_mask_account_no_keeps_only_last_four_digits():
    assert mask_account_no("1234567890") == "******7890"


def test_mask_account_no_handles_short_and_empty_values():
    assert mask_account_no("123") == "***"
    assert mask_account_no(None) == ""
    assert mask_account_no("") == ""


def test_mask_idempotency_key_does_not_return_full_key():
    key = "idem-20260528-001"

    masked = mask_idempotency_key(key)

    assert masked != key
    assert masked == "idem...-001"
    assert mask_idempotency_key("short") == "***"


def test_mask_signature_does_not_return_full_signature():
    signature = "a" * 64

    masked = mask_signature(signature)

    assert masked != signature
    assert masked == "aaaaaaaa***"
    assert mask_signature("short") == "<redacted>"


def test_redact_secret_always_redacts():
    assert redact_secret("super-secret") == "<redacted>"
    assert redact_secret(None) == "<redacted>"
