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


class MissingIdempotencyKey(Exception):
    def __init__(self) -> None:
        super().__init__("Idempotency-Key header is required")


class InvalidIdempotencyKey(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class IdempotencyConflict(Exception):
    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(
            "Idempotency-Key was already used with a different request body"
        )


class InvalidIdempotencyState(Exception):
    def __init__(self, current_status: str, attempted_status: str) -> None:
        self.current_status = current_status
        self.attempted_status = attempted_status
        super().__init__(
            f"Cannot mark idempotency record from {current_status} "
            f"to {attempted_status}."
        )


class InvalidTransactionEvent(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AccountNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("Account not found")


class InsufficientBalance(Exception):
    def __init__(self) -> None:
        super().__init__("Insufficient account balance")


class OriginalTransactionNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("Original transaction event not found")


class TransactionAlreadyCancelled(Exception):
    def __init__(self) -> None:
        super().__init__("Original transaction event is already cancelled")


class TransactionAlreadySettled(Exception):
    def __init__(self) -> None:
        super().__init__("Settled transaction event cannot be cancelled")


class RecoveryCaseNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("Recovery case not found")


class InvalidRecoveryCaseTransition(Exception):
    def __init__(self, current_status: str, next_status: str) -> None:
        self.current_status = current_status
        self.next_status = next_status
        super().__init__(
            f"Cannot transition recovery case from {current_status} to {next_status}."
        )


class RecoveryApprovalRequired(Exception):
    def __init__(self) -> None:
        super().__init__("Recovery case requires manual approval before execution")


class RecoveryApprovalMissingActor(Exception):
    def __init__(self) -> None:
        super().__init__("Recovery approval requires approved_by")


class UnsafeAnalyzerResult(Exception):
    def __init__(self) -> None:
        super().__init__("Analyzer result contains sensitive data metadata")


class UnsupportedAnalyzerClassification(Exception):
    def __init__(self, classification: str) -> None:
        self.classification = classification
        super().__init__(
            "Analyzer classification is not supported for PH4 recovery case "
            f"creation: {classification}"
        )


class QuarantineRecordNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("Quarantine record not found")


class TargetQuarantined(Exception):
    def __init__(self, target_type: str, quarantine_id: str) -> None:
        self.target_type = target_type
        self.quarantine_id = quarantine_id
        super().__init__(f"{target_type} target is quarantined")
