"""Unit tests for FastAPI partner HMAC dependency wiring."""

import asyncio
from datetime import UTC, datetime

import pytest
from starlette.requests import Request

from app.api.dependencies import security as security_dependency
from app.core.config import settings
from app.security.exceptions import (
    DisabledClient,
    InvalidSignature,
    MissingSecurityHeader,
)
from app.security.partner_hmac import (
    build_partner_canonical_request,
    generate_partner_hmac_signature,
)

PATH = "/api/v1/transaction-events"
BODY = b'{"amount":1000,"currency":"KRW"}'


@pytest.fixture(autouse=True)
def reset_partner_hmac_settings(monkeypatch):
    security_dependency.get_partner_secret_registry.cache_clear()
    monkeypatch.setattr(settings, "enable_partner_hmac_auth", True)
    monkeypatch.setattr(settings, "partner_hmac_timestamp_skew_seconds", 300)
    monkeypatch.setattr(settings, "partner_hmac_allow_next_dry_run", False)
    yield
    security_dependency.get_partner_secret_registry.cache_clear()


def test_partner_dependency_accepts_current_secret(monkeypatch):
    monkeypatch.setattr(
        settings,
        "partner_hmac_secrets",
        "bank-a|key-current|current|dummy-current-value||true",
    )
    request = _signed_request(key_id="key-current", signing_value="dummy-current-value")

    asyncio.run(security_dependency.verify_external_request_signature(request))


def test_partner_dependency_requires_key_id(monkeypatch):
    monkeypatch.setattr(
        settings,
        "partner_hmac_secrets",
        "bank-a|key-current|current|dummy-current-value||true",
    )
    headers = _signed_headers("key-current", "dummy-current-value")
    headers.pop("X-Key-Id")
    request = _request(headers=headers)

    with pytest.raises(MissingSecurityHeader):
        asyncio.run(security_dependency.verify_external_request_signature(request))


def test_partner_dependency_rejects_query_string(monkeypatch):
    monkeypatch.setattr(
        settings,
        "partner_hmac_secrets",
        "bank-a|key-current|current|dummy-current-value||true",
    )
    request = _signed_request(
        key_id="key-current",
        signing_value="dummy-current-value",
        query_string="dry_run=true",
    )

    with pytest.raises(InvalidSignature):
        asyncio.run(security_dependency.verify_external_request_signature(request))


def test_partner_dependency_never_accepts_next_key_on_write_api(monkeypatch):
    monkeypatch.setattr(settings, "partner_hmac_allow_next_dry_run", True)
    monkeypatch.setattr(
        settings,
        "partner_hmac_secrets",
        "bank-a|key-next|next|dummy-next-value||true",
    )
    request = _signed_request(key_id="key-next", signing_value="dummy-next-value")

    with pytest.raises(InvalidSignature):
        asyncio.run(security_dependency.verify_external_request_signature(request))


def test_partner_dependency_fails_fast_when_enabled_without_valid_secret(monkeypatch):
    monkeypatch.setattr(settings, "partner_hmac_secrets", "")
    request = _signed_request(key_id="key-current", signing_value="dummy-current-value")

    with pytest.raises(RuntimeError):
        asyncio.run(security_dependency.verify_external_request_signature(request))


@pytest.mark.parametrize(
    ("raw_secrets", "key_id", "signing_value"),
    [
        (
            "bank-a|key-revoked|revoked|dummy-revoked-value||true",
            "key-revoked",
            "dummy-revoked-value",
        ),
        (
            "bank-a|key-previous|previous|dummy-previous-value|"
            "2026-01-01T00:00:00+00:00|true",
            "key-previous",
            "dummy-previous-value",
        ),
        (
            "bank-a|key-current|current|dummy-current-value||true",
            "unknown-key",
            "dummy-current-value",
        ),
    ],
)
def test_partner_dependency_maps_rejected_keys_to_invalid_signature(
    monkeypatch,
    raw_secrets,
    key_id,
    signing_value,
):
    monkeypatch.setattr(settings, "partner_hmac_secrets", raw_secrets)
    request = _signed_request(key_id=key_id, signing_value=signing_value)

    with pytest.raises(InvalidSignature):
        asyncio.run(security_dependency.verify_external_request_signature(request))


def test_partner_dependency_maps_disabled_client_to_disabled_client(monkeypatch):
    monkeypatch.setattr(
        settings,
        "partner_hmac_secrets",
        "bank-disabled|key-current|disabled|dummy-disabled-value||false",
    )
    request = _signed_request(
        client_id="bank-disabled",
        key_id="key-current",
        signing_value="dummy-disabled-value",
    )

    with pytest.raises(DisabledClient):
        asyncio.run(security_dependency.verify_external_request_signature(request))


def test_partner_dependency_metric_reason_stays_bounded(monkeypatch):
    reasons: list[str] = []
    monkeypatch.setattr(security_dependency, "record_hmac_auth_failure", reasons.append)
    monkeypatch.setattr(
        settings,
        "partner_hmac_secrets",
        "bank-a|key-current|current|dummy-current-value||true",
    )
    request = _signed_request(key_id="unknown-key", signing_value="dummy-current-value")

    with pytest.raises(InvalidSignature):
        asyncio.run(security_dependency.verify_external_request_signature(request))

    assert reasons == ["invalid_signature"]


def _signed_request(
    *,
    key_id: str,
    signing_value: str,
    client_id: str = "bank-a",
    query_string: str = "",
) -> Request:
    return _request(
        headers=_signed_headers(
            key_id=key_id,
            signing_value=signing_value,
            client_id=client_id,
        ),
        query_string=query_string,
    )


def _signed_headers(
    key_id: str,
    signing_value: str,
    client_id: str = "bank-a",
) -> dict[str, str]:
    timestamp = datetime.now(UTC).isoformat()
    nonce = "nonce-001"
    canonical = build_partner_canonical_request("POST", PATH, timestamp, nonce, BODY)
    return {
        "X-Client-Id": client_id,
        "X-Key-Id": key_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": generate_partner_hmac_signature(signing_value, canonical),
    }


def _request(headers: dict[str, str], query_string: str = "") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": PATH,
        "headers": [
            (key.lower().encode(), value.encode()) for key, value in headers.items()
        ],
        "query_string": query_string.encode(),
        "server": ("testserver", 80),
        "scheme": "http",
    }

    async def receive():
        return {"type": "http.request", "body": BODY, "more_body": False}

    return Request(scope, receive)
