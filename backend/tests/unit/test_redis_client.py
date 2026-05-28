"""Unit tests for Redis client factory."""

from app.redis import client as redis_client_module


class FakeRedisClient:
    pass


def test_get_redis_client_reuses_cached_client_and_configures_pool(monkeypatch):
    calls = []

    def fake_from_url(url, **kwargs):
        calls.append((url, kwargs))
        return FakeRedisClient()

    redis_client_module.get_redis_client.cache_clear()
    monkeypatch.setattr(redis_client_module.Redis, "from_url", fake_from_url)
    monkeypatch.setattr(
        redis_client_module.settings, "redis_url", "redis://test:6379/0"
    )
    monkeypatch.setattr(redis_client_module.settings, "redis_socket_timeout_ms", 250)
    monkeypatch.setattr(redis_client_module.settings, "redis_max_connections", 77)

    first = redis_client_module.get_redis_client()
    second = redis_client_module.get_redis_client()

    assert first is second
    assert len(calls) == 1
    assert calls[0] == (
        "redis://test:6379/0",
        {
            "decode_responses": True,
            "socket_connect_timeout": 0.25,
            "socket_timeout": 0.25,
            "max_connections": 77,
        },
    )
    redis_client_module.get_redis_client.cache_clear()
