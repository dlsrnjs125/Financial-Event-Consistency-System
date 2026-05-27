"""Transaction event ORM model."""

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


class TransactionEvent(Base):
    __tablename__ = "transaction_events"
    __table_args__ = (
        UniqueConstraint(
            "external_event_id", name="uq_transaction_events_external_event_id"
        ),
        Index("ix_transaction_events_account_id", "account_id"),
        Index("ix_transaction_events_idempotency_key", "idempotency_key"),
        Index("ix_transaction_events_status", "status"),
        Index("ix_transaction_events_occurred_at", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="KRW"
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    account = relationship("Account", back_populates="transaction_events")
    ledger_entry = relationship(
        "LedgerEntry", back_populates="transaction_event", uselist=False
    )
    state_histories = relationship(
        "EventStateHistory",
        back_populates="transaction_event",
        cascade="all, delete-orphan",
    )
