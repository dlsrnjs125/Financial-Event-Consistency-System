"""Repository for idempotency records."""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.idempotency_status import IdempotencyStatus
from app.models.idempotency_record import IdempotencyRecord


class IdempotencyRecordRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_key(self, idempotency_key: str) -> IdempotencyRecord | None:
        return (
            self.session.query(IdempotencyRecord)
            .filter(IdempotencyRecord.idempotency_key == idempotency_key)
            .one_or_none()
        )

    def create_processing(
        self,
        idempotency_key: str,
        request_hash: str,
        expires_at: datetime,
        locked_until: datetime | None = None,
    ) -> IdempotencyRecord:
        # TODO(Phase 5/6): On concurrent insert IntegrityError, rollback and re-read
        # the existing IdempotencyRecord to return ALREADY_PROCESSING or
        # REPLAY_COMPLETED.
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status=IdempotencyStatus.PROCESSING.value,
            expires_at=expires_at,
            locked_until=locked_until,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def mark_completed(
        self,
        record: IdempotencyRecord,
        response_code: int,
        response_body: Any | None,
        completed_at: datetime,
    ) -> IdempotencyRecord:
        record.status = IdempotencyStatus.COMPLETED.value
        record.response_code = response_code
        record.response_body = response_body
        record.completed_at = completed_at
        record.updated_at = completed_at
        record.locked_until = None
        self.session.flush()
        return record

    def mark_failed(
        self,
        record: IdempotencyRecord,
        failed_at: datetime,
        response_code: int | None = None,
        response_body: Any | None = None,
        error_message: str | None = None,
    ) -> IdempotencyRecord:
        record.status = IdempotencyStatus.FAILED.value
        record.response_code = response_code
        record.response_body = response_body
        record.error_message = error_message
        record.updated_at = failed_at
        record.locked_until = None
        self.session.flush()
        return record

    def list_expired(self, now: datetime) -> list[IdempotencyRecord]:
        return (
            self.session.query(IdempotencyRecord)
            .filter(IdempotencyRecord.expires_at.is_not(None))
            .filter(IdempotencyRecord.expires_at <= now)
            .filter(
                IdempotencyRecord.status.in_(
                    [
                        IdempotencyStatus.COMPLETED.value,
                        IdempotencyStatus.FAILED.value,
                    ]
                )
            )
            .order_by(IdempotencyRecord.expires_at.asc(), IdempotencyRecord.id.asc())
            .all()
        )

    def delete_expired(self, now: datetime) -> int:
        expired_records = self.list_expired(now)
        for record in expired_records:
            self.session.delete(record)
        self.session.flush()
        return len(expired_records)
