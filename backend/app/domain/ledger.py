"""Ledger amount calculation rules."""

from decimal import Decimal

from app.domain.event_type import EventType
from app.domain.exceptions import InvalidTransactionEvent


def _normalize_event_type(event_type: EventType | str) -> EventType:
    try:
        return EventType(event_type)
    except ValueError as exc:
        raise InvalidTransactionEvent("Unsupported transaction event type") from exc


def calculate_ledger_amount(
    event_type: EventType | str,
    amount: Decimal,
    original_event_type: EventType | str | None = None,
) -> Decimal:
    if amount <= 0:
        raise InvalidTransactionEvent("Transaction amount must be greater than zero")

    normalized_event_type = _normalize_event_type(event_type)

    if normalized_event_type == EventType.DEPOSIT:
        return amount
    if normalized_event_type == EventType.WITHDRAW:
        return -amount

    if original_event_type is None:
        raise InvalidTransactionEvent("CANCEL requires original_event_type")

    normalized_original_type = _normalize_event_type(original_event_type)
    if normalized_original_type == EventType.DEPOSIT:
        return -amount
    if normalized_original_type == EventType.WITHDRAW:
        return amount

    raise InvalidTransactionEvent("CANCEL supports only DEPOSIT or WITHDRAW originals")
