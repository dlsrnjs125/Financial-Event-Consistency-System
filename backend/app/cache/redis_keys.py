"""Central Redis key builders."""

import hashlib

IDEMPOTENCY_LOCK_PREFIX = "lock:idempotency"
IDEMPOTENCY_CACHE_PREFIX = "cache:idempotency"


def hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def idempotency_lock_key(idempotency_key: str) -> str:
    return f"{IDEMPOTENCY_LOCK_PREFIX}:{hash_key(idempotency_key)}"


def idempotency_cache_key(idempotency_key: str) -> str:
    return f"{IDEMPOTENCY_CACHE_PREFIX}:{hash_key(idempotency_key)}"
