"""Service for idempotency decisions and result persistence."""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.exceptions import IdempotencyConflict, InvalidIdempotencyState
from app.domain.idempotency import (
    IdempotencyCheckResult,
    IdempotencyDecision,
    generate_request_hash,
)
from app.domain.idempotency_status import IdempotencyStatus
from app.models.idempotency_record import IdempotencyRecord
from app.observability.metrics import (
    record_idempotency_conflict,
    record_idempotency_decision,
)
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
            record_idempotency_decision(IdempotencyDecision.STARTED, "db")
            return IdempotencyCheckResult(
                decision=IdempotencyDecision.STARTED,
                record_id=new_record.id,
            )

        # expires_at is a retention hint, not a request-time invalidation rule
        # in Phase 4. Expired key deletion is handled by a separate operation.
        try:
            self._ensure_same_request_hash(record, request_hash)
        except IdempotencyConflict:
            record_idempotency_conflict("db")
            raise
        status = IdempotencyStatus(record.status)

        if status == IdempotencyStatus.PROCESSING:
            record_idempotency_decision(IdempotencyDecision.ALREADY_PROCESSING, "db")
            return IdempotencyCheckResult(
                decision=IdempotencyDecision.ALREADY_PROCESSING,
                record_id=record.id,
            )
        if status == IdempotencyStatus.COMPLETED:
            record_idempotency_decision(IdempotencyDecision.REPLAY_COMPLETED, "db")
            return IdempotencyCheckResult(
                decision=IdempotencyDecision.REPLAY_COMPLETED,
                record_id=record.id,
                response_code=record.response_code,
                response_body=record.response_body,
            )

        record_idempotency_decision(IdempotencyDecision.REPLAY_FAILED, "db")
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
        payload: Any | None = None,
        request_hash: str | None = None,
        now: datetime | None = None,
    ) -> IdempotencyRecord:
        record = self._get_existing_record(idempotency_key)
        self._ensure_completion_matches_request(record, payload, request_hash)
        if self._is_terminal_noop(record, IdempotencyStatus.COMPLETED):
            return record
        self._ensure_can_close_processing(record, IdempotencyStatus.COMPLETED)
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
        error_message: str | None = None,
        payload: Any | None = None,
        request_hash: str | None = None,
        now: datetime | None = None,
    ) -> IdempotencyRecord:
        record = self._get_existing_record(idempotency_key)
        self._ensure_completion_matches_request(record, payload, request_hash)
        if self._is_terminal_noop(record, IdempotencyStatus.FAILED):
            return record
        self._ensure_can_close_processing(record, IdempotencyStatus.FAILED)
        failed_at = now or datetime.now(UTC)
        return self.repository.mark_failed(
            record=record,
            response_code=response_code,
            response_body=response_body,
            error_message=error_message,
            failed_at=failed_at,
        )

    def _ensure_same_request_hash(
        self, record: IdempotencyRecord, request_hash: str
    ) -> None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict(record.idempotency_key)

    def _ensure_completion_matches_request(
        self,
        record: IdempotencyRecord,
        payload: Any | None,
        request_hash: str | None,
    ) -> None:
        if payload is not None and request_hash is not None:
            raise ValueError("Provide either payload or request_hash, not both.")

        if payload is not None:
            self._ensure_same_request_hash(record, generate_request_hash(payload))
        elif request_hash is not None:
            self._ensure_same_request_hash(record, request_hash)

    def _is_terminal_noop(
        self, record: IdempotencyRecord, attempted_status: IdempotencyStatus
    ) -> bool:
        return IdempotencyStatus(record.status) == attempted_status

    def _ensure_can_close_processing(
        self, record: IdempotencyRecord, attempted_status: IdempotencyStatus
    ) -> None:
        current_status = IdempotencyStatus(record.status)
        if current_status == IdempotencyStatus.PROCESSING:
            return

        raise InvalidIdempotencyState(
            current_status=current_status.value,
            attempted_status=attempted_status.value,
        )

    def _get_existing_record(self, idempotency_key: str) -> IdempotencyRecord:
        record = self.repository.get_by_key(idempotency_key)
        if record is None:
            raise KeyError("IdempotencyRecord not found")
        return record
