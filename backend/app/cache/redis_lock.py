"""Short TTL Redis lock helper."""

from dataclasses import dataclass
from uuid import uuid4


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
            return RedisLockResult(
                acquired=False,
                token=None,
                redis_available=False,
                reason=type(exc).__name__,
            )

        if not acquired:
            return RedisLockResult(
                acquired=False,
                token=None,
                redis_available=True,
                reason="LOCK_NOT_ACQUIRED",
            )

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
        except Exception:
            return
