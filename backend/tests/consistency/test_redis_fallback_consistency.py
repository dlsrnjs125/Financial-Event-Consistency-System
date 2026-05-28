"""Consistency tests for Redis fallback behavior."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.cache.redis_lock import RedisLockResult
from app.db.base import Base
from app.domain.event_type import EventType
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


class UnavailableRedisLock:
    def acquire(self, key):
        return RedisLockResult(
            acquired=False,
            token=None,
            redis_available=False,
            reason="redis unavailable",
        )

    def release(self, key, token):
        raise AssertionError("release should not be called without an acquired lock")


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


def make_request(
    external_event_id: str,
    event_type: EventType,
    amount: int = 1000,
) -> TransactionEventCreateRequest:
    return TransactionEventCreateRequest(
        external_event_id=external_event_id,
        account_no="1234567890",
        event_type=event_type,
        amount=amount,
        currency="KRW",
        occurred_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
    )


def build_service_with_unavailable_redis(db_session):
    account_repository = AccountRepository(db_session)
    ledger_repository = LedgerEntryRepository(db_session)
    return TransactionEventService(
        session=db_session,
        idempotency_service=IdempotencyService(IdempotencyRecordRepository(db_session)),
        transaction_event_repository=TransactionEventRepository(db_session),
        account_repository=account_repository,
        ledger_service=LedgerService(account_repository, ledger_repository),
        transaction_state_service=TransactionStateService(db_session),
        redis_lock=UnavailableRedisLock(),
    )


def test_redis_down_still_processes_same_event_once(db_session):
    account = create_account(db_session)
    service = build_service_with_unavailable_redis(db_session)
    request = make_request("ext-redis-down-001", EventType.DEPOSIT)

    first = service.process("idem-redis-down-001", request)
    second = service.process("idem-redis-down-002", request)

    db_session.refresh(account)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.body["duplicated"] is True
    assert db_session.query(TransactionEvent).count() == 1
    assert db_session.query(LedgerEntry).count() == 1
    assert account.balance == 11000
