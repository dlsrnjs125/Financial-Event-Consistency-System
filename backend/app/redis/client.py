"""Redis client and health-check helpers."""

from functools import lru_cache

from redis import Redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> Redis:
    timeout_seconds = settings.redis_socket_timeout_ms / 1000
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=timeout_seconds,
        socket_timeout=timeout_seconds,
        max_connections=settings.redis_max_connections,
    )


def check_redis_connection() -> bool:
    try:
        client = get_redis_client()
        return bool(client.ping())
    except Exception:
        return False
