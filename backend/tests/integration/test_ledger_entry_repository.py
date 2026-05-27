"""Integration tests for ledger entry repository."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.domain.event_type import EventType
from app.models import import_all_models
from app.models.account import Account
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.transaction_event_repository import TransactionEventRepository

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


def create_event(db_session):
    account = Account(account_no="1234567890", balance=10000, status="ACTIVE")
    db_session.add(account)
    db_session.flush()
    event = TransactionEventRepository(db_session).create_received(
        external_event_id="ext-001",
        idempotency_key="idem-001",
        account_id=account.id,
        event_type=EventType.DEPOSIT.value,
        amount=1000,
        currency="KRW",
        occurred_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
    )
    return account, event


def test_ledger_entry_create_and_sum(db_session):
    account, event = create_event(db_session)
    repository = LedgerEntryRepository(db_session)

    ledger = repository.create(event.id, account.id, "CREDIT", 1000, 11000)

    assert ledger.id is not None
    assert repository.get_by_transaction_event_id(event.id) == ledger
    assert repository.sum_amount_by_account_id(account.id) == 1000


def test_ledger_entry_transaction_event_id_is_unique(db_session):
    account, event = create_event(db_session)
    repository = LedgerEntryRepository(db_session)
    repository.create(event.id, account.id, "CREDIT", 1000, 11000)

    with pytest.raises(IntegrityError):
        repository.create(event.id, account.id, "CREDIT", 1000, 11000)
