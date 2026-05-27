"""Schemas for transaction event APIs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.event_type import EventType


def mask_account_no(account_no: str) -> str:
    if len(account_no) <= 4:
        return "*" * len(account_no)
    return f"{'*' * (len(account_no) - 4)}{account_no[-4:]}"


class TransactionEventCreateRequest(BaseModel):
    external_event_id: str = Field(..., min_length=1, max_length=128)
    account_no: str = Field(..., min_length=1, max_length=64)
    event_type: EventType
    amount: int = Field(..., gt=0)
    currency: str = Field(default="KRW", min_length=1, max_length=10)
    occurred_at: datetime
    original_external_event_id: str | None = Field(default=None, max_length=128)

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_cancel_reference(self) -> "TransactionEventCreateRequest":
        if self.event_type == EventType.CANCEL and not self.original_external_event_id:
            raise ValueError("CANCEL requires original_external_event_id")
        if self.event_type != EventType.CANCEL and self.original_external_event_id:
            raise ValueError(
                "original_external_event_id is allowed only for CANCEL events"
            )
        return self


class TransactionEventResponse(BaseModel):
    event_id: str
    external_event_id: str
    status: str
    processed: bool
    duplicated: bool
    balance_after: int


class TransactionEventStatusResponse(BaseModel):
    event_id: str
    external_event_id: str
    event_type: str
    status: str
    amount: int
    currency: str
    occurred_at: datetime
    created_at: datetime


class AccountBalanceResponse(BaseModel):
    account_no: str
    balance: int
    currency: str = "KRW"
    as_of: datetime


class TransactionProcessingResponse(BaseModel):
    status_code: int
    body: dict[str, Any]
