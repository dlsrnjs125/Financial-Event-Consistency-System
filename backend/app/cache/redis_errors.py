"""Redis failure classification helpers."""

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

REDIS_FALLBACK_EXCEPTIONS = (
    RedisConnectionError,
    RedisTimeoutError,
    RedisError,
    TimeoutError,
    OSError,
)


def redis_failure_reason(exc: Exception) -> str:
    if isinstance(exc, (RedisTimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(exc, (RedisConnectionError, ConnectionError, OSError)):
        return "connection_error"
    return "unknown"
