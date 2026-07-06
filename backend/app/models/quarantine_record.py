"""Quarantine record ORM model."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuarantineRecord(Base):
    __tablename__ = "quarantine_records"
    __table_args__ = (
        Index(
            "ix_quarantine_records_active_target",
            "active",
            "target_type",
            "target_id",
        ),
        Index("ix_quarantine_records_quarantine_id", "quarantine_id", unique=True),
        Index(
            "ix_quarantine_records_source_recovery_case_id", "source_recovery_case_id"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    quarantine_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_recovery_case_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("recovery_cases.id"),
        nullable=True,
    )
    source_incident_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    activated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    source_recovery_case = relationship("RecoveryCase")
