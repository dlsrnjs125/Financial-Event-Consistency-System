"""Integration tests for transaction event processing."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.domain.event_type import EventType
from app.domain.exceptions import IdempotencyConflict
from app.domain.transaction_status import TransactionStatus
from app.models import import_all_models
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.transaction_event import TransactionEvent
from app.repositories.account_repository import AccountRepository
from app.repositories.idempotency_record_repository import IdempotencyRecordRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.transaction_event_repository import TransactionEventRepository
from app.schemas.transaction_event import TransactionEventCreateRequest
from app.services.idempotency_service import IdempotencyService
from app.services.ledger_service import LedgerService
from app.services.transaction_event_service import TransactionEventService
from app.services.transaction_state_service import TransactionStateService

import_all_models()


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_account(db_session: Session, balance: int = 10000) -> Account:
    account = Account(account_no="1234567890", balance=balance, status="ACTIVE")
    db_session.add(account)
    db_session.commit()
    return account


def build_service(db_session: Session) -> TransactionEventService:
    account_repository = AccountRepository(db_session)
    ledger_repository = LedgerEntryRepository(db_session)
    return TransactionEventService(
        session=db_session,
        idempotency_service=IdempotencyService(IdempotencyRecordRepository(db_session)),
        transaction_event_repository=TransactionEventRepository(db_session),
        account_repository=account_repository,
        ledger_service=LedgerService(account_repository, ledger_repository),
        transaction_state_service=TransactionStateService(db_session),
    )


def make_request(
    external_event_id: str,
    event_type: EventType,
    amount: int = 1000,
    original_external_event_id: str | None = None,
) -> TransactionEventCreateRequest:
    return TransactionEventCreateRequest(
        external_event_id=external_event_id,
        account_no="1234567890",
        event_type=event_type,
        amount=amount,
        currency="KRW",
        occurred_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
        original_external_event_id=original_external_event_id,
    )


def test_deposit_increases_balance(db_session):
    account = create_account(db_session)
    result = build_service(db_session).process(
        "idem-001", make_request("ext-001", EventType.DEPOSIT)
    )

    db_session.refresh(account)
    assert result.status_code == 200
    assert account.balance == 11000
    assert db_session.query(LedgerEntry).count() == 1


def test_withdraw_decreases_balance(db_session):
    account = create_account(db_session)
    result = build_service(db_session).process(
        "idem-001", make_request("ext-001", EventType.WITHDRAW)
    )

    db_session.refresh(account)
    assert result.status_code == 200
    assert account.balance == 9000
    assert db_session.query(LedgerEntry).one().amount == -1000


def test_withdraw_insufficient_balance_fails(db_session):
    account = create_account(db_session, balance=500)
    result = build_service(db_session).process(
        "idem-001", make_request("ext-001", EventType.WITHDRAW)
    )

    db_session.refresh(account)
    event = (
        db_session.query(TransactionEvent)
        .filter(TransactionEvent.external_event_id == "ext-001")
        .one()
    )
    assert result.status_code == 422
    assert account.balance == 500
    assert event.status == TransactionStatus.FAILED.value
    assert db_session.query(LedgerEntry).count() == 0


def test_same_external_event_id_is_processed_once(db_session):
    account = create_account(db_session)
    service = build_service(db_session)
    request = make_request("ext-001", EventType.DEPOSIT)

    first = service.process("idem-001", request)
    second = service.process("idem-002", request)

    db_session.refresh(account)
    assert first.body["duplicated"] is False
    assert second.body["duplicated"] is True
    assert db_session.query(TransactionEvent).count() == 1
    assert db_session.query(LedgerEntry).count() == 1
    assert account.balance == 11000


def test_same_external_event_id_with_different_body_is_rejected(db_session):
    account = create_account(db_session)
    service = build_service(db_session)
    first = service.process("idem-001", make_request("ext-001", EventType.DEPOSIT))
    second = service.process(
        "idem-002", make_request("ext-001", EventType.DEPOSIT, amount=2000)
    )

    db_session.refresh(account)
    assert first.status_code == 200
    assert second.status_code == 422
    assert second.body["code"] == "InvalidTransactionEvent"
    assert db_session.query(TransactionEvent).count() == 1
    assert db_session.query(LedgerEntry).count() == 1
    assert account.balance == 11000


def test_same_idempotency_key_same_body_replays_response(db_session):
    create_account(db_session)
    service = build_service(db_session)
    request = make_request("ext-001", EventType.DEPOSIT)

    first = service.process("idem-001", request)
    second = service.process("idem-001", request)

    assert first.body == second.body
    assert db_session.query(TransactionEvent).count() == 1
    assert db_session.query(LedgerEntry).count() == 1


def test_same_idempotency_key_different_body_conflicts(db_session):
    create_account(db_session)
    service = build_service(db_session)
    service.process("idem-001", make_request("ext-001", EventType.DEPOSIT))

    with pytest.raises(IdempotencyConflict):
        service.process("idem-001", make_request("ext-002", EventType.DEPOSIT))


def test_cancel_deposit_restores_balance(db_session):
    account = create_account(db_session)
    service = build_service(db_session)
    service.process("idem-001", make_request("ext-001", EventType.DEPOSIT))

    result = service.process(
        "idem-002",
        make_request(
            "ext-cancel-001",
            EventType.CANCEL,
            original_external_event_id="ext-001",
        ),
    )

    db_session.refresh(account)
    original = (
        db_session.query(TransactionEvent)
        .filter(TransactionEvent.external_event_id == "ext-001")
        .one()
    )
    assert result.status_code == 200
    assert account.balance == 10000
    assert original.status == TransactionStatus.CANCELLED.value
    assert db_session.query(LedgerEntry).count() == 2


def test_cancel_withdraw_restores_balance(db_session):
    account = create_account(db_session)
    service = build_service(db_session)
    service.process("idem-001", make_request("ext-001", EventType.WITHDRAW))

    service.process(
        "idem-002",
        make_request(
            "ext-cancel-001",
            EventType.CANCEL,
            original_external_event_id="ext-001",
        ),
    )

    db_session.refresh(account)
    assert account.balance == 10000


def test_settled_original_cannot_be_cancelled(db_session):
    create_account(db_session)
    service = build_service(db_session)
    service.process("idem-001", make_request("ext-001", EventType.DEPOSIT))
    original = (
        db_session.query(TransactionEvent)
        .filter(TransactionEvent.external_event_id == "ext-001")
        .one()
    )
    original.status = TransactionStatus.SETTLED.value
    db_session.commit()

    result = service.process(
        "idem-002",
        make_request(
            "ext-cancel-001",
            EventType.CANCEL,
            original_external_event_id="ext-001",
        ),
    )

    cancel_event = (
        db_session.query(TransactionEvent)
        .filter(TransactionEvent.external_event_id == "ext-cancel-001")
        .one()
    )
    assert result.status_code == 409
    assert cancel_event.status == TransactionStatus.FAILED.value


def test_already_cancelled_original_cannot_be_cancelled_again(db_session):
    create_account(db_session)
    service = build_service(db_session)
    service.process("idem-001", make_request("ext-001", EventType.DEPOSIT))
    service.process(
        "idem-002",
        make_request(
            "ext-cancel-001",
            EventType.CANCEL,
            original_external_event_id="ext-001",
        ),
    )

    result = service.process(
        "idem-003",
        make_request(
            "ext-cancel-002",
            EventType.CANCEL,
            original_external_event_id="ext-001",
        ),
    )

    assert result.status_code == 409
