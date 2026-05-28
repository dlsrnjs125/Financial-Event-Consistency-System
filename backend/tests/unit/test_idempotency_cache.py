"""Unit tests for idempotency response cache."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from app.cache.idempotency_cache import IdempotencyResponseCache
from app.cache.redis_keys import idempotency_cache_key


class FakeRedis:
    def __init__(self, fail_get=False, fail_set=False) -> None:
        self.store = {}
        self.ttl = {}
        self.fail_get = fail_get
        self.fail_set = fail_set

    def get(self, key):
        if self.fail_get:
            raise TimeoutError("redis timeout")
        return self.store.get(key)

    def setex(self, key, ttl, value):
        if self.fail_set:
            raise TimeoutError("redis timeout")
        self.store[key] = value
        self.ttl[key] = ttl

    def delete(self, key):
        self.store.pop(key, None)


def test_set_completed_then_get():
    redis = FakeRedis()
    cache = IdempotencyResponseCache(redis, ttl_seconds=60)

    cache.set_completed("idem-001", "hash", 200, {"ok": True})
    cached = cache.get("idem-001")

    assert cached.request_hash == "hash"
    assert cached.response_code == 200
    assert cached.response_body == {"ok": True}
    assert redis.ttl[idempotency_cache_key("idem-001")] == 60


def test_get_returns_none_on_cache_miss():
    assert IdempotencyResponseCache(FakeRedis()).get("idem-001") is None


def test_get_returns_none_on_redis_error():
    assert IdempotencyResponseCache(FakeRedis(fail_get=True)).get("idem-001") is None


def test_set_completed_does_not_raise_on_redis_error():
    IdempotencyResponseCache(FakeRedis(fail_set=True)).set_completed(
        "idem-001", "hash", 200, {"ok": True}
    )


def test_invalid_cached_payload_returns_none():
    redis = FakeRedis()
    redis.store[idempotency_cache_key("idem-001")] = json.dumps({"bad": "payload"})

    assert IdempotencyResponseCache(redis).get("idem-001") is None


def test_set_completed_serializes_decimal_datetime_and_enum_values():
    class ResultStatus(StrEnum):
        COMPLETED = "COMPLETED"

    redis = FakeRedis()
    cache = IdempotencyResponseCache(redis)
    response_body = {
        "balance_after": Decimal("11000"),
        "processed_at": datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
        "status": ResultStatus.COMPLETED,
    }

    cache.set_completed("idem-001", "hash", 200, response_body)
    cached = cache.get("idem-001")

    assert cached.response_body == {
        "balance_after": 11000,
        "processed_at": "2026-05-28T12:00:00+00:00",
        "status": "COMPLETED",
    }
