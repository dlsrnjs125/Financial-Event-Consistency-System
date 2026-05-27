"""Transaction event state machine."""

from app.domain.exceptions import InvalidStateTransition
from app.domain.transaction_status import TransactionStatus


class TransactionStateMachine:
    """Validate transaction event status transitions."""

    ALLOWED_TRANSITIONS: dict[TransactionStatus, frozenset[TransactionStatus]] = {
        TransactionStatus.RECEIVED: frozenset(
            {TransactionStatus.VALIDATED, TransactionStatus.FAILED}
        ),
        TransactionStatus.VALIDATED: frozenset(
            {TransactionStatus.PROCESSING, TransactionStatus.FAILED}
        ),
        TransactionStatus.PROCESSING: frozenset(
            {TransactionStatus.COMPLETED, TransactionStatus.FAILED}
        ),
        TransactionStatus.COMPLETED: frozenset(
            {TransactionStatus.SETTLED, TransactionStatus.CANCELLED}
        ),
        TransactionStatus.SETTLED: frozenset(),
        TransactionStatus.FAILED: frozenset(),
        TransactionStatus.CANCELLED: frozenset(),
    }

    @classmethod
    def normalize(cls, status: TransactionStatus | str) -> TransactionStatus:
        return (
            status
            if isinstance(status, TransactionStatus)
            else TransactionStatus(status)
        )

    @classmethod
    def allowed_next_statuses(
        cls, current_status: TransactionStatus | str
    ) -> frozenset[TransactionStatus]:
        return cls.ALLOWED_TRANSITIONS[cls.normalize(current_status)]

    @classmethod
    def can_transition(
        cls,
        current_status: TransactionStatus | str,
        next_status: TransactionStatus | str,
    ) -> bool:
        current = cls.normalize(current_status)
        next_ = cls.normalize(next_status)
        return next_ in cls.ALLOWED_TRANSITIONS[current]

    @classmethod
    def validate_transition(
        cls,
        current_status: TransactionStatus | str,
        next_status: TransactionStatus | str,
    ) -> None:
        current = cls.normalize(current_status)
        next_ = cls.normalize(next_status)
        if not cls.can_transition(current, next_):
            allowed = ", ".join(
                status.value for status in cls.allowed_next_statuses(current)
            )
            message = (
                f"Cannot transition from {current.value} to {next_.value}. "
                f"Allowed next statuses: {allowed or 'none'}."
            )
            raise InvalidStateTransition(current, next_, message)

    @classmethod
    def can_cancel(cls, current_status: TransactionStatus | str) -> bool:
        return cls.can_transition(current_status, TransactionStatus.CANCELLED)

    @classmethod
    def validate_cancel_allowed(cls, current_status: TransactionStatus | str) -> None:
        cls.validate_transition(current_status, TransactionStatus.CANCELLED)
