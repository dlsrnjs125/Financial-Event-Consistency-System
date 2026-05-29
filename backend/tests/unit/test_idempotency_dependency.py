"""Unit tests for Idempotency-Key dependency helpers."""

import pytest

from app.api.dependencies.idempotency import get_idempotency_key, mask_idempotency_key
from app.domain.exceptions import InvalidIdempotencyKey, MissingIdempotencyKey


def test_get_idempotency_key_rejects_missing_header():
    with pytest.raises(MissingIdempotencyKey):
        get_idempotency_key(None)


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_get_idempotency_key_rejects_blank_header(value):
    with pytest.raises(MissingIdempotencyKey):
        get_idempotency_key(value)


def test_get_idempotency_key_strips_surrounding_whitespace():
    assert get_idempotency_key("  idem-001  ") == "idem-001"


def test_get_idempotency_key_accepts_128_character_key():
    key = "a" * 128

    assert get_idempotency_key(key) == key


def test_get_idempotency_key_rejects_129_character_key():
    with pytest.raises(InvalidIdempotencyKey):
        get_idempotency_key("a" * 129)


def test_mask_idempotency_key_does_not_return_full_key():
    assert mask_idempotency_key("idem-20260528-0001") == "idem...0001"
    assert mask_idempotency_key("short") == "***"
