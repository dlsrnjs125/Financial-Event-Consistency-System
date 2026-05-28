"""Unit tests for RedisLock."""

from app.cache.redis_lock import RedisLock


class FakeRedis:
    def __init__(self, fail: bool = False) -> None:
        self.store = {}
        self.fail = fail

    def set(self, key, value, nx=False, px=None):
        if self.fail:
            raise TimeoutError("redis timeout")
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def eval(self, script, numkeys, key, token):
        if self.fail:
            raise TimeoutError("redis timeout")
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0


def test_acquire_success():
    redis = FakeRedis()
    lock = RedisLock(redis)

    result = lock.acquire("lock:key")

    assert result.acquired is True
    assert result.redis_available is True
    assert result.token is not None


def test_acquire_fails_when_key_exists():
    redis = FakeRedis()
    lock = RedisLock(redis)
    first = lock.acquire("lock:key")

    second = lock.acquire("lock:key")

    assert first.acquired is True
    assert second.acquired is False
    assert second.redis_available is True


def test_release_deletes_only_same_token():
    redis = FakeRedis()
    lock = RedisLock(redis)
    result = lock.acquire("lock:key")

    lock.release("lock:key", "wrong-token")
    assert "lock:key" in redis.store

    lock.release("lock:key", result.token)
    assert "lock:key" not in redis.store


def test_acquire_handles_redis_exception():
    lock = RedisLock(FakeRedis(fail=True))

    result = lock.acquire("lock:key")

    assert result.acquired is False
    assert result.redis_available is False


def test_release_handles_redis_exception_without_raising():
    lock = RedisLock(FakeRedis(fail=True))

    lock.release("lock:key", "token")
