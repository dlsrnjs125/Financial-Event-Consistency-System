"""Unit tests for IdempotencyService."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.domain.exceptions import IdempotencyConflict
from app.domain.idempotency import IdempotencyDecision, generate_request_hash
from app.domain.idempotency_status import IdempotencyStatus
from app.services.idempotency_service import IdempotencyService


class FakeIdempotencyRecordRepository:
    def __init__(self) -> None:
        self.records: dict[str, SimpleNamespace] = {}
        self.next_id = 1

    def get_by_key(self, idempotency_key: str):
        return self.records.get(idempotency_key)

    def create_processing(
        self,
        idempotency_key: str,
        request_hash: str,
        expires_at: datetime,
        locked_until: datetime | None = None,
    ):
        record = SimpleNamespace(
            id=self.next_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status=IdempotencyStatus.PROCESSING.value,
            response_code=None,
            response_body=None,
            completed_at=None,
            updated_at=None,
            expires_at=expires_at,
            locked_until=locked_until,
        )
        self.next_id += 1
        self.records[idempotency_key] = record
        return record

    def mark_completed(
        self,
        record,
        response_code: int,
        response_body: Any | None,
        completed_at: datetime,
    ):
        record.status = IdempotencyStatus.COMPLETED.value
        record.response_code = response_code
        record.response_body = response_body
        record.completed_at = completed_at
        record.updated_at = completed_at
        record.locked_until = None
        return record

    def mark_failed(
        self,
        record,
        failed_at: datetime,
        response_code: int | None = None,
        response_body: Any | None = None,
    ):
        record.status = IdempotencyStatus.FAILED.value
        record.response_code = response_code
        record.response_body = response_body
        record.updated_at = failed_at
        record.locked_until = None
        return record


def make_service(ttl_seconds=60, processing_lock_seconds=10):
    repository = FakeIdempotencyRecordRepository()
    service = IdempotencyService(
        repository,
        ttl_seconds=ttl_seconds,
        processing_lock_seconds=processing_lock_seconds,
    )
    return service, repository


def test_new_key_creates_processing_record_and_returns_started():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, repository = make_service()

    result = service.check_or_start("idem-001", {"amount": 1000}, now=now)

    record = repository.get_by_key("idem-001")
    assert result.decision == IdempotencyDecision.STARTED
    assert result.record_id == record.id
    assert record.status == IdempotencyStatus.PROCESSING.value
    assert record.expires_at.timestamp() - now.timestamp() == 60
    assert record.locked_until.timestamp() - now.timestamp() == 10


def test_same_key_same_body_processing_returns_already_processing():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)

    result = service.check_or_start("idem-001", payload, now=now)

    assert result.decision == IdempotencyDecision.ALREADY_PROCESSING


def test_same_key_same_body_completed_replays_saved_response():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)
    service.complete("idem-001", 200, {"ok": True}, now=now)

    result = service.check_or_start("idem-001", payload, now=now)

    assert result.decision == IdempotencyDecision.REPLAY_COMPLETED
    assert result.response_code == 200
    assert result.response_body == {"ok": True}


def test_same_key_same_body_failed_replays_failed_response():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)
    service.fail("idem-001", 422, {"error": "invalid amount"}, now=now)

    result = service.check_or_start("idem-001", payload, now=now)

    assert result.decision == IdempotencyDecision.REPLAY_FAILED
    assert result.response_code == 422
    assert result.response_body == {"error": "invalid amount"}


def test_same_key_different_body_raises_conflict():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    service.check_or_start("idem-001", {"amount": 1000}, now=now)

    with pytest.raises(IdempotencyConflict):
        service.check_or_start("idem-001", {"amount": 2000}, now=now)


def test_complete_sets_completed_status_and_response_data():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, repository = make_service()
    service.check_or_start("idem-001", {"amount": 1000}, now=now)

    record = service.complete("idem-001", 200, {"ok": True}, now=now)

    assert record is repository.get_by_key("idem-001")
    assert record.status == IdempotencyStatus.COMPLETED.value
    assert record.response_code == 200
    assert record.response_body == {"ok": True}
    assert record.completed_at == now
    assert record.locked_until is None


def test_fail_sets_failed_status_and_response_data():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, repository = make_service()
    service.check_or_start("idem-001", {"amount": 1000}, now=now)

    record = service.fail("idem-001", 422, {"error": "invalid amount"}, now=now)

    assert record is repository.get_by_key("idem-001")
    assert record.status == IdempotencyStatus.FAILED.value
    assert record.response_code == 422
    assert record.response_body == {"error": "invalid amount"}
    assert record.updated_at == now
    assert record.locked_until is None


def test_existing_same_body_compares_generated_request_hash():
    service, repository = make_service()
    record = repository.create_processing(
        idempotency_key="idem-001",
        request_hash=generate_request_hash({"currency": "KRW", "amount": 1000}),
        expires_at=datetime(2026, 5, 29, tzinfo=UTC),
    )

    result = service.check_or_start(
        "idem-001",
        {"amount": 1000, "currency": "KRW"},
        now=datetime(2026, 5, 28, tzinfo=UTC),
    )

    assert result.decision == IdempotencyDecision.ALREADY_PROCESSING
    assert result.record_id == record.id
