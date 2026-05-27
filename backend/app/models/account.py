"""Account ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("account_no", name="uq_accounts_account_no"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_no: Mapped[str] = mapped_column(String(64), nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    transaction_events = relationship(
        "TransactionEvent", back_populates="account", cascade="all, delete-orphan"
    )
    ledger_entries = relationship(
        "LedgerEntry", back_populates="account", cascade="all, delete-orphan"
    )
