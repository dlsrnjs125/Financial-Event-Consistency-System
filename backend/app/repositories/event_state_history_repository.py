"""Repository for transaction event state history rows."""

from sqlalchemy.orm import Session

from app.domain.transaction_status import TransactionStatus
from app.models.event_state_history import EventStateHistory


class EventStateHistoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        transaction_event_id: int,
        old_status: TransactionStatus | str | None,
        new_status: TransactionStatus | str,
        reason: str | None = None,
    ) -> EventStateHistory:
        history = EventStateHistory(
            transaction_event_id=transaction_event_id,
            old_status=self._value_or_none(old_status),
            new_status=self._value(new_status),
            reason=reason,
        )
        self.session.add(history)
        return history

    def list_by_transaction_event_id(
        self, transaction_event_id: int
    ) -> list[EventStateHistory]:
        return (
            self.session.query(EventStateHistory)
            .filter(EventStateHistory.transaction_event_id == transaction_event_id)
            .order_by(EventStateHistory.created_at.asc(), EventStateHistory.id.asc())
            .all()
        )

    def get_latest_by_transaction_event_id(
        self, transaction_event_id: int
    ) -> EventStateHistory | None:
        return (
            self.session.query(EventStateHistory)
            .filter(EventStateHistory.transaction_event_id == transaction_event_id)
            .order_by(EventStateHistory.created_at.desc(), EventStateHistory.id.desc())
            .first()
        )

    @staticmethod
    def _value(status: TransactionStatus | str) -> str:
        return status.value if isinstance(status, TransactionStatus) else status

    @classmethod
    def _value_or_none(cls, status: TransactionStatus | str | None) -> str | None:
        return None if status is None else cls._value(status)
