"""Event state history ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EventStateHistory(Base):
    __tablename__ = "event_state_histories"
    __table_args__ = (
        Index("ix_event_state_histories_transaction_event_id", "transaction_event_id"),
        Index("ix_event_state_histories_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transaction_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transaction_events.id"), nullable=False
    )
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    transaction_event = relationship(
        "TransactionEvent", back_populates="state_histories"
    )
