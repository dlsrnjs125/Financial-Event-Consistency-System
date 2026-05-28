"""Structured logging setup."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.observability.logging import RequestContextFilter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": settings.app_name,
            "environment": settings.app_env,
            "message": record.getMessage(),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            payload["trace_id"] = trace_id

        for field in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "event_id",
            "external_event_id",
            "event_type",
            "transaction_status",
            "idempotency_decision",
            "idempotency_key_masked",
            "account_no_masked",
            "redis_available",
            "redis_lock_result",
            "hmac_failure_reason",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())

    # Do not log secrets, signatures, access tokens, or raw account identifiers.
