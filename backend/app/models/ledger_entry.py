"""Ledger entry ORM model."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "transaction_event_id", name="uq_ledger_entries_transaction_event_id"
        ),
        Index("ix_ledger_entries_account_id", "account_id"),
        Index("ix_ledger_entries_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    transaction_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transaction_events.id"), nullable=False
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    transaction_event = relationship("TransactionEvent", back_populates="ledger_entry")
    account = relationship("Account", back_populates="ledger_entries")
