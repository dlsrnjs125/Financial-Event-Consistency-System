"""Service for transaction event state changes."""

from sqlalchemy.orm import Session

from app.domain.transaction_state_machine import TransactionStateMachine
from app.domain.transaction_status import TransactionStatus
from app.models.event_state_history import EventStateHistory
from app.models.transaction_event import TransactionEvent
from app.observability.metrics import record_state_transition
from app.repositories.event_state_history_repository import EventStateHistoryRepository


class TransactionStateService:
    """Apply status transitions and append EventStateHistory rows.

    The service deliberately does not commit, create ledger entries, or update balances.
    Callers own transaction boundaries in later phases.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.history_repository = EventStateHistoryRepository(session)

    def change_status(
        self,
        transaction_event: TransactionEvent,
        next_status: TransactionStatus | str,
        reason: str | None = None,
    ) -> EventStateHistory:
        current_status = TransactionStatus(transaction_event.status)
        normalized_next_status = TransactionStatus(next_status)

        try:
            TransactionStateMachine.validate_transition(
                current_status, normalized_next_status
            )
        except Exception:
            record_state_transition(
                current_status.value,
                normalized_next_status.value,
                "rejected",
            )
            raise

        history = self.history_repository.add(
            transaction_event_id=transaction_event.id,
            old_status=current_status,
            new_status=normalized_next_status,
            reason=reason,
        )
        transaction_event.status = normalized_next_status.value
        self.session.flush()
        record_state_transition(
            current_status.value,
            normalized_next_status.value,
            "allowed",
        )
        return history
