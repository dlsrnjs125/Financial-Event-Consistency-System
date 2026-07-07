"""Repository for recovery case persistence operations."""

from sqlalchemy.orm import Session

from app.models.recovery_case import RecoveryCase


class RecoveryCaseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, recovery_case: RecoveryCase) -> RecoveryCase:
        self.session.add(recovery_case)
        self.session.flush()
        return recovery_case

    def get_by_case_id(self, case_id: str) -> RecoveryCase | None:
        return (
            self.session.query(RecoveryCase)
            .filter(RecoveryCase.case_id == case_id)
            .one_or_none()
        )

    def get_by_source_key(self, source_key: str) -> RecoveryCase | None:
        return (
            self.session.query(RecoveryCase)
            .filter(RecoveryCase.source_key == source_key)
            .one_or_none()
        )

    def list(self, limit: int = 100) -> list[RecoveryCase]:
        return (
            self.session.query(RecoveryCase)
            .order_by(RecoveryCase.created_at.desc(), RecoveryCase.id.desc())
            .limit(limit)
            .all()
        )

    def save(self, recovery_case: RecoveryCase) -> RecoveryCase:
        self.session.flush()
        return recovery_case
