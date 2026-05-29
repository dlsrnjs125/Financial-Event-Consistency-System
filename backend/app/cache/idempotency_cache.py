"""Redis-backed completed idempotency response cache."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.cache.redis_errors import REDIS_FALLBACK_EXCEPTIONS, redis_failure_reason
from app.cache.redis_keys import idempotency_cache_key
from app.observability.logging import log_event
from app.observability.metrics import (
    record_idempotency_cache_hit,
    record_idempotency_cache_miss,
    record_idempotency_cache_set_failure,
    record_redis_fallback,
    record_redis_operation,
    record_redis_operation_v2,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedIdempotencyResponse:
    request_hash: str
    response_code: int
    response_body: Any


class IdempotencyResponseCache:
    def __init__(self, redis_client, ttl_seconds: int = 86400) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    def get(self, idempotency_key: str) -> CachedIdempotencyResponse | None:
        try:
            cached = self.redis_client.get(idempotency_cache_key(idempotency_key))
        except REDIS_FALLBACK_EXCEPTIONS as exc:
            reason = redis_failure_reason(exc)
            record_redis_operation("cache_get", "unavailable")
            record_redis_operation_v2("cache_get", "failure", reason)
            record_redis_fallback("cache_get", reason)
            log_event(
                logger,
                logging.WARNING,
                "redis_cache_get_fallback",
                idempotency_key=idempotency_key,
                operation="cache_get",
                dependency="redis",
                fallback_used=True,
                error_type=type(exc).__name__,
            )
            return None
        if cached is None:
            record_idempotency_cache_miss()
            return None

        try:
            data = json.loads(cached)
            record_idempotency_cache_hit()
            return CachedIdempotencyResponse(
                request_hash=data["request_hash"],
                response_code=int(data["response_code"]),
                response_body=data.get("response_body"),
            )
        except (TypeError, ValueError, KeyError):
            record_idempotency_cache_miss()
            return None

    def set_completed(
        self,
        idempotency_key: str,
        request_hash: str,
        response_code: int,
        response_body: Any,
    ) -> None:
        payload = {
            "request_hash": request_hash,
            "response_code": response_code,
            "response_body": response_body,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        try:
            self.redis_client.setex(
                idempotency_cache_key(idempotency_key),
                self.ttl_seconds,
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=_json_default,
                ),
            )
            record_redis_operation("cache_set", "success")
            record_redis_operation_v2("cache_set", "success")
        except REDIS_FALLBACK_EXCEPTIONS as exc:
            reason = redis_failure_reason(exc)
            record_idempotency_cache_set_failure()
            record_redis_fallback("cache_set", reason)
            log_event(
                logger,
                logging.WARNING,
                "redis_cache_set_fallback",
                idempotency_key=idempotency_key,
                operation="cache_set",
                dependency="redis",
                fallback_used=True,
                error_type=type(exc).__name__,
            )
            return

    def delete(self, idempotency_key: str) -> None:
        try:
            self.redis_client.delete(idempotency_cache_key(idempotency_key))
            record_redis_operation("cache_delete", "success")
            record_redis_operation_v2("cache_delete", "success")
        except REDIS_FALLBACK_EXCEPTIONS as exc:
            reason = redis_failure_reason(exc)
            record_redis_operation("cache_delete", "unavailable")
            record_redis_operation_v2("cache_delete", "failure", reason)
            record_redis_fallback("cache_delete", reason)
            log_event(
                logger,
                logging.WARNING,
                "redis_cache_delete_fallback",
                idempotency_key=idempotency_key,
                operation="cache_delete",
                dependency="redis",
                fallback_used=True,
                error_type=type(exc).__name__,
            )
            return


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
