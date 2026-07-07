"""PH5 stale PROCESSING detector and count-only reconciliation service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.domain.idempotency_status import IdempotencyStatus
from app.domain.recovery import (
    QuarantineTargetType,
    RecoveryCaseStatus,
    RecoveryCaseType,
    RecoveryProposedAction,
)
from app.domain.transaction_status import TransactionStatus
from app.models.account import Account
from app.models.idempotency_record import IdempotencyRecord
from app.models.ledger_entry import LedgerEntry
from app.models.recovery_case import RecoveryCase
from app.models.transaction_event import TransactionEvent
from app.services.quarantine_service import QuarantineService
from app.services.recovery_case_service import RecoveryCaseService


@dataclass(frozen=True)
class StaleProcessingCandidate:
    idempotency_record_id: int
    idempotency_key_hash: str
    status: str
    locked_until: str | None
    expires_at: str | None
    created_at: str
    updated_at: str
    matching_transaction_event_exists: bool
    matching_ledger_entry_exists: bool
    account_balance_check: str
    proposed_action: str
    recovery_case_id: str | None = None
    recovery_case_source_key: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "idempotency_record_id": self.idempotency_record_id,
            "idempotency_key_hash": self.idempotency_key_hash,
            "status": self.status,
            "locked_until": self.locked_until,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "matching_transaction_event_exists": self.matching_transaction_event_exists,
            "matching_ledger_entry_exists": self.matching_ledger_entry_exists,
            "account_balance_check": self.account_balance_check,
            "proposed_action": self.proposed_action,
            "recovery_case_id": self.recovery_case_id,
            "recovery_case_source_key": self.recovery_case_source_key,
        }


@dataclass(frozen=True)
class ReconciliationCounts:
    duplicate_ledger_count: int
    duplicate_external_event_count: int
    completed_idempotency_without_transaction_event_count: int
    transaction_event_without_ledger_count: int
    ledger_without_transaction_event_count: int
    account_balance_mismatch_count: int
    stale_processing_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "duplicate_ledger_count": self.duplicate_ledger_count,
            "duplicate_external_event_count": self.duplicate_external_event_count,
            "completed_idempotency_without_transaction_event_count": (
                self.completed_idempotency_without_transaction_event_count
            ),
            "transaction_event_without_ledger_count": (
                self.transaction_event_without_ledger_count
            ),
            "ledger_without_transaction_event_count": (
                self.ledger_without_transaction_event_count
            ),
            "account_balance_mismatch_count": self.account_balance_mismatch_count,
            "stale_processing_count": self.stale_processing_count,
        }


@dataclass(frozen=True)
class RecoveryCaseLink:
    issue_type: str
    case_type: str
    source_key: str
    case_id: str
    quarantine_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_type": self.issue_type,
            "case_type": self.case_type,
            "source_key": self.source_key,
            "case_id": self.case_id,
            "quarantine_id": self.quarantine_id,
        }


class ReconciliationService:
    def __init__(
        self,
        session: Session,
        recovery_case_service: RecoveryCaseService,
        quarantine_service: QuarantineService | None = None,
    ) -> None:
        self.session = session
        self.recovery_case_service = recovery_case_service
        self.quarantine_service = quarantine_service

    def detect_stale_processing(
        self,
        threshold_minutes: int,
        create_recovery_cases: bool = True,
    ) -> list[StaleProcessingCandidate]:
        now = datetime.now(UTC)
        threshold_at = now - timedelta(minutes=threshold_minutes)
        records = (
            self.session.query(IdempotencyRecord)
            .filter(IdempotencyRecord.status == IdempotencyStatus.PROCESSING.value)
            .filter(
                or_(
                    IdempotencyRecord.locked_until.is_not(None)
                    & (IdempotencyRecord.locked_until < now),
                    IdempotencyRecord.updated_at < threshold_at,
                )
            )
            .order_by(IdempotencyRecord.updated_at.asc(), IdempotencyRecord.id.asc())
            .all()
        )

        candidates: list[StaleProcessingCandidate] = []
        for record in records:
            matching_event = self._matching_event(record.idempotency_key)
            matching_ledger = (
                matching_event is not None
                and self._ledger_exists_for_event(matching_event.id)
            )
            proposed_action = self._proposed_stale_action(
                matching_event, matching_ledger
            )
            recovery_case: RecoveryCase | None = None
            if create_recovery_cases:
                recovery_case = self._create_stale_recovery_case(
                    record,
                    matching_event,
                    proposed_action,
                )
            candidates.append(
                StaleProcessingCandidate(
                    idempotency_record_id=record.id,
                    idempotency_key_hash=_safe_hash(record.idempotency_key),
                    status=record.status,
                    locked_until=_iso(record.locked_until),
                    expires_at=_iso(record.expires_at),
                    created_at=_iso_required(record.created_at),
                    updated_at=_iso_required(record.updated_at),
                    matching_transaction_event_exists=matching_event is not None,
                    matching_ledger_entry_exists=bool(matching_ledger),
                    account_balance_check=(
                        "candidate_only"
                        if matching_event is not None
                        else "not_applicable"
                    ),
                    proposed_action=proposed_action,
                    recovery_case_id=(
                        recovery_case.case_id if recovery_case is not None else None
                    ),
                    recovery_case_source_key=(
                        recovery_case.source_key if recovery_case is not None else None
                    ),
                )
            )
        return candidates

    def count_stale_processing(self, threshold_minutes: int) -> int:
        return len(
            self.detect_stale_processing(
                threshold_minutes=threshold_minutes,
                create_recovery_cases=False,
            )
        )

    def reconcile(
        self,
        threshold_minutes: int,
        create_recovery_cases: bool = True,
    ) -> tuple[ReconciliationCounts, list[RecoveryCaseLink]]:
        counts = ReconciliationCounts(
            duplicate_ledger_count=self._duplicate_ledger_count(),
            duplicate_external_event_count=self._duplicate_external_event_count(),
            completed_idempotency_without_transaction_event_count=(
                self._completed_idempotency_without_transaction_event_count()
            ),
            transaction_event_without_ledger_count=(
                self._transaction_event_without_ledger_count()
            ),
            ledger_without_transaction_event_count=(
                self._ledger_without_transaction_event_count()
            ),
            account_balance_mismatch_count=self._account_balance_mismatch_count(),
            stale_processing_count=self.count_stale_processing(threshold_minutes),
        )
        links: list[RecoveryCaseLink] = []
        if create_recovery_cases:
            links.extend(self._create_reconciliation_cases(counts))
        return counts, links

    def _matching_event(self, idempotency_key: str) -> TransactionEvent | None:
        return (
            self.session.query(TransactionEvent)
            .filter(TransactionEvent.idempotency_key == idempotency_key)
            .order_by(TransactionEvent.id.asc())
            .first()
        )

    def _ledger_exists_for_event(self, transaction_event_id: int) -> bool:
        return (
            self.session.query(LedgerEntry.id)
            .filter(LedgerEntry.transaction_event_id == transaction_event_id)
            .first()
            is not None
        )

    def _proposed_stale_action(
        self,
        matching_event: TransactionEvent | None,
        matching_ledger: bool,
    ) -> str:
        if matching_event is not None and matching_ledger:
            return RecoveryProposedAction.MARK_COMPLETED.value
        return RecoveryProposedAction.MARK_FAILED_RETRYABLE.value

    def _create_stale_recovery_case(
        self,
        record: IdempotencyRecord,
        matching_event: TransactionEvent | None,
        proposed_action: str,
    ) -> RecoveryCase:
        return self.recovery_case_service.create_case(
            source_key=f"ph5:stale:{record.id}",
            case_type=RecoveryCaseType.STALE_PROCESSING.value,
            severity="SEV2",
            classification="STALE_PROCESSING_DETECTED",
            confidence_candidate=0.8,
            detected_by="ph5_reconciliation",
            proposed_action=proposed_action,
            approval_required=True,
            status=RecoveryCaseStatus.WAITING_APPROVAL,
            transaction_event_id=matching_event.id if matching_event else None,
            account_id=matching_event.account_id if matching_event else None,
            external_event_id=matching_event.external_event_id
            if matching_event
            else None,
            idempotency_key_hash=_safe_hash(record.idempotency_key),
        )

    def _create_reconciliation_cases(
        self,
        counts: ReconciliationCounts,
    ) -> list[RecoveryCaseLink]:
        links: list[RecoveryCaseLink] = []
        if counts.duplicate_ledger_count > 0:
            links.append(
                self._create_count_case(
                    "duplicate_ledger",
                    RecoveryCaseType.DUPLICATE_LEDGER,
                    RecoveryProposedAction.KEEP_QUARANTINED,
                    "SEV1",
                    counts.duplicate_ledger_count,
                    quarantine_global=True,
                )
            )
        if counts.account_balance_mismatch_count > 0:
            links.append(
                self._create_count_case(
                    "account_balance_mismatch",
                    RecoveryCaseType.BALANCE_MISMATCH,
                    RecoveryProposedAction.KEEP_QUARANTINED,
                    "SEV1",
                    counts.account_balance_mismatch_count,
                    quarantine_global=True,
                )
            )
        if counts.completed_idempotency_without_transaction_event_count > 0:
            links.append(
                self._create_count_case(
                    "completed_idempotency_without_transaction_event",
                    RecoveryCaseType.ORPHAN_IDEMPOTENCY,
                    RecoveryProposedAction.NOOP_REVIEW_ONLY,
                    "SEV2",
                    counts.completed_idempotency_without_transaction_event_count,
                )
            )
        if counts.transaction_event_without_ledger_count > 0:
            links.append(
                self._create_count_case(
                    "transaction_event_without_ledger",
                    RecoveryCaseType.FAILOVER_IN_DOUBT,
                    RecoveryProposedAction.KEEP_QUARANTINED,
                    "SEV1",
                    counts.transaction_event_without_ledger_count,
                    quarantine_global=True,
                )
            )
        if counts.ledger_without_transaction_event_count > 0:
            links.append(
                self._create_count_case(
                    "ledger_without_transaction_event",
                    RecoveryCaseType.CONSISTENCY_ISSUE_CANDIDATE,
                    RecoveryProposedAction.KEEP_QUARANTINED,
                    "SEV1",
                    counts.ledger_without_transaction_event_count,
                    quarantine_global=True,
                )
            )
        return links

    def _create_count_case(
        self,
        issue_type: str,
        case_type: RecoveryCaseType,
        proposed_action: RecoveryProposedAction,
        severity: str,
        count: int,
        quarantine_global: bool = False,
    ) -> RecoveryCaseLink:
        source_key = f"ph5:reconcile:{issue_type}"
        recovery_case = self.recovery_case_service.create_case(
            source_key=source_key,
            case_type=case_type.value,
            severity=severity,
            classification=f"{issue_type.upper()}_DETECTED",
            confidence_candidate=0.85,
            detected_by="ph5_reconciliation",
            proposed_action=proposed_action.value,
            approval_required=True,
            status=RecoveryCaseStatus.WAITING_APPROVAL,
        )
        quarantine_id = None
        if quarantine_global and self.quarantine_service is not None:
            quarantine = self.quarantine_service.create_quarantine(
                QuarantineTargetType.GLOBAL_WRITE,
                f"ph5:{issue_type}",
                f"PH5 reconciliation detected {count} {issue_type} candidate(s)",
                "ph5_reconciliation",
                source_recovery_case_id=recovery_case.id,
            )
            quarantine_id = quarantine.quarantine_id
        return RecoveryCaseLink(
            issue_type=issue_type,
            case_type=case_type.value,
            source_key=recovery_case.source_key,
            case_id=recovery_case.case_id,
            quarantine_id=quarantine_id,
        )

    def _duplicate_ledger_count(self) -> int:
        return self._count_group_duplicates(LedgerEntry.transaction_event_id)

    def _duplicate_external_event_count(self) -> int:
        return self._count_group_duplicates(TransactionEvent.external_event_id)

    def _count_group_duplicates(self, column) -> int:
        return int(
            self.session.query(func.count())
            .select_from(
                self.session.query(column)
                .group_by(column)
                .having(func.count() > 1)
                .subquery()
            )
            .scalar()
            or 0
        )

    def _completed_idempotency_without_transaction_event_count(self) -> int:
        return int(
            self.session.query(func.count(IdempotencyRecord.id))
            .outerjoin(
                TransactionEvent,
                TransactionEvent.idempotency_key == IdempotencyRecord.idempotency_key,
            )
            .filter(IdempotencyRecord.status == IdempotencyStatus.COMPLETED.value)
            .filter(TransactionEvent.id.is_(None))
            .scalar()
            or 0
        )

    def _transaction_event_without_ledger_count(self) -> int:
        return int(
            self.session.query(func.count(TransactionEvent.id))
            .outerjoin(
                LedgerEntry, LedgerEntry.transaction_event_id == TransactionEvent.id
            )
            .filter(TransactionEvent.status != TransactionStatus.FAILED.value)
            .filter(LedgerEntry.id.is_(None))
            .scalar()
            or 0
        )

    def _ledger_without_transaction_event_count(self) -> int:
        return int(
            self.session.query(func.count(LedgerEntry.id))
            .outerjoin(
                TransactionEvent,
                TransactionEvent.id == LedgerEntry.transaction_event_id,
            )
            .filter(TransactionEvent.id.is_(None))
            .scalar()
            or 0
        )

    def _account_balance_mismatch_count(self) -> int:
        ledger_sum = (
            self.session.query(
                LedgerEntry.account_id.label("account_id"),
                func.coalesce(func.sum(LedgerEntry.amount), 0).label("ledger_sum"),
            )
            .group_by(LedgerEntry.account_id)
            .subquery()
        )
        return int(
            self.session.query(func.count(Account.id))
            .outerjoin(ledger_sum, ledger_sum.c.account_id == Account.id)
            .filter(Account.balance != func.coalesce(ledger_sum.c.ledger_sum, 0))
            .scalar()
            or 0
        )


def _safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _iso_required(value: datetime) -> str:
    return value.isoformat()
