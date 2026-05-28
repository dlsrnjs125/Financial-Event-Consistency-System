"""FastAPI dependencies for external system request authentication."""

from functools import lru_cache

from fastapi import Request

from app.core.config import settings
from app.observability.metrics import record_hmac_auth_failure, record_hmac_auth_success
from app.security.client_secret_provider import ClientSecretProvider
from app.security.exceptions import (
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
from app.security.timestamp import parse_timestamp, validate_timestamp_window


@lru_cache
def get_client_secret_provider(raw_secrets: str) -> ClientSecretProvider:
    # TODO(Phase 8+): support secret versioning/rotation without process restart.
    return ClientSecretProvider(raw_secrets)


async def verify_external_request_signature(request: Request) -> None:
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


def _required_header(request: Request, header_name: str) -> str:
    value = request.headers.get(header_name)
    if value is None or not value.strip():
        record_hmac_auth_failure("missing_header")
        raise MissingSecurityHeader(header_name)
    return value.strip()
