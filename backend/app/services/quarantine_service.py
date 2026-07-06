"""Service for quarantine record lifecycle and write guards."""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.exceptions import QuarantineRecordNotFound, TargetQuarantined
from app.domain.recovery import QuarantineTargetType
from app.models.quarantine_record import QuarantineRecord
from app.repositories.quarantine_repository import QuarantineRepository


class QuarantineService:
    def __init__(self, repository: QuarantineRepository) -> None:
        self.repository = repository

    def create_quarantine(
        self,
        target_type: QuarantineTargetType,
        target_id: str,
        reason: str,
        activated_by: str,
        source_recovery_case_id: int | None = None,
        source_incident_id: str | None = None,
    ) -> QuarantineRecord:
        active = self.repository.get_active(target_type.value, target_id)
        if active is not None:
            return active
        quarantine = QuarantineRecord(
            quarantine_id=f"qr-{uuid4().hex[:16]}",
            target_type=target_type.value,
            target_id=target_id,
            reason=reason,
            source_recovery_case_id=source_recovery_case_id,
            source_incident_id=source_incident_id,
            active=True,
            activated_at=datetime.now(UTC),
            activated_by=activated_by,
        )
        return self.repository.create(quarantine)

    def release_quarantine(
        self,
        quarantine_id: str,
        released_by: str,
        release_reason: str,
    ) -> QuarantineRecord:
        quarantine = self.repository.get_by_quarantine_id(quarantine_id)
        if quarantine is None:
            raise QuarantineRecordNotFound()
        if quarantine.active:
            quarantine.active = False
            quarantine.released_at = datetime.now(UTC)
            quarantine.released_by = released_by
            quarantine.release_reason = release_reason
            self.repository.save(quarantine)
        return quarantine

    def assert_not_quarantined(
        self,
        target_type: QuarantineTargetType,
        target_id: str,
    ) -> None:
        quarantine = self.repository.get_active(target_type.value, target_id)
        if quarantine is not None:
            raise TargetQuarantined(target_type.value, quarantine.quarantine_id)

    def list_quarantines(
        self,
        active: bool | None = None,
        limit: int = 100,
    ) -> list[QuarantineRecord]:
        return self.repository.list(active=active, limit=limit)
