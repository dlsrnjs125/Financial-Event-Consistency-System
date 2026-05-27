"""SQLAlchemy ORM model package exports."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.event_state_history import EventStateHistory
    from app.models.idempotency_record import IdempotencyRecord
    from app.models.ledger_entry import LedgerEntry
    from app.models.transaction_event import TransactionEvent

_MODEL_EXPORTS = {
    "Account": "app.models.account",
    "TransactionEvent": "app.models.transaction_event",
    "LedgerEntry": "app.models.ledger_entry",
    "IdempotencyRecord": "app.models.idempotency_record",
    "EventStateHistory": "app.models.event_state_history",
}


def import_all_models() -> None:
    """Import all model modules so Base.metadata is populated."""
    for module_name in _MODEL_EXPORTS.values():
        import_module(module_name)


def __getattr__(name: str) -> Any:
    if name not in _MODEL_EXPORTS:
        raise AttributeError(f"module 'app.models' has no attribute {name!r}")

    module = import_module(_MODEL_EXPORTS[name])
    return getattr(module, name)


__all__ = [
    "Account",
    "TransactionEvent",
    "LedgerEntry",
    "IdempotencyRecord",
    "EventStateHistory",
    "import_all_models",
]
