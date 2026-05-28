"""Short TTL Redis lock helper."""

from dataclasses import dataclass
from uuid import uuid4

from app.observability.metrics import record_redis_lock_result, record_redis_operation


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
        token = uuid4().hex
        try:
            acquired = bool(self.redis_client.set(key, token, nx=True, px=self.ttl_ms))
        except Exception as exc:
            record_redis_lock_result("unavailable")
            return RedisLockResult(
                acquired=False,
                token=None,
                redis_available=False,
                reason=type(exc).__name__,
            )

        if not acquired:
            record_redis_lock_result("rejected")
            return RedisLockResult(
                acquired=False,
                token=None,
                redis_available=True,
                reason="LOCK_NOT_ACQUIRED",
            )

        record_redis_lock_result("success")
        return RedisLockResult(
            acquired=True,
            token=token,
            redis_available=True,
        )

    def release(self, key: str, token: str | None) -> None:
        if token is None:
            return
        try:
            self.redis_client.eval(self._RELEASE_SCRIPT, 1, key, token)
            record_redis_operation("lock_release", "success")
        except Exception:
            record_redis_operation("lock_release", "unavailable")
            return
