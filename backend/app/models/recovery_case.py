"""Recovery case ORM model."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_recovery_cases_case_id"),
        UniqueConstraint("source_key", name="uq_recovery_cases_source_key"),
        Index("ix_recovery_cases_current_status", "current_status"),
        Index("ix_recovery_cases_case_type", "case_type"),
        Index("ix_recovery_cases_source_incident_id", "source_incident_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    case_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    current_status: Mapped[str] = mapped_column(String(40), nullable=False)
    classification: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence_candidate: Mapped[float | None] = mapped_column(Float, nullable=True)
    account_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("accounts.id"),
        nullable=True,
    )
    transaction_event_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("transaction_events.id"),
        nullable=True,
    )
    external_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detected_by: Mapped[str] = mapped_column(String(80), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_incident_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_analyzer_result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_action: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executing_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_failure_type: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    action_attempt_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    account = relationship("Account")
    transaction_event = relationship("TransactionEvent")
