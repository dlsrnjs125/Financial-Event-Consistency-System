"""Repository for ledger entry persistence operations."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry


class LedgerEntryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_transaction_event_id(
        self, transaction_event_id: int
    ) -> LedgerEntry | None:
        return (
            self.session.query(LedgerEntry)
            .filter(LedgerEntry.transaction_event_id == transaction_event_id)
            .one_or_none()
        )

    def create(
        self,
        transaction_event_id: int,
        account_id: int,
        entry_type: str,
        amount: int,
        balance_after: int,
    ) -> LedgerEntry:
        ledger_entry = LedgerEntry(
            transaction_event_id=transaction_event_id,
            account_id=account_id,
            entry_type=entry_type,
            amount=amount,
            balance_after=balance_after,
        )
        self.session.add(ledger_entry)
        self.session.flush()
        return ledger_entry

    def sum_amount_by_account_id(self, account_id: int) -> int:
        value = (
            self.session.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
            .filter(LedgerEntry.account_id == account_id)
            .scalar()
        )
        return int(value or 0)
