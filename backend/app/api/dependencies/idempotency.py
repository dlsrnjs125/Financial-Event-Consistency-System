"""Idempotency request dependencies."""

from fastapi import Header

from app.domain.exceptions import InvalidIdempotencyKey, MissingIdempotencyKey

MAX_IDEMPOTENCY_KEY_LENGTH = 128


def mask_idempotency_key(idempotency_key: str) -> str:
    stripped = idempotency_key.strip()
    if len(stripped) <= 8:
        return "*" * len(stripped)
    return f"{stripped[:4]}...{stripped[-4:]}"


def get_idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    if idempotency_key is None:
        raise MissingIdempotencyKey()

    stripped = idempotency_key.strip()
    if not stripped:
        raise MissingIdempotencyKey()
    if len(stripped) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise InvalidIdempotencyKey("Idempotency-Key must be 128 characters or fewer")

    return stripped
