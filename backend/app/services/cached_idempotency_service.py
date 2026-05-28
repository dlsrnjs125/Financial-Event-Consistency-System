"""Redis cache wrapper for IdempotencyService."""

from datetime import datetime
from typing import Any

from app.cache.idempotency_cache import IdempotencyResponseCache
from app.domain.idempotency import (
    IdempotencyCheckResult,
    IdempotencyDecision,
    generate_request_hash,
)
from app.models.idempotency_record import IdempotencyRecord
from app.services.idempotency_service import IdempotencyService


class CachedIdempotencyService:
    def __init__(
        self,
        idempotency_service: IdempotencyService,
        response_cache: IdempotencyResponseCache,
    ) -> None:
        self.idempotency_service = idempotency_service
        self.response_cache = response_cache

    def check_or_start(
        self,
        idempotency_key: str,
        payload: Any,
        now: datetime | None = None,
    ) -> IdempotencyCheckResult:
        request_hash = generate_request_hash(payload)
        cached = self.response_cache.get(idempotency_key)
        if cached is not None and cached.request_hash == request_hash:
            return IdempotencyCheckResult(
                decision=IdempotencyDecision.REPLAY_COMPLETED,
                record_id=None,
                response_code=cached.response_code,
                response_body=cached.response_body,
            )

        result = self.idempotency_service.check_or_start(idempotency_key, payload, now)
        if result.decision == IdempotencyDecision.REPLAY_COMPLETED:
            self.response_cache.set_completed(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_code=result.response_code or 200,
                response_body=result.response_body,
            )
        return result

    def complete(
        self,
        idempotency_key: str,
        response_code: int,
        response_body: Any | None,
        payload: Any | None = None,
        request_hash: str | None = None,
        now: datetime | None = None,
    ) -> IdempotencyRecord:
        record = self.idempotency_service.complete(
            idempotency_key=idempotency_key,
            response_code=response_code,
            response_body=response_body,
            payload=payload,
            request_hash=request_hash,
            now=now,
        )
        resolved_hash = request_hash
        if resolved_hash is None and payload is not None:
            resolved_hash = generate_request_hash(payload)
        if resolved_hash is not None:
            self.response_cache.set_completed(
                idempotency_key=idempotency_key,
                request_hash=resolved_hash,
                response_code=response_code,
                response_body=response_body,
            )
        return record

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
        return self.idempotency_service.fail(
            idempotency_key=idempotency_key,
            response_code=response_code,
            response_body=response_body,
            error_message=error_message,
            payload=payload,
            request_hash=request_hash,
            now=now,
        )
