"""Service for recovery case lifecycle and PH3 analyzer ingestion."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.exceptions import (
    InvalidRecoveryCaseTransition,
    RecoveryApprovalMissingActor,
    RecoveryApprovalRequired,
    RecoveryCaseNotFound,
    UnsafeAnalyzerResult,
)
from app.domain.recovery import (
    ALLOWED_RECOVERY_TRANSITIONS,
    QuarantineTargetType,
    RecoveryCaseStatus,
    case_type_from_classification,
    proposed_action_for_case_type,
)
from app.models.recovery_case import RecoveryCase
from app.repositories.recovery_case_repository import RecoveryCaseRepository
from app.services.quarantine_service import QuarantineService


class RecoveryCaseService:
    def __init__(
        self,
        repository: RecoveryCaseRepository,
        quarantine_service: QuarantineService | None = None,
    ) -> None:
        self.repository = repository
        self.quarantine_service = quarantine_service

    def create_case(
        self,
        *,
        source_key: str,
        case_type: str,
        severity: str,
        classification: str,
        confidence_candidate: float | None,
        detected_by: str,
        proposed_action: str,
        approval_required: bool = True,
        status: RecoveryCaseStatus = RecoveryCaseStatus.WAITING_APPROVAL,
        source_incident_id: str | None = None,
        source_artifact_path: str | None = None,
        source_analyzer_result_path: str | None = None,
        external_event_id: str | None = None,
        idempotency_key_hash: str | None = None,
        client_id: str | None = None,
        account_id: int | None = None,
        transaction_event_id: int | None = None,
        evidence_path: str | None = None,
    ) -> RecoveryCase:
        existing = self.repository.get_by_source_key(source_key)
        if existing is not None:
            return existing

        recovery_case = RecoveryCase(
            case_id=f"rc-{uuid4().hex[:16]}",
            source_key=source_key,
            case_type=case_type,
            severity=severity,
            current_status=status.value,
            classification=classification,
            confidence_candidate=confidence_candidate,
            account_id=account_id,
            transaction_event_id=transaction_event_id,
            external_event_id=external_event_id,
            idempotency_key_hash=idempotency_key_hash,
            client_id=client_id,
            detected_by=detected_by,
            detected_at=datetime.now(UTC),
            source_incident_id=source_incident_id,
            source_artifact_path=source_artifact_path,
            source_analyzer_result_path=source_analyzer_result_path,
            proposed_action=proposed_action,
            approval_required=approval_required,
            evidence_path=evidence_path,
        )
        return self.repository.create(recovery_case)

    def create_from_analyzer_result(self, incident_dir: Path) -> RecoveryCase:
        result_path = incident_dir / "analyzer-result.json"
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if payload.get("sensitive_data_included") is not False:
            raise UnsafeAnalyzerResult()

        classification = str(payload.get("classification") or "")
        case_type = case_type_from_classification(classification)
        proposed_action = proposed_action_for_case_type(case_type)
        incident_id = str(payload.get("incident_id") or incident_dir.name)
        target_type = QuarantineTargetType.GLOBAL_WRITE.value
        target_id = incident_id
        source_key = (
            f"{incident_id}:{case_type.value}:{target_type}:{target_id}:unknown"
        )
        recovery_case = self.create_case(
            source_key=source_key,
            case_type=case_type.value,
            severity=str(payload.get("severity_candidate") or "SEV3"),
            classification=classification or case_type.value,
            confidence_candidate=_as_float(payload.get("confidence_candidate")),
            detected_by=str(payload.get("analyzer_version") or "ph3-analyzer"),
            proposed_action=proposed_action.value,
            approval_required=True,
            status=RecoveryCaseStatus.WAITING_APPROVAL,
            source_incident_id=incident_id,
            source_artifact_path=str(incident_dir),
            source_analyzer_result_path=str(result_path),
            evidence_path=str(incident_dir / "incident-analysis.md"),
        )

        if (
            self.quarantine_service is not None
            and case_type.value == "CONSISTENCY_ISSUE_CANDIDATE"
        ):
            self.quarantine_service.create_quarantine(
                target_type=QuarantineTargetType.GLOBAL_WRITE,
                target_id=incident_id,
                reason="PH3 analyzer detected consistency issue candidate",
                activated_by="ph4_recovery_case",
                source_recovery_case_id=recovery_case.id,
                source_incident_id=incident_id,
            )
        return recovery_case

    def approve(
        self,
        case_id: str,
        approved_by: str,
        approval_reason: str | None = None,
    ) -> RecoveryCase:
        if not approved_by:
            raise RecoveryApprovalMissingActor()
        recovery_case = self._get(case_id)
        self._transition(recovery_case, RecoveryCaseStatus.APPROVED)
        recovery_case.approved_by = approved_by
        recovery_case.approved_at = datetime.now(UTC)
        recovery_case.approval_reason = approval_reason
        return self.repository.save(recovery_case)

    def reject(self, case_id: str, reason: str | None = None) -> RecoveryCase:
        recovery_case = self._get(case_id)
        self._transition(recovery_case, RecoveryCaseStatus.REJECTED)
        recovery_case.approval_reason = reason
        return self.repository.save(recovery_case)

    def start_execution(self, case_id: str) -> RecoveryCase:
        recovery_case = self._get(case_id)
        if recovery_case.current_status != RecoveryCaseStatus.APPROVED.value:
            if recovery_case.approval_required and not recovery_case.approved_by:
                current_status = RecoveryCaseStatus(recovery_case.current_status)
                if current_status in {
                    RecoveryCaseStatus.AUTO_ANALYZED,
                    RecoveryCaseStatus.WAITING_APPROVAL,
                }:
                    raise RecoveryApprovalRequired()
            raise InvalidRecoveryCaseTransition(
                recovery_case.current_status,
                RecoveryCaseStatus.EXECUTING.value,
            )
        if recovery_case.approval_required and not recovery_case.approved_by:
            raise RecoveryApprovalRequired()
        recovery_case.current_status = RecoveryCaseStatus.EXECUTING.value
        recovery_case.executing_at = datetime.now(UTC)
        if not recovery_case.action_attempt_id:
            recovery_case.action_attempt_id = f"attempt-{uuid4().hex[:16]}"
        return self.repository.save(recovery_case)

    def mark_executed(
        self,
        case_id: str,
        after_snapshot_hash: str | None = None,
    ) -> RecoveryCase:
        recovery_case = self._get(case_id)
        self._transition(recovery_case, RecoveryCaseStatus.EXECUTED)
        recovery_case.executed_at = datetime.now(UTC)
        recovery_case.after_snapshot_hash = after_snapshot_hash
        return self.repository.save(recovery_case)

    def mark_execution_failed(
        self,
        case_id: str,
        failure_type: str,
    ) -> RecoveryCase:
        recovery_case = self._get(case_id)
        self._transition(recovery_case, RecoveryCaseStatus.EXECUTION_FAILED)
        recovery_case.execution_failed_at = datetime.now(UTC)
        recovery_case.execution_failure_type = failure_type
        return self.repository.save(recovery_case)

    def close(self, case_id: str) -> RecoveryCase:
        recovery_case = self._get(case_id)
        self._transition(recovery_case, RecoveryCaseStatus.CLOSED)
        return self.repository.save(recovery_case)

    def list_cases(self, limit: int = 100) -> list[RecoveryCase]:
        return self.repository.list(limit=limit)

    def _get(self, case_id: str) -> RecoveryCase:
        recovery_case = self.repository.get_by_case_id(case_id)
        if recovery_case is None:
            raise RecoveryCaseNotFound()
        return recovery_case

    def _transition(
        self,
        recovery_case: RecoveryCase,
        next_status: RecoveryCaseStatus,
    ) -> None:
        current = RecoveryCaseStatus(recovery_case.current_status)
        allowed = ALLOWED_RECOVERY_TRANSITIONS[current]
        if next_status not in allowed:
            raise InvalidRecoveryCaseTransition(current.value, next_status.value)
        recovery_case.current_status = next_status.value


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
