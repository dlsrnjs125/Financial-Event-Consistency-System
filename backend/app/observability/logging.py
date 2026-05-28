"""Structured logging helpers."""

import logging
from typing import Any

from app.observability.context import get_request_id, get_trace_id
from app.security.masking import (
    mask_account_no,
    mask_idempotency_key,
    mask_signature,
    redact_secret,
)

SENSITIVE_FIELD_NAMES = {
    "account_no",
    "idempotency_key",
    "signature",
    "secret",
    "expected_signature",
    "raw_body",
}


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "trace_id", None):
            record.trace_id = get_trace_id()
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id()
        return True


def sanitize_log_extra(extra: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(extra)
    if "account_no" in sanitized:
        sanitized["account_no_masked"] = mask_account_no(
            str(sanitized.pop("account_no"))
        )
    if "idempotency_key" in sanitized:
        sanitized["idempotency_key_masked"] = mask_idempotency_key(
            str(sanitized.pop("idempotency_key"))
        )
    if "signature" in sanitized:
        sanitized["signature_masked"] = mask_signature(str(sanitized.pop("signature")))
    if "secret" in sanitized:
        sanitized["secret"] = redact_secret(str(sanitized["secret"]))
    if "expected_signature" in sanitized:
        sanitized["expected_signature"] = redact_secret(
            str(sanitized["expected_signature"])
        )
    sanitized.pop("raw_body", None)
    return sanitized


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    **extra: Any,
) -> None:
    try:
        logger.log(level, message, extra=sanitize_log_extra(extra))
    except Exception:
        return
