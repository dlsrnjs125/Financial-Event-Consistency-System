"""Unit tests for ledger amount and balance policies."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.event_type import EventType
from app.domain.exceptions import InsufficientBalance, InvalidTransactionEvent
from app.domain.ledger import calculate_ledger_amount
from app.domain.transaction_status import TransactionStatus
from app.services.ledger_service import LedgerService


class FakeAccountRepository:
    def update_balance(self, account, new_balance: int):
        account.balance = new_balance
        return account


class FakeLedgerEntryRepository:
    def __init__(self) -> None:
        self.entries = []

    def create(
        self, transaction_event_id, account_id, entry_type, amount, balance_after
    ):
        entry = SimpleNamespace(
            transaction_event_id=transaction_event_id,
            account_id=account_id,
            entry_type=entry_type,
            amount=amount,
            balance_after=balance_after,
        )
        self.entries.append(entry)
        return entry


def make_service():
    ledger_repository = FakeLedgerEntryRepository()
    return LedgerService(FakeAccountRepository(), ledger_repository), ledger_repository


def test_deposit_amount_is_positive():
    assert calculate_ledger_amount(EventType.DEPOSIT, Decimal("1000")) == Decimal(
        "1000"
    )


def test_withdraw_amount_is_negative():
    assert calculate_ledger_amount(EventType.WITHDRAW, Decimal("1000")) == Decimal(
        "-1000"
    )


def test_cancel_deposit_amount_is_negative():
    assert calculate_ledger_amount(
        EventType.CANCEL, Decimal("1000"), EventType.DEPOSIT
    ) == Decimal("-1000")


def test_cancel_withdraw_amount_is_positive():
    assert calculate_ledger_amount(
        EventType.CANCEL, Decimal("1000"), EventType.WITHDRAW
    ) == Decimal("1000")


def test_amount_must_be_positive():
    with pytest.raises(InvalidTransactionEvent):
        calculate_ledger_amount(EventType.DEPOSIT, Decimal("0"))


def test_cancel_requires_original_event_type():
    with pytest.raises(InvalidTransactionEvent):
        calculate_ledger_amount(EventType.CANCEL, Decimal("1000"))


def test_withdraw_insufficient_balance_raises():
    service, _ = make_service()
    account = SimpleNamespace(id=1, balance=500)
    event = SimpleNamespace(
        id=1,
        account_id=1,
        event_type=EventType.WITHDRAW.value,
        amount=1000,
        currency="KRW",
    )

    with pytest.raises(InsufficientBalance):
        service.apply_event(account, event)


def test_cancel_deposit_creates_debit_and_restores_balance():
    service, ledger_repository = make_service()
    account = SimpleNamespace(id=1, balance=11000)
    cancel_event = SimpleNamespace(
        id=2,
        account_id=1,
        event_type=EventType.CANCEL.value,
        amount=1000,
        currency="KRW",
    )
    original = SimpleNamespace(
        id=1,
        account_id=1,
        event_type=EventType.DEPOSIT.value,
        amount=1000,
        currency="KRW",
        status=TransactionStatus.COMPLETED.value,
    )

    ledger = service.apply_event(account, cancel_event, original)

    assert ledger.amount == -1000
    assert ledger.entry_type == "DEBIT"
    assert ledger.balance_after == 10000
    assert ledger_repository.entries == [ledger]
