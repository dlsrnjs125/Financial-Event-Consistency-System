"""Unit tests for Redis key builders."""

from app.cache.redis_keys import (
    IDEMPOTENCY_CACHE_PREFIX,
    IDEMPOTENCY_LOCK_PREFIX,
    idempotency_cache_key,
    idempotency_lock_key,
)


def test_same_idempotency_key_builds_same_redis_key():
    assert idempotency_lock_key("idem-001") == idempotency_lock_key("idem-001")
    assert idempotency_cache_key("idem-001") == idempotency_cache_key("idem-001")


def test_different_idempotency_key_builds_different_redis_key():
    assert idempotency_lock_key("idem-001") != idempotency_lock_key("idem-002")
    assert idempotency_cache_key("idem-001") != idempotency_cache_key("idem-002")


def test_raw_idempotency_key_is_not_included():
    raw_key = "idem-secret-001"

    assert raw_key not in idempotency_lock_key(raw_key)
    assert raw_key not in idempotency_cache_key(raw_key)


def test_expected_prefixes_are_used():
    assert idempotency_lock_key("idem-001").startswith(f"{IDEMPOTENCY_LOCK_PREFIX}:")
    assert idempotency_cache_key("idem-001").startswith(f"{IDEMPOTENCY_CACHE_PREFIX}:")
