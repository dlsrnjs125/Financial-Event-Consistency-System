"""Repository for quarantine record persistence operations."""

from sqlalchemy.orm import Session

from app.models.quarantine_record import QuarantineRecord


class QuarantineRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, quarantine: QuarantineRecord) -> QuarantineRecord:
        self.session.add(quarantine)
        self.session.flush()
        return quarantine

    def get_by_quarantine_id(self, quarantine_id: str) -> QuarantineRecord | None:
        return (
            self.session.query(QuarantineRecord)
            .filter(QuarantineRecord.quarantine_id == quarantine_id)
            .one_or_none()
        )

    def get_active(self, target_type: str, target_id: str) -> QuarantineRecord | None:
        return (
            self.session.query(QuarantineRecord)
            .filter(
                QuarantineRecord.active.is_(True),
                QuarantineRecord.target_type == target_type,
                QuarantineRecord.target_id == target_id,
            )
            .order_by(QuarantineRecord.activated_at.desc(), QuarantineRecord.id.desc())
            .first()
        )

    def list(
        self, active: bool | None = None, limit: int = 100
    ) -> list[QuarantineRecord]:
        query = self.session.query(QuarantineRecord)
        if active is not None:
            query = query.filter(QuarantineRecord.active.is_(active))
        return (
            query.order_by(
                QuarantineRecord.created_at.desc(), QuarantineRecord.id.desc()
            )
            .limit(limit)
            .all()
        )

    def save(self, quarantine: QuarantineRecord) -> QuarantineRecord:
        self.session.flush()
        return quarantine
