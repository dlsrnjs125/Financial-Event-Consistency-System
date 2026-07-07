"""FastAPI dependencies for external system request authentication."""

from functools import lru_cache

from fastapi import Request

from app.core.config import settings
from app.observability.metrics import record_hmac_auth_failure, record_hmac_auth_success
from app.security.client_secret_provider import ClientSecretProvider
from app.security.exceptions import (
    DisabledClient,
    ExpiredTimestamp,
    InvalidSignature,
    InvalidTimestamp,
    MissingSecurityHeader,
    UnknownClient,
)
from app.security.hmac import (
    build_signature_base_string,
    generate_body_hash,
    verify_hmac_signature,
)
from app.security.partner_hmac import PartnerSecretRegistry, verify_partner_hmac_request
from app.security.timestamp import parse_timestamp, validate_timestamp_window


@lru_cache
def get_client_secret_provider(raw_secrets: str) -> ClientSecretProvider:
    # TODO(Phase 8+): support secret versioning/rotation without process restart.
    return ClientSecretProvider(raw_secrets)


@lru_cache
def get_partner_secret_registry(raw_secrets: str) -> PartnerSecretRegistry:
    return PartnerSecretRegistry.from_config(raw_secrets)


async def verify_external_request_signature(request: Request) -> None:
    if settings.enable_partner_hmac_auth:
        await _verify_partner_request_signature(request)
        return

    if not settings.hmac_enabled:
        # TODO(Phase 8+): move production HMAC misconfiguration checks to
        # application startup or Settings validation so the app fails fast.
        if settings.app_env.lower() in {"prod", "production"}:
            raise RuntimeError("HMAC must be enabled in production")
        return

    client_id = _required_header(request, "X-Client-Id")
    timestamp = _required_header(request, "X-Timestamp")
    signature = _required_header(request, "X-Signature")

    provider = get_client_secret_provider(settings.external_client_secrets)
    secret = provider.get_secret(client_id)
    if secret is None:
        record_hmac_auth_failure("unknown_client")
        raise UnknownClient()

    try:
        parsed_timestamp = parse_timestamp(timestamp)
        validate_timestamp_window(
            parsed_timestamp,
            allowed_skew_seconds=settings.hmac_allowed_skew_seconds,
        )
    except InvalidTimestamp:
        record_hmac_auth_failure("invalid_timestamp")
        raise
    except ExpiredTimestamp:
        record_hmac_auth_failure("expired_timestamp")
        raise

    raw_body = await request.body()
    body_hash = generate_body_hash(raw_body)
    base_string = build_signature_base_string(
        method=request.method,
        path=request.url.path,
        timestamp=timestamp,
        body_hash=body_hash,
    )
    if not verify_hmac_signature(secret, base_string, signature):
        record_hmac_auth_failure("invalid_signature")
        raise InvalidSignature()
    record_hmac_auth_success()


async def _verify_partner_request_signature(request: Request) -> None:
    client_id = _required_header(request, "X-Client-Id")
    key_id = _required_header(request, "X-Key-Id")
    timestamp = _required_header(request, "X-Timestamp")
    nonce = _required_header(request, "X-Nonce")
    signature = _required_header(request, "X-Signature")

    raw_body = await request.body()
    result = verify_partner_hmac_request(
        registry=get_partner_secret_registry(settings.partner_hmac_secrets),
        method=request.method,
        path=request.url.path,
        timestamp=timestamp,
        nonce=nonce,
        raw_body=raw_body,
        client_id=client_id,
        key_id=key_id,
        signature=signature,
        allowed_skew_seconds=settings.partner_hmac_timestamp_skew_seconds,
        allow_next_for_dry_run=settings.partner_hmac_allow_next_dry_run,
    )
    if result.accepted:
        record_hmac_auth_success()
        return

    record_hmac_auth_failure(_metric_reason(result.decision_reason))
    if result.decision_reason == "unknown_client":
        raise UnknownClient()
    if result.decision_reason == "disabled_client":
        raise DisabledClient()
    if result.decision_reason in {"invalid_timestamp", "timestamp_skew_exceeded"}:
        if result.decision_reason == "invalid_timestamp":
            raise InvalidTimestamp()
        raise ExpiredTimestamp()
    raise InvalidSignature()


def _required_header(request: Request, header_name: str) -> str:
    value = request.headers.get(header_name)
    if value is None or not value.strip():
        record_hmac_auth_failure("missing_header")
        raise MissingSecurityHeader(header_name)
    return value.strip()


def _metric_reason(decision_reason: str) -> str:
    if decision_reason in {"unknown_client"}:
        return "unknown_client"
    if decision_reason in {"disabled_client"}:
        return "disabled_client"
    if decision_reason in {"invalid_timestamp"}:
        return "invalid_timestamp"
    if decision_reason in {"timestamp_skew_exceeded"}:
        return "expired_timestamp"
    if decision_reason in {
        "invalid_signature",
        "invalid_signature_format",
        "missing_signature",
        "missing_nonce",
        "unknown_key",
        "revoked_key",
        "previous_expired",
        "next_not_allowed",
    }:
        return "invalid_signature"
    return "unknown"
