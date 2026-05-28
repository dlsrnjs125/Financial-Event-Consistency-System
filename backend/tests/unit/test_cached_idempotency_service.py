"""Unit tests for CachedIdempotencyService."""

from app.domain.idempotency import (
    IdempotencyCheckResult,
    IdempotencyDecision,
    generate_request_hash,
)
from app.services.cached_idempotency_service import CachedIdempotencyService


class FakeCache:
    def __init__(self, cached=None, fail_get=False, fail_set=False) -> None:
        self.cached = cached
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.set_calls = []

    def get(self, idempotency_key):
        if self.fail_get:
            return None
        return self.cached

    def set_completed(
        self, idempotency_key, request_hash, response_code, response_body
    ):
        self.set_calls.append(
            (idempotency_key, request_hash, response_code, response_body)
        )
        if self.fail_set:
            return None


class FakeCachedResponse:
    def __init__(self, request_hash, response_code=200, response_body=None) -> None:
        self.request_hash = request_hash
        self.response_code = response_code
        self.response_body = response_body or {"ok": True}


class FakeIdempotencyService:
    def __init__(self, result=None) -> None:
        self.result = result or IdempotencyCheckResult(
            IdempotencyDecision.STARTED, record_id=1
        )
        self.check_calls = 0
        self.complete_calls = []
        self.fail_calls = []

    def check_or_start(self, idempotency_key, payload, now=None):
        self.check_calls += 1
        return self.result

    def complete(self, **kwargs):
        self.complete_calls.append(kwargs)
        return "record"

    def fail(self, **kwargs):
        self.fail_calls.append(kwargs)
        return "record"


def test_cache_hit_same_hash_replays_without_db_call():
    payload = {"amount": 1000}
    cached = FakeCachedResponse(generate_request_hash(payload), 200, {"ok": True})
    db_service = FakeIdempotencyService()
    service = CachedIdempotencyService(db_service, FakeCache(cached))

    result = service.check_or_start("idem-001", payload)

    assert result.decision == IdempotencyDecision.REPLAY_COMPLETED
    assert db_service.check_calls == 0


def test_cache_hit_different_hash_falls_back_to_db():
    cached = FakeCachedResponse("other-hash")
    db_service = FakeIdempotencyService()
    service = CachedIdempotencyService(db_service, FakeCache(cached))

    result = service.check_or_start("idem-001", {"amount": 1000})

    assert result.decision == IdempotencyDecision.STARTED
    assert db_service.check_calls == 1


def test_cache_miss_falls_back_to_db():
    db_service = FakeIdempotencyService()
    service = CachedIdempotencyService(db_service, FakeCache())

    result = service.check_or_start("idem-001", {"amount": 1000})

    assert result.decision == IdempotencyDecision.STARTED
    assert db_service.check_calls == 1


def test_db_replay_completed_sets_cache():
    payload = {"amount": 1000}
    db_service = FakeIdempotencyService(
        IdempotencyCheckResult(
            IdempotencyDecision.REPLAY_COMPLETED,
            record_id=1,
            response_code=200,
            response_body={"ok": True},
        )
    )
    cache = FakeCache()
    service = CachedIdempotencyService(db_service, cache)

    service.check_or_start("idem-001", payload)

    assert cache.set_calls


def test_cache_set_failure_does_not_fail_check():
    db_service = FakeIdempotencyService(
        IdempotencyCheckResult(
            IdempotencyDecision.REPLAY_COMPLETED,
            record_id=1,
            response_code=200,
            response_body={"ok": True},
        )
    )
    service = CachedIdempotencyService(db_service, FakeCache(fail_set=True))

    result = service.check_or_start("idem-001", {"amount": 1000})

    assert result.decision == IdempotencyDecision.REPLAY_COMPLETED


def test_complete_writes_db_then_cache():
    payload = {"amount": 1000}
    db_service = FakeIdempotencyService()
    cache = FakeCache()
    service = CachedIdempotencyService(db_service, cache)

    service.complete(
        idempotency_key="idem-001",
        response_code=200,
        response_body={"ok": True},
        payload=payload,
    )

    assert db_service.complete_calls
    assert cache.set_calls


def test_fail_does_not_write_cache():
    db_service = FakeIdempotencyService()
    cache = FakeCache()
    service = CachedIdempotencyService(db_service, cache)

    service.fail(idempotency_key="idem-001", response_code=422)

    assert db_service.fail_calls
    assert cache.set_calls == []


def test_cache_set_failure_does_not_fail_complete():
    db_service = FakeIdempotencyService()
    service = CachedIdempotencyService(db_service, FakeCache(fail_set=True))

    record = service.complete(
        idempotency_key="idem-001",
        response_code=200,
        response_body={"ok": True},
        payload={"amount": 1000},
    )

    assert record == "record"
    assert db_service.complete_calls
