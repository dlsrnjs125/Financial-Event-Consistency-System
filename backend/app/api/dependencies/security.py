"""FastAPI dependencies for external system request authentication."""

from functools import lru_cache

from fastapi import Request

from app.core.config import settings
from app.security.client_secret_provider import ClientSecretProvider
from app.security.exceptions import (
    InvalidSignature,
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
    return ClientSecretProvider(raw_secrets)


async def verify_external_request_signature(request: Request) -> None:
    if not settings.hmac_enabled:
        return

    client_id = _required_header(request, "X-Client-Id")
    timestamp = _required_header(request, "X-Timestamp")
    signature = _required_header(request, "X-Signature")

    provider = get_client_secret_provider(settings.external_client_secrets)
    secret = provider.get_secret(client_id)
    if secret is None:
        raise UnknownClient()

    parsed_timestamp = parse_timestamp(timestamp)
    validate_timestamp_window(
        parsed_timestamp,
        allowed_skew_seconds=settings.hmac_allowed_skew_seconds,
    )

    raw_body = await request.body()
    body_hash = generate_body_hash(raw_body)
    base_string = build_signature_base_string(
        method=request.method,
        path=request.url.path,
        timestamp=timestamp,
        body_hash=body_hash,
    )
    if not verify_hmac_signature(secret, base_string, signature):
        raise InvalidSignature()


def _required_header(request: Request, header_name: str) -> str:
    value = request.headers.get(header_name)
    if value is None or not value.strip():
        raise MissingSecurityHeader(header_name)
    return value.strip()
