"""Service for idempotency decisions and result persistence."""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.exceptions import IdempotencyConflict
from app.domain.idempotency import (
    IdempotencyCheckResult,
    IdempotencyDecision,
    generate_request_hash,
)
from app.domain.idempotency_status import IdempotencyStatus
from app.models.idempotency_record import IdempotencyRecord
from app.repositories.idempotency_record_repository import IdempotencyRecordRepository


class IdempotencyService:
    def __init__(
        self,
        repository: IdempotencyRecordRepository,
        ttl_seconds: int = 86400,
        processing_lock_seconds: int = 30,
    ) -> None:
        self.repository = repository
        self.ttl_seconds = ttl_seconds
        self.processing_lock_seconds = processing_lock_seconds

    def check_or_start(
        self,
        idempotency_key: str,
        payload: Any,
        now: datetime | None = None,
    ) -> IdempotencyCheckResult:
        checked_at = now or datetime.now(UTC)
        request_hash = generate_request_hash(payload)
        record = self.repository.get_by_key(idempotency_key)

        if record is None:
            new_record = self.repository.create_processing(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                expires_at=checked_at + timedelta(seconds=self.ttl_seconds),
                locked_until=checked_at
                + timedelta(seconds=self.processing_lock_seconds),
            )
            return IdempotencyCheckResult(
                decision=IdempotencyDecision.STARTED,
                record_id=new_record.id,
            )

        self._ensure_same_request_hash(record, request_hash)
        status = IdempotencyStatus(record.status)

        if status == IdempotencyStatus.PROCESSING:
            return IdempotencyCheckResult(
                decision=IdempotencyDecision.ALREADY_PROCESSING,
                record_id=record.id,
            )
        if status == IdempotencyStatus.COMPLETED:
            return IdempotencyCheckResult(
                decision=IdempotencyDecision.REPLAY_COMPLETED,
                record_id=record.id,
                response_code=record.response_code,
                response_body=record.response_body,
            )

        return IdempotencyCheckResult(
            decision=IdempotencyDecision.REPLAY_FAILED,
            record_id=record.id,
            response_code=record.response_code,
            response_body=record.response_body,
        )

    def complete(
        self,
        idempotency_key: str,
        response_code: int,
        response_body: Any | None,
        now: datetime | None = None,
    ) -> IdempotencyRecord:
        record = self._get_existing_record(idempotency_key)
        completed_at = now or datetime.now(UTC)
        return self.repository.mark_completed(
            record=record,
            response_code=response_code,
            response_body=response_body,
            completed_at=completed_at,
        )

    def fail(
        self,
        idempotency_key: str,
        response_code: int | None = None,
        response_body: Any | None = None,
        now: datetime | None = None,
    ) -> IdempotencyRecord:
        record = self._get_existing_record(idempotency_key)
        failed_at = now or datetime.now(UTC)
        return self.repository.mark_failed(
            record=record,
            response_code=response_code,
            response_body=response_body,
            failed_at=failed_at,
        )

    def _ensure_same_request_hash(
        self, record: IdempotencyRecord, request_hash: str
    ) -> None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict(record.idempotency_key)

    def _get_existing_record(self, idempotency_key: str) -> IdempotencyRecord:
        record = self.repository.get_by_key(idempotency_key)
        if record is None:
            raise KeyError(f"IdempotencyRecord not found for key: {idempotency_key}")
        return record
