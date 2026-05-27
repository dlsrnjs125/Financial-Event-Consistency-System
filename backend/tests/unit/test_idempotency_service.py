"""Unit tests for IdempotencyService."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.domain.exceptions import IdempotencyConflict, InvalidIdempotencyState
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
            error_message=None,
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
        error_message: str | None = None,
    ):
        record.status = IdempotencyStatus.FAILED.value
        record.response_code = response_code
        record.response_body = response_body
        record.error_message = error_message
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
    service.complete("idem-001", 200, {"ok": True}, payload=payload, now=now)

    result = service.check_or_start("idem-001", payload, now=now)

    assert result.decision == IdempotencyDecision.REPLAY_COMPLETED
    assert result.response_code == 200
    assert result.response_body == {"ok": True}


def test_same_key_same_body_failed_replays_failed_response():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)
    service.fail("idem-001", 422, {"error": "invalid amount"}, payload=payload, now=now)

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

    record = service.complete(
        "idem-001", 200, {"ok": True}, payload={"amount": 1000}, now=now
    )

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

    record = service.fail(
        "idem-001",
        422,
        {"error": "invalid amount"},
        error_message="invalid amount",
        payload={"amount": 1000},
        now=now,
    )

    assert record is repository.get_by_key("idem-001")
    assert record.status == IdempotencyStatus.FAILED.value
    assert record.response_code == 422
    assert record.response_body == {"error": "invalid amount"}
    assert record.error_message == "invalid amount"
    assert record.updated_at == now
    assert record.locked_until is None


def test_completed_record_cannot_be_marked_failed():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)
    service.complete("idem-001", 200, {"ok": True}, payload=payload, now=now)

    with pytest.raises(InvalidIdempotencyState):
        service.fail(
            "idem-001",
            500,
            {"error": "late failure"},
            payload=payload,
            now=now,
        )


def test_failed_record_cannot_be_marked_completed():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)
    service.fail("idem-001", 422, {"error": "invalid"}, payload=payload, now=now)

    with pytest.raises(InvalidIdempotencyState):
        service.complete("idem-001", 200, {"ok": True}, payload=payload, now=now)


def test_completed_record_complete_is_noop_and_keeps_original_response():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)
    first = service.complete("idem-001", 200, {"ok": True}, payload=payload, now=now)

    second = service.complete(
        "idem-001",
        201,
        {"ok": "changed"},
        payload=payload,
        now=datetime(2026, 5, 28, 10, 1, tzinfo=UTC),
    )

    assert second is first
    assert second.response_code == 200
    assert second.response_body == {"ok": True}
    assert second.completed_at == now


def test_failed_record_fail_is_noop_and_keeps_original_response():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)
    first = service.fail(
        "idem-001",
        422,
        {"error": "invalid"},
        error_message="invalid",
        payload=payload,
        now=now,
    )

    second = service.fail(
        "idem-001",
        500,
        {"error": "changed"},
        error_message="changed",
        payload=payload,
        now=datetime(2026, 5, 28, 10, 1, tzinfo=UTC),
    )

    assert second is first
    assert second.response_code == 422
    assert second.response_body == {"error": "invalid"}
    assert second.error_message == "invalid"
    assert second.updated_at == now


def test_missing_record_error_does_not_include_full_idempotency_key():
    service, _ = make_service()

    with pytest.raises(KeyError) as exc_info:
        service.complete("idem-secret-001", 200, {"ok": True})

    assert "idem-secret-001" not in str(exc_info.value)


def test_complete_rejects_different_payload_for_existing_key():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    service.check_or_start("idem-001", {"amount": 1000}, now=now)

    with pytest.raises(IdempotencyConflict):
        service.complete(
            "idem-001",
            200,
            {"ok": True},
            payload={"amount": 2000},
            now=now,
        )


def test_fail_rejects_different_request_hash_for_existing_key():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    service.check_or_start("idem-001", {"amount": 1000}, now=now)

    with pytest.raises(IdempotencyConflict):
        service.fail(
            "idem-001",
            422,
            {"error": "invalid amount"},
            request_hash=generate_request_hash({"amount": 2000}),
            now=now,
        )


def test_completion_rejects_payload_and_request_hash_together():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, _ = make_service()
    payload = {"amount": 1000}
    service.check_or_start("idem-001", payload, now=now)

    with pytest.raises(ValueError):
        service.complete(
            "idem-001",
            200,
            {"ok": True},
            payload=payload,
            request_hash=generate_request_hash(payload),
            now=now,
        )


def test_expired_record_is_still_reused_until_retention_cleanup_deletes_it():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    service, repository = make_service()
    payload = {"amount": 1000}
    record = repository.create_processing(
        "idem-001",
        generate_request_hash(payload),
        expires_at=datetime(2026, 5, 27, tzinfo=UTC),
    )

    result = service.check_or_start("idem-001", payload, now=now)

    assert result.decision == IdempotencyDecision.ALREADY_PROCESSING
    assert result.record_id == record.id


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
