"""Integration-style tests for IdempotencyRecordRepository."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.domain.idempotency_status import IdempotencyStatus
from app.models import import_all_models
from app.models.idempotency_record import IdempotencyRecord
from app.repositories.idempotency_record_repository import IdempotencyRecordRepository

import_all_models()


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[IdempotencyRecord.__table__])
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=[IdempotencyRecord.__table__])
        engine.dispose()


def test_create_processing_and_get_by_key(db_session):
    repository = IdempotencyRecordRepository(db_session)
    expires_at = datetime(2026, 5, 29, tzinfo=UTC)

    record = repository.create_processing(
        idempotency_key="idem-001",
        request_hash="a" * 64,
        expires_at=expires_at,
    )

    assert record.id is not None
    assert record.status == IdempotencyStatus.PROCESSING.value
    assert repository.get_by_key("idem-001") == record


def test_create_processing_duplicate_key_raises_integrity_error(db_session):
    repository = IdempotencyRecordRepository(db_session)
    expires_at = datetime(2026, 5, 29, tzinfo=UTC)
    repository.create_processing("idem-001", "a" * 64, expires_at)

    with pytest.raises(IntegrityError):
        repository.create_processing("idem-001", "a" * 64, expires_at)


def test_mark_completed_updates_status_and_response(db_session):
    repository = IdempotencyRecordRepository(db_session)
    record = repository.create_processing(
        "idem-001", "a" * 64, datetime(2026, 5, 29, tzinfo=UTC)
    )
    completed_at = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)

    repository.mark_completed(record, 200, {"event_id": "evt-001"}, completed_at)

    assert record.status == IdempotencyStatus.COMPLETED.value
    assert record.response_code == 200
    assert record.response_body == {"event_id": "evt-001"}
    assert record.completed_at == completed_at
    assert record.locked_until is None


def test_mark_failed_updates_status_and_response(db_session):
    repository = IdempotencyRecordRepository(db_session)
    record = repository.create_processing(
        "idem-001", "a" * 64, datetime(2026, 5, 29, tzinfo=UTC)
    )
    failed_at = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)

    repository.mark_failed(
        record,
        failed_at,
        422,
        {"error": "invalid"},
        error_message="invalid request body",
    )

    assert record.status == IdempotencyStatus.FAILED.value
    assert record.response_code == 422
    assert record.response_body == {"error": "invalid"}
    assert record.error_message == "invalid request body"
    assert record.updated_at == failed_at
    assert record.locked_until is None


def test_list_and_delete_expired_records(db_session):
    repository = IdempotencyRecordRepository(db_session)
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    expired = repository.create_processing(
        "idem-expired", "a" * 64, now - timedelta(seconds=1)
    )
    repository.create_processing("idem-active", "b" * 64, now + timedelta(days=1))

    assert repository.list_expired(now) == [expired]
    assert repository.delete_expired(now) == 1
    assert repository.get_by_key("idem-expired") is None
    assert repository.get_by_key("idem-active") is not None
