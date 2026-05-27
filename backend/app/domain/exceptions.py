"""Domain exceptions."""

from app.domain.transaction_status import TransactionStatus


class InvalidStateTransition(Exception):
    """Raised when a transaction event attempts a forbidden state transition."""

    def __init__(
        self,
        current_status: TransactionStatus,
        next_status: TransactionStatus,
        message: str | None = None,
    ) -> None:
        self.current_status = current_status
        self.next_status = next_status
        detail = (
            message
            or f"Cannot transition from {current_status.value} to {next_status.value}."
        )
        super().__init__(detail)
