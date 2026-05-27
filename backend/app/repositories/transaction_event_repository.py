"""Repository for transaction event persistence operations."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.transaction_status import TransactionStatus
from app.models.transaction_event import TransactionEvent


class TransactionEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, event_id: int) -> TransactionEvent | None:
        return (
            self.session.query(TransactionEvent)
            .filter(TransactionEvent.id == event_id)
            .one_or_none()
        )

    def get_by_external_event_id(
        self, external_event_id: str
    ) -> TransactionEvent | None:
        return (
            self.session.query(TransactionEvent)
            .filter(TransactionEvent.external_event_id == external_event_id)
            .one_or_none()
        )

    def get_original_for_cancel(
        self, original_external_event_id: str
    ) -> TransactionEvent | None:
        return self.get_by_external_event_id(original_external_event_id)

    def create_received(
        self,
        external_event_id: str,
        idempotency_key: str,
        account_id: int,
        event_type: str,
        amount: int,
        currency: str,
        occurred_at: datetime,
    ) -> TransactionEvent:
        event = TransactionEvent(
            external_event_id=external_event_id,
            idempotency_key=idempotency_key,
            account_id=account_id,
            event_type=event_type,
            amount=amount,
            currency=currency,
            status=TransactionStatus.RECEIVED.value,
            occurred_at=occurred_at,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def update_status(
        self, event: TransactionEvent, status: TransactionStatus | str
    ) -> TransactionEvent:
        event.status = TransactionStatus(status).value
        self.session.flush()
        return event
