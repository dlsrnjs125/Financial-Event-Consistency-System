"""Recovery case and quarantine domain values."""

from enum import Enum


class RecoveryCaseStatus(str, Enum):
    OPEN = "OPEN"
    AUTO_ANALYZED = "AUTO_ANALYZED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class RecoveryCaseType(str, Enum):
    STALE_PROCESSING = "STALE_PROCESSING"
    BALANCE_MISMATCH = "BALANCE_MISMATCH"
    DUPLICATE_LEDGER = "DUPLICATE_LEDGER"
    ORPHAN_IDEMPOTENCY = "ORPHAN_IDEMPOTENCY"
    FAILOVER_IN_DOUBT = "FAILOVER_IN_DOUBT"
    CONSISTENCY_ISSUE_CANDIDATE = "CONSISTENCY_ISSUE_CANDIDATE"
    WRITE_SUSPENDED_UNKNOWN_DEPENDENCY = "WRITE_SUSPENDED_UNKNOWN_DEPENDENCY"
    POSTGRES_DOWN_WRITE_SUSPENDED = "POSTGRES_DOWN_WRITE_SUSPENDED"


class RecoveryProposedAction(str, Enum):
    NOOP_REVIEW_ONLY = "NOOP_REVIEW_ONLY"
    MARK_COMPLETED = "MARK_COMPLETED"
    MARK_FAILED_RETRYABLE = "MARK_FAILED_RETRYABLE"
    REPLAY_EVENT = "REPLAY_EVENT"
    COMPENSATE_LEDGER = "COMPENSATE_LEDGER"
    KEEP_QUARANTINED = "KEEP_QUARANTINED"


class QuarantineTargetType(str, Enum):
    ACCOUNT = "ACCOUNT"
    CLIENT = "CLIENT"
    EVENT = "EVENT"
    GLOBAL_WRITE = "GLOBAL_WRITE"


ALLOWED_RECOVERY_TRANSITIONS: dict[RecoveryCaseStatus, set[RecoveryCaseStatus]] = {
    RecoveryCaseStatus.OPEN: {
        RecoveryCaseStatus.AUTO_ANALYZED,
        RecoveryCaseStatus.WAITING_APPROVAL,
        RecoveryCaseStatus.REJECTED,
        RecoveryCaseStatus.CLOSED,
    },
    RecoveryCaseStatus.AUTO_ANALYZED: {
        RecoveryCaseStatus.WAITING_APPROVAL,
        RecoveryCaseStatus.APPROVED,
        RecoveryCaseStatus.REJECTED,
        RecoveryCaseStatus.CLOSED,
    },
    RecoveryCaseStatus.WAITING_APPROVAL: {
        RecoveryCaseStatus.APPROVED,
        RecoveryCaseStatus.REJECTED,
        RecoveryCaseStatus.CLOSED,
    },
    RecoveryCaseStatus.APPROVED: {
        RecoveryCaseStatus.EXECUTING,
        RecoveryCaseStatus.REJECTED,
        RecoveryCaseStatus.CLOSED,
    },
    RecoveryCaseStatus.EXECUTING: {
        RecoveryCaseStatus.EXECUTED,
        RecoveryCaseStatus.EXECUTION_FAILED,
    },
    RecoveryCaseStatus.EXECUTION_FAILED: {
        RecoveryCaseStatus.WAITING_APPROVAL,
        RecoveryCaseStatus.REJECTED,
        RecoveryCaseStatus.CLOSED,
    },
    RecoveryCaseStatus.EXECUTED: {RecoveryCaseStatus.CLOSED},
    RecoveryCaseStatus.REJECTED: {RecoveryCaseStatus.CLOSED},
    RecoveryCaseStatus.CLOSED: set(),
}


def case_type_from_classification(classification: str) -> RecoveryCaseType:
    try:
        return RecoveryCaseType(classification)
    except ValueError:
        return RecoveryCaseType.CONSISTENCY_ISSUE_CANDIDATE


def proposed_action_for_case_type(
    case_type: RecoveryCaseType,
) -> RecoveryProposedAction:
    if case_type == RecoveryCaseType.CONSISTENCY_ISSUE_CANDIDATE:
        return RecoveryProposedAction.KEEP_QUARANTINED
    return RecoveryProposedAction.NOOP_REVIEW_ONLY
