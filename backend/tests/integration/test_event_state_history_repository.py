"""Integration-style tests for state history persistence helpers."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.domain.exceptions import InvalidStateTransition
from app.domain.transaction_status import TransactionStatus
from app.models.account import Account
from app.models.event_state_history import EventStateHistory
from app.models.transaction_event import TransactionEvent
from app.repositories.event_state_history_repository import EventStateHistoryRepository
from app.services.transaction_state_service import TransactionStateService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Account.__table__,
            TransactionEvent.__table__,
            EventStateHistory.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(
            engine,
            tables=[
                EventStateHistory.__table__,
                TransactionEvent.__table__,
                Account.__table__,
            ],
        )
        engine.dispose()


def create_event(db_session, status=TransactionStatus.RECEIVED) -> TransactionEvent:
    account = Account(id=1, account_no="ACC-001", balance=0, status="ACTIVE")
    event = TransactionEvent(
        id=1,
        external_event_id="BANK-A-20260528-0001",
        idempotency_key="idem-20260528-0001",
        account_id=1,
        event_type="DEPOSIT",
        amount=10000,
        currency="KRW",
        status=status.value,
        occurred_at=datetime.now(UTC),
    )
    db_session.add(account)
    db_session.add(event)
    db_session.flush()
    return event


def test_repository_appends_state_history(db_session):
    create_event(db_session)
    repository = EventStateHistoryRepository(db_session)

    history = repository.add(
        transaction_event_id=1,
        old_status=TransactionStatus.RECEIVED,
        new_status=TransactionStatus.VALIDATED,
        reason="basic validation succeeded",
    )
    db_session.flush()

    assert history.id is not None
    assert history.old_status == "RECEIVED"
    assert history.new_status == "VALIDATED"
    assert history.reason == "basic validation succeeded"


def test_transaction_state_service_changes_status_and_records_history(db_session):
    event = create_event(db_session)
    service = TransactionStateService(db_session)

    history = service.change_status(
        event,
        TransactionStatus.VALIDATED,
        reason="basic validation succeeded",
    )
    db_session.flush()

    assert event.status == "VALIDATED"
    assert history.old_status == "RECEIVED"
    assert history.new_status == "VALIDATED"
    histories = EventStateHistoryRepository(db_session).list_by_transaction_event_id(1)
    assert [item.new_status for item in histories] == ["VALIDATED"]


def test_transaction_state_service_blocks_forbidden_transition(db_session):
    event = create_event(db_session, status=TransactionStatus.COMPLETED)
    service = TransactionStateService(db_session)

    with pytest.raises(InvalidStateTransition):
        service.change_status(event, TransactionStatus.PROCESSING)

    assert event.status == "COMPLETED"
    assert EventStateHistoryRepository(db_session).list_by_transaction_event_id(1) == []
