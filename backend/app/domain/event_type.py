"""Transaction event type definitions."""

from enum import StrEnum


class EventType(StrEnum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    CANCEL = "CANCEL"
