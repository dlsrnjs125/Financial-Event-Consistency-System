"""Short TTL Redis lock helper."""

import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from app.cache.redis_errors import REDIS_FALLBACK_EXCEPTIONS, redis_failure_reason
from app.observability.logging import log_event
from app.observability.metrics import (
    record_redis_fallback,
    record_redis_lock_result,
    record_redis_operation,
    record_redis_operation_v2,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RedisLockResult:
    acquired: bool
    token: str | None
    redis_available: bool
    reason: str | None = None


class RedisLock:
    _RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """

    def __init__(self, redis_client, ttl_ms: int = 3000) -> None:
        self.redis_client = redis_client
        self.ttl_ms = ttl_ms

    def acquire(self, key: str) -> RedisLockResult:
        started_at = perf_counter()
        token = uuid4().hex
        try:
            acquired = bool(self.redis_client.set(key, token, nx=True, px=self.ttl_ms))
        except REDIS_FALLBACK_EXCEPTIONS as exc:
            reason = redis_failure_reason(exc)
            record_redis_lock_result("unavailable")
            record_redis_operation_v2("lock_acquire", "failure", reason)
            record_redis_fallback("lock_acquire", reason)
            log_event(
                logger,
                logging.WARNING,
                "redis_lock_acquire_fallback",
                operation="lock_acquire",
                dependency="redis",
                fallback_used=True,
                error_type=type(exc).__name__,
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
            )
            return RedisLockResult(
                acquired=False,
                token=None,
                redis_available=False,
                reason=reason,
            )

        if not acquired:
            record_redis_lock_result("rejected")
            record_redis_operation_v2("lock_acquire", "failure", "unavailable")
            return RedisLockResult(
                acquired=False,
                token=None,
                redis_available=True,
                reason="LOCK_NOT_ACQUIRED",
            )

        record_redis_lock_result("success")
        record_redis_operation_v2("lock_acquire", "success")
        return RedisLockResult(
            acquired=True,
            token=token,
            redis_available=True,
        )

    def release(self, key: str, token: str | None) -> None:
        if token is None:
            return
        started_at = perf_counter()
        try:
            self.redis_client.eval(self._RELEASE_SCRIPT, 1, key, token)
            record_redis_operation("lock_release", "success")
            record_redis_operation_v2("lock_release", "success")
        except REDIS_FALLBACK_EXCEPTIONS as exc:
            reason = redis_failure_reason(exc)
            record_redis_operation("lock_release", "unavailable")
            record_redis_operation_v2("lock_release", "failure", reason)
            log_event(
                logger,
                logging.WARNING,
                "redis_lock_release_failed",
                operation="lock_release",
                dependency="redis",
                fallback_used=False,
                error_type=type(exc).__name__,
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
            )
            return
