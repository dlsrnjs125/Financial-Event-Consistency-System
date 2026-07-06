import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.domain.exceptions import (
    InvalidRecoveryCaseTransition,
    RecoveryApprovalMissingActor,
    RecoveryApprovalRequired,
    UnsafeAnalyzerResult,
)
from app.domain.recovery import (
    QuarantineTargetType,
    RecoveryCaseStatus,
    RecoveryCaseType,
    RecoveryProposedAction,
)
from app.models import import_all_models
from app.repositories.quarantine_repository import QuarantineRepository
from app.repositories.recovery_case_repository import RecoveryCaseRepository
from app.services.quarantine_service import QuarantineService
from app.services.recovery_case_service import RecoveryCaseService


@pytest.fixture()
def session() -> Session:
    import_all_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def service(session: Session) -> RecoveryCaseService:
    quarantine_service = QuarantineService(QuarantineRepository(session))
    return RecoveryCaseService(
        RecoveryCaseRepository(session),
        quarantine_service=quarantine_service,
    )


def _create_case(
    service: RecoveryCaseService, source_key: str = "incident:case"
) -> str:
    recovery_case = service.create_case(
        source_key=source_key,
        case_type=RecoveryCaseType.WRITE_SUSPENDED_UNKNOWN_DEPENDENCY.value,
        severity="SEV2",
        classification=RecoveryCaseType.WRITE_SUSPENDED_UNKNOWN_DEPENDENCY.value,
        confidence_candidate=0.7,
        detected_by="unit-test",
        proposed_action=RecoveryProposedAction.NOOP_REVIEW_ONLY.value,
    )
    return recovery_case.case_id


def test_create_case_is_idempotent_by_source_key(
    service: RecoveryCaseService,
) -> None:
    first = service.create_case(
        source_key="incident:type:target:id:unknown",
        case_type=RecoveryCaseType.POSTGRES_DOWN_WRITE_SUSPENDED.value,
        severity="SEV1",
        classification=RecoveryCaseType.POSTGRES_DOWN_WRITE_SUSPENDED.value,
        confidence_candidate=0.9,
        detected_by="unit-test",
        proposed_action=RecoveryProposedAction.NOOP_REVIEW_ONLY.value,
    )
    second = service.create_case(
        source_key="incident:type:target:id:unknown",
        case_type=RecoveryCaseType.POSTGRES_DOWN_WRITE_SUSPENDED.value,
        severity="SEV1",
        classification=RecoveryCaseType.POSTGRES_DOWN_WRITE_SUSPENDED.value,
        confidence_candidate=0.9,
        detected_by="unit-test",
        proposed_action=RecoveryProposedAction.NOOP_REVIEW_ONLY.value,
    )

    assert second.id == first.id
    assert second.case_id == first.case_id


def test_approval_and_execution_guard(service: RecoveryCaseService) -> None:
    case_id = _create_case(service)

    with pytest.raises(RecoveryApprovalRequired):
        service.start_execution(case_id)

    approved = service.approve(case_id, approved_by="operator-a", approval_reason="ok")
    assert approved.current_status == RecoveryCaseStatus.APPROVED.value
    executing = service.start_execution(case_id)
    assert executing.current_status == RecoveryCaseStatus.EXECUTING.value
    assert executing.action_attempt_id is not None

    with pytest.raises(InvalidRecoveryCaseTransition):
        service.start_execution(case_id)


def test_approval_requires_actor(service: RecoveryCaseService) -> None:
    case_id = _create_case(service)

    with pytest.raises(RecoveryApprovalMissingActor):
        service.approve(case_id, approved_by="")


def test_reject_blocks_execution(service: RecoveryCaseService) -> None:
    case_id = _create_case(service)
    rejected = service.reject(case_id, reason="not needed")

    assert rejected.current_status == RecoveryCaseStatus.REJECTED.value
    with pytest.raises(InvalidRecoveryCaseTransition):
        service.start_execution(case_id)


def test_create_from_analyzer_result_creates_case_and_quarantine(
    tmp_path: Path,
    service: RecoveryCaseService,
) -> None:
    incident_dir = tmp_path / "inc-20260706-180000-postgres-down"
    incident_dir.mkdir()
    (incident_dir / "analyzer-result.json").write_text(
        json.dumps(
            {
                "incident_id": incident_dir.name,
                "analyzer_version": "ph3-mvp-v1",
                "classification": "CONSISTENCY_ISSUE_CANDIDATE",
                "severity_candidate": "SEV2",
                "confidence_candidate": 0.8,
                "sensitive_data_included": False,
            }
        ),
        encoding="utf-8",
    )

    recovery_case = service.create_from_analyzer_result(incident_dir)

    assert recovery_case.case_type == "CONSISTENCY_ISSUE_CANDIDATE"
    assert recovery_case.proposed_action == "KEEP_QUARANTINED"
    assert recovery_case.approval_required is True
    quarantine_service = service.quarantine_service
    assert quarantine_service is not None
    quarantine = quarantine_service.repository.get_active(
        QuarantineTargetType.GLOBAL_WRITE.value,
        incident_dir.name,
    )
    assert quarantine is not None


def test_sensitive_analyzer_result_is_refused(
    tmp_path: Path,
    service: RecoveryCaseService,
) -> None:
    incident_dir = tmp_path / "inc-sensitive"
    incident_dir.mkdir()
    (incident_dir / "analyzer-result.json").write_text(
        json.dumps({"sensitive_data_included": True}),
        encoding="utf-8",
    )

    with pytest.raises(UnsafeAnalyzerResult):
        service.create_from_analyzer_result(incident_dir)
