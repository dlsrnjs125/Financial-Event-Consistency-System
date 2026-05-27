"""Unit tests for idempotency request hashing."""

from app.domain.idempotency import generate_request_hash


def test_generate_request_hash_is_order_independent_for_dict():
    payload1 = {"amount": 1000, "currency": "KRW"}
    payload2 = {"currency": "KRW", "amount": 1000}

    assert generate_request_hash(payload1) == generate_request_hash(payload2)


def test_generate_request_hash_changes_when_payload_value_changes():
    payload1 = {"amount": 1000, "currency": "KRW"}
    payload2 = {"amount": 2000, "currency": "KRW"}

    assert generate_request_hash(payload1) != generate_request_hash(payload2)


def test_generate_request_hash_supports_unicode_payload():
    payload = {"memo": "입금 테스트", "currency": "KRW"}

    assert len(generate_request_hash(payload)) == 64


def test_generate_request_hash_supports_list_payload():
    payload = [{"amount": 1000}, {"amount": 2000}]

    assert generate_request_hash(payload) == generate_request_hash(payload)


def test_generate_request_hash_supports_bytes_payload():
    payload = b'{"amount":1000,"currency":"KRW"}'

    assert len(generate_request_hash(payload)) == 64


def test_generate_request_hash_is_stable_for_same_payload():
    payload = {"nested": {"currency": "KRW", "amount": 1000}}

    assert generate_request_hash(payload) == generate_request_hash(payload)
