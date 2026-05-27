"""SQLAlchemy declarative base and model metadata registry."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so Alembic autogenerate can discover Base.metadata.
from app.models import (  # noqa: E402,F401
    Account,
    EventStateHistory,
    IdempotencyRecord,
    LedgerEntry,
    TransactionEvent,
)
