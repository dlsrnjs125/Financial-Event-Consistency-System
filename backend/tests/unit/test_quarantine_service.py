import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.domain.exceptions import TargetQuarantined
from app.domain.recovery import QuarantineTargetType
from app.models import import_all_models
from app.repositories.quarantine_repository import QuarantineRepository
from app.services.quarantine_service import QuarantineService


@pytest.fixture()
def service() -> QuarantineService:
    import_all_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()
    return QuarantineService(QuarantineRepository(session))


def test_quarantine_create_is_idempotent_for_active_target(
    service: QuarantineService,
) -> None:
    first = service.create_quarantine(
        QuarantineTargetType.ACCOUNT,
        "100",
        "manual review",
        "operator-a",
    )
    second = service.create_quarantine(
        QuarantineTargetType.ACCOUNT,
        "100",
        "manual review",
        "operator-a",
    )

    assert second.quarantine_id == first.quarantine_id


def test_active_quarantine_blocks_target(service: QuarantineService) -> None:
    quarantine = service.create_quarantine(
        QuarantineTargetType.ACCOUNT,
        "100",
        "manual review",
        "operator-a",
    )

    with pytest.raises(TargetQuarantined) as exc_info:
        service.assert_not_quarantined(QuarantineTargetType.ACCOUNT, "100")

    assert exc_info.value.quarantine_id == quarantine.quarantine_id


def test_released_quarantine_allows_target(service: QuarantineService) -> None:
    quarantine = service.create_quarantine(
        QuarantineTargetType.ACCOUNT,
        "100",
        "manual review",
        "operator-a",
    )
    service.release_quarantine(
        quarantine.quarantine_id,
        released_by="operator-b",
        release_reason="review complete",
    )

    service.assert_not_quarantined(QuarantineTargetType.ACCOUNT, "100")
