import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.domain.idempotency_status import IdempotencyStatus
from app.domain.recovery import RecoveryCaseType
from app.domain.transaction_status import TransactionStatus
from app.models import import_all_models
from app.models.account import Account
from app.models.idempotency_record import IdempotencyRecord
from app.models.ledger_entry import LedgerEntry
from app.models.transaction_event import TransactionEvent
from app.repositories.quarantine_repository import QuarantineRepository
from app.repositories.recovery_case_repository import RecoveryCaseRepository
from app.services.quarantine_service import QuarantineService
from app.services.reconciliation_service import (
    ReconciliationCounts,
    ReconciliationService,
)
from app.services.recovery_case_service import RecoveryCaseService

ROOT_DIR = Path(__file__).resolve().parents[3]
PH5_SPEC = importlib.util.spec_from_file_location(
    "ph5_reconciliation", ROOT_DIR / "scripts/ph5_reconciliation.py"
)
ph5_reconciliation = importlib.util.module_from_spec(PH5_SPEC)
assert PH5_SPEC and PH5_SPEC.loader
PH5_SPEC.loader.exec_module(ph5_reconciliation)


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
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def service(session: Session) -> ReconciliationService:
    quarantine_service = QuarantineService(QuarantineRepository(session))
    recovery_service = RecoveryCaseService(
        RecoveryCaseRepository(session),
        quarantine_service=quarantine_service,
    )
    return ReconciliationService(
        session,
        recovery_service,
        quarantine_service=quarantine_service,
    )


def _record(
    session: Session,
    key: str,
    status: IdempotencyStatus,
    locked_until: datetime | None,
    updated_at: datetime,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        idempotency_key=key,
        request_hash=f"hash-{key}",
        status=status.value,
        expires_at=updated_at + timedelta(days=1),
        locked_until=locked_until,
        created_at=updated_at,
        updated_at=updated_at,
    )
    session.add(record)
    session.flush()
    return record


def _account(session: Session, balance: int = 0) -> Account:
    account = Account(
        account_no=f"ACC-{balance}-{session.query(Account).count()}",
        balance=balance,
    )
    session.add(account)
    session.flush()
    return account


def _event(
    session: Session,
    account: Account,
    idempotency_key: str,
    status: str = TransactionStatus.COMPLETED.value,
    updated_at: datetime | None = None,
) -> TransactionEvent:
    timestamp = updated_at or datetime(2026, 7, 7, 1, 0, tzinfo=UTC)
    event = TransactionEvent(
        external_event_id=f"ext-{idempotency_key}",
        idempotency_key=idempotency_key,
        account_id=account.id,
        event_type="DEPOSIT",
        amount=1000,
        currency="KRW",
        status=status,
        occurred_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(event)
    session.flush()
    return event


def test_detect_stale_processing_filters_fresh_and_terminal_records(
    session: Session,
    service: ReconciliationService,
) -> None:
    now = datetime.now(UTC)
    stale = _record(
        session,
        "idem-stale",
        IdempotencyStatus.PROCESSING,
        now - timedelta(minutes=1),
        now,
    )
    _record(
        session,
        "idem-fresh",
        IdempotencyStatus.PROCESSING,
        now + timedelta(minutes=5),
        now,
    )
    _record(
        session,
        "idem-completed",
        IdempotencyStatus.COMPLETED,
        None,
        now - timedelta(minutes=30),
    )

    candidates = service.detect_stale_processing(threshold_minutes=5)

    assert [candidate.idempotency_record_id for candidate in candidates] == [stale.id]
    assert candidates[0].idempotency_key_hash != "idem-stale"
    assert candidates[0].recovery_case_id is not None


def test_stale_recovery_case_is_idempotent(
    session: Session,
    service: ReconciliationService,
) -> None:
    now = datetime.now(UTC)
    record = _record(
        session,
        "idem-stale",
        IdempotencyStatus.PROCESSING,
        now - timedelta(minutes=1),
        now,
    )

    first = service.detect_stale_processing(threshold_minutes=5)
    second = service.detect_stale_processing(threshold_minutes=5)

    assert first[0].recovery_case_id == second[0].recovery_case_id
    assert (
        session.query(IdempotencyRecord).filter(IdempotencyRecord.id == record.id).one()
        is not None
    )
    assert len(service.recovery_case_service.list_cases()) == 1


def test_stale_with_event_and_ledger_is_mark_completed_candidate(
    session: Session,
    service: ReconciliationService,
) -> None:
    now = datetime.now(UTC)
    _record(
        session,
        "idem-stale",
        IdempotencyStatus.PROCESSING,
        now - timedelta(minutes=1),
        now,
    )
    account = _account(session, balance=1000)
    event = _event(session, account, "idem-stale")
    session.add(
        LedgerEntry(
            transaction_event_id=event.id,
            account_id=account.id,
            entry_type="CREDIT",
            amount=1000,
            balance_after=1000,
        )
    )
    session.flush()

    candidate = service.detect_stale_processing(threshold_minutes=5)[0]

    assert candidate.matching_transaction_event_exists is True
    assert candidate.matching_ledger_entry_exists is True
    assert candidate.proposed_action == "MARK_COMPLETED"


def test_reconcile_creates_cases_for_count_only_issues(
    session: Session,
    service: ReconciliationService,
) -> None:
    now = datetime.now(UTC)
    _record(session, "idem-orphan", IdempotencyStatus.COMPLETED, None, now)
    mismatched_account = _account(session, balance=5000)
    _event(
        session,
        mismatched_account,
        "idem-event-without-ledger",
        updated_at=now,
    )

    counts, links = service.reconcile(threshold_minutes=5)

    assert counts.completed_idempotency_without_transaction_event_count == 1
    assert counts.transaction_event_without_ledger_count == 1
    assert counts.account_balance_mismatch_count == 1
    case_types = {link.case_type for link in links}
    assert RecoveryCaseType.ORPHAN_IDEMPOTENCY.value in case_types
    assert RecoveryCaseType.FAILOVER_IN_DOUBT.value in case_types
    assert RecoveryCaseType.BALANCE_MISMATCH.value in case_types


def test_reconcile_does_not_count_fresh_processing_event_without_ledger(
    session: Session,
    service: ReconciliationService,
) -> None:
    account = _account(session)
    _event(
        session,
        account,
        "idem-fresh-processing-event",
        status=TransactionStatus.PROCESSING.value,
        updated_at=datetime.now(UTC),
    )

    counts, links = service.reconcile(threshold_minutes=5)

    assert counts.transaction_event_without_ledger_count == 0
    assert all(
        link.case_type != RecoveryCaseType.FAILOVER_IN_DOUBT.value for link in links
    )


def test_reconcile_counts_stale_processing_event_without_ledger(
    session: Session,
    service: ReconciliationService,
) -> None:
    account = _account(session)
    _event(
        session,
        account,
        "idem-stale-processing-event",
        status=TransactionStatus.PROCESSING.value,
        updated_at=datetime.now(UTC) - timedelta(minutes=10),
    )

    counts, links = service.reconcile(threshold_minutes=5)

    assert counts.transaction_event_without_ledger_count == 1
    assert RecoveryCaseType.FAILOVER_IN_DOUBT.value in {
        link.case_type for link in links
    }


def test_ph5_report_artifact_validates_without_sensitive_values(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-20260707-010000"
    run_dir.mkdir()
    summary = ph5_reconciliation._write_artifact(
        run_dir,
        5,
        [],
        ReconciliationCounts(
            duplicate_ledger_count=0,
            duplicate_external_event_count=0,
            completed_idempotency_without_transaction_event_count=0,
            transaction_event_without_ledger_count=0,
            ledger_without_transaction_event_count=0,
            account_balance_mismatch_count=0,
            stale_processing_count=0,
        ),
        [],
    )

    assert summary["sensitive_data_included"] is False
    assert ph5_reconciliation.validate_artifact(run_dir) == []


def test_ph5_report_artifact_with_stale_candidate_validates(
    tmp_path: Path,
    session: Session,
    service: ReconciliationService,
) -> None:
    now = datetime.now(UTC)
    _record(
        session,
        "idem-stale",
        IdempotencyStatus.PROCESSING,
        now - timedelta(minutes=1),
        now,
    )
    candidates = service.detect_stale_processing(threshold_minutes=5)
    run_dir = tmp_path / "run-20260707-020000"
    run_dir.mkdir()

    ph5_reconciliation._write_artifact(
        run_dir,
        5,
        candidates,
        ReconciliationCounts(
            duplicate_ledger_count=0,
            duplicate_external_event_count=0,
            completed_idempotency_without_transaction_event_count=0,
            transaction_event_without_ledger_count=0,
            ledger_without_transaction_event_count=0,
            account_balance_mismatch_count=0,
            stale_processing_count=len(candidates),
        ),
        [],
    )

    assert ph5_reconciliation.validate_artifact(run_dir) == []
    assert "idem-stale" not in (run_dir / "stale-processing-summary.json").read_text(
        encoding="utf-8"
    )


def test_ph5_report_rejects_raw_idempotency_key(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-20260707-030000"
    run_dir.mkdir()
    ph5_reconciliation._write_artifact(
        run_dir,
        5,
        [],
        ReconciliationCounts(
            duplicate_ledger_count=0,
            duplicate_external_event_count=0,
            completed_idempotency_without_transaction_event_count=0,
            transaction_event_without_ledger_count=0,
            ledger_without_transaction_event_count=0,
            account_balance_mismatch_count=0,
            stale_processing_count=0,
        ),
        [],
    )
    (run_dir / "stale-processing-summary.json").write_text(
        '{"idempotency_key": "raw-key", "sensitive_data_included": false}',
        encoding="utf-8",
    )

    errors = ph5_reconciliation.validate_artifact(run_dir)

    assert errors
    assert any("idempotency_key" in error for error in errors)
