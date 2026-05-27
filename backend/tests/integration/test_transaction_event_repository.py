"""Integration tests for transaction event repository."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.domain.event_type import EventType
from app.models import import_all_models
from app.models.account import Account
from app.repositories.account_repository import AccountRepository
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


def create_account(db_session):
    account = Account(account_no="1234567890", balance=10000, status="ACTIVE")
    db_session.add(account)
    db_session.flush()
    return account


def test_transaction_event_create_and_get_by_external_event_id(db_session):
    account = create_account(db_session)
    repository = TransactionEventRepository(db_session)

    event = repository.create_received(
        external_event_id="ext-001",
        idempotency_key="idem-001",
        account_id=account.id,
        event_type=EventType.DEPOSIT.value,
        amount=1000,
        currency="KRW",
        occurred_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
    )

    assert event.id is not None
    assert repository.get_by_external_event_id("ext-001") == event


def test_transaction_event_external_event_id_is_unique(db_session):
    account = create_account(db_session)
    repository = TransactionEventRepository(db_session)
    kwargs = {
        "external_event_id": "ext-001",
        "idempotency_key": "idem-001",
        "account_id": account.id,
        "event_type": EventType.DEPOSIT.value,
        "amount": 1000,
        "currency": "KRW",
        "occurred_at": datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
    }
    repository.create_received(**kwargs)

    with pytest.raises(IntegrityError):
        repository.create_received(**{**kwargs, "idempotency_key": "idem-002"})


def test_account_balance_update(db_session):
    account = create_account(db_session)
    repository = AccountRepository(db_session)

    repository.update_balance(account, 12000)

    assert repository.get_by_account_no("1234567890").balance == 12000
    assert repository.get_by_account_no_for_update("1234567890") == account
