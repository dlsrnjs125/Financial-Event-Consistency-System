"""Service for applying transaction events to account ledger."""

from decimal import Decimal

from app.domain.event_type import EventType
from app.domain.exceptions import (
    InsufficientBalance,
    InvalidTransactionEvent,
    TransactionAlreadyCancelled,
    TransactionAlreadySettled,
)
from app.domain.ledger import calculate_ledger_amount
from app.domain.transaction_status import TransactionStatus
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.transaction_event import TransactionEvent
from app.repositories.account_repository import AccountRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository


class LedgerService:
    def __init__(
        self,
        account_repository: AccountRepository,
        ledger_entry_repository: LedgerEntryRepository,
    ) -> None:
        self.account_repository = account_repository
        self.ledger_entry_repository = ledger_entry_repository

    def apply_event(
        self,
        account: Account,
        transaction_event: TransactionEvent,
        original_event: TransactionEvent | None = None,
    ) -> LedgerEntry:
        event_type = EventType(transaction_event.event_type)
        original_event_type = None
        if event_type == EventType.CANCEL:
            if original_event is None:
                raise InvalidTransactionEvent("CANCEL requires original event")
            self._validate_cancel_original(transaction_event, original_event)
            original_event_type = EventType(original_event.event_type)

        ledger_amount = int(
            calculate_ledger_amount(
                event_type=event_type,
                amount=Decimal(transaction_event.amount),
                original_event_type=original_event_type,
            )
        )
        new_balance = account.balance + ledger_amount
        if new_balance < 0:
            raise InsufficientBalance()

        entry_type = "CREDIT" if ledger_amount > 0 else "DEBIT"
        ledger_entry = self.ledger_entry_repository.create(
            transaction_event_id=transaction_event.id,
            account_id=account.id,
            entry_type=entry_type,
            amount=ledger_amount,
            balance_after=new_balance,
        )
        self.account_repository.update_balance(account, new_balance)
        return ledger_entry

    def _validate_cancel_original(
        self, cancel_event: TransactionEvent, original_event: TransactionEvent
    ) -> None:
        if original_event.event_type not in {
            EventType.DEPOSIT.value,
            EventType.WITHDRAW.value,
        }:
            raise InvalidTransactionEvent("CANCEL original must be DEPOSIT or WITHDRAW")
        if original_event.status == TransactionStatus.SETTLED.value:
            raise TransactionAlreadySettled()
        if original_event.status == TransactionStatus.CANCELLED.value:
            raise TransactionAlreadyCancelled()
        if original_event.status != TransactionStatus.COMPLETED.value:
            raise InvalidTransactionEvent("CANCEL original must be COMPLETED")
        if original_event.account_id != cancel_event.account_id:
            raise InvalidTransactionEvent("CANCEL account does not match original")
        if original_event.amount != cancel_event.amount:
            raise InvalidTransactionEvent("CANCEL amount does not match original")
        if original_event.currency != cancel_event.currency:
            raise InvalidTransactionEvent("CANCEL currency does not match original")
