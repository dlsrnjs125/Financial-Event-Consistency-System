"""Service for processing transaction events atomically."""

import logging
from datetime import datetime
from time import perf_counter
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache.redis_keys import idempotency_lock_key
from app.cache.redis_lock import RedisLock
from app.domain.event_type import EventType
from app.domain.exceptions import (
    AccountNotFound,
    IdempotencyConflict,
    InsufficientBalance,
    InvalidTransactionEvent,
    OriginalTransactionNotFound,
    TransactionAlreadyCancelled,
    TransactionAlreadySettled,
)
from app.domain.idempotency import IdempotencyDecision
from app.domain.transaction_result import TransactionProcessingResult
from app.domain.transaction_status import TransactionStatus
from app.models.ledger_entry import LedgerEntry
from app.models.transaction_event import TransactionEvent
from app.observability.logging import log_event
from app.observability.metrics import (
    observe_transaction_duration,
    record_db_transaction_retry,
    record_duplicate_external_event,
    record_transaction_processed,
)
from app.repositories.account_repository import AccountRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.transaction_event_repository import TransactionEventRepository
from app.schemas.transaction_event import TransactionEventCreateRequest
from app.security.masking import mask_idempotency_key
from app.services.idempotency_service import IdempotencyService
from app.services.ledger_service import LedgerService
from app.services.transaction_state_service import TransactionStateService

logger = logging.getLogger(__name__)


class TransactionEventService:
    def __init__(
        self,
        session: Session,
        idempotency_service: IdempotencyService,
        transaction_event_repository: TransactionEventRepository,
        account_repository: AccountRepository,
        ledger_service: LedgerService,
        transaction_state_service: TransactionStateService,
        redis_lock: RedisLock | None = None,
    ) -> None:
        self.session = session
        self.idempotency_service = idempotency_service
        self.transaction_event_repository = transaction_event_repository
        self.account_repository = account_repository
        self.ledger_service = ledger_service
        self.transaction_state_service = transaction_state_service
        self.redis_lock = redis_lock
        self._active_event: TransactionEvent | None = None

    def process(
        self,
        idempotency_key: str,
        request: TransactionEventCreateRequest,
    ) -> TransactionProcessingResult:
        started_at = perf_counter()
        lock_key = idempotency_lock_key(idempotency_key)
        lock_result = None
        if self.redis_lock is not None:
            lock_result = self.redis_lock.acquire(lock_key)
            if not lock_result.redis_available:
                log_event(
                    logger,
                    logging.WARNING,
                    "redis_lock_degraded_mode_enabled",
                    external_event_id=request.external_event_id,
                    event_type=request.event_type.value,
                    idempotency_key_masked=mask_idempotency_key(idempotency_key),
                    account_no=request.account_no,
                    operation="lock_acquire",
                    dependency="redis",
                    fallback_used=True,
                    error_type=lock_result.reason,
                )
            if lock_result.redis_available and not lock_result.acquired:
                result = self._already_processing_result()
                self._record_process_result(request, result, started_at)
                return result

        try:
            result = self._process_with_db_fallback(idempotency_key, request)
            self._record_process_result(request, result, started_at)
            return result
        finally:
            if (
                self.redis_lock is not None
                and lock_result is not None
                and lock_result.acquired
            ):
                self.redis_lock.release(lock_key, lock_result.token)

    def _process_with_db_fallback(
        self,
        idempotency_key: str,
        request: TransactionEventCreateRequest,
    ) -> TransactionProcessingResult:
        payload = request.model_dump(mode="json")

        for attempt in range(2):
            try:
                with self.session.begin():
                    idem = self.idempotency_service.check_or_start(
                        idempotency_key, payload
                    )
                    if idem.decision == IdempotencyDecision.ALREADY_PROCESSING:
                        return self._already_processing_result()
                    if idem.decision == IdempotencyDecision.REPLAY_COMPLETED:
                        return TransactionProcessingResult(
                            status_code=idem.response_code or 200,
                            body=dict(idem.response_body or {}),
                            processed=False,
                            duplicated=True,
                        )
                    if idem.decision == IdempotencyDecision.REPLAY_FAILED:
                        return TransactionProcessingResult(
                            status_code=idem.response_code or 422,
                            body=dict(idem.response_body or {}),
                            processed=False,
                            duplicated=True,
                        )

                    return self._process_started(idempotency_key, request, payload)
            except IntegrityError as exc:
                self.session.rollback()
                if attempt >= 1:
                    raise
                record_db_transaction_retry("integrity_conflict")
                log_event(
                    logger,
                    logging.WARNING,
                    "db_integrity_conflict_retry",
                    external_event_id=request.external_event_id,
                    event_type=request.event_type.value,
                    idempotency_key_masked=mask_idempotency_key(idempotency_key),
                    account_no=request.account_no,
                    operation="transaction_event_process",
                    dependency="postgres",
                    fallback_used=True,
                    error_type=type(exc).__name__,
                )
                continue
            except Exception:
                self.session.rollback()
                raise

        raise RuntimeError("unreachable transaction retry state")

    def _already_processing_result(self) -> TransactionProcessingResult:
        return TransactionProcessingResult(
            status_code=202,
            body={
                "status": "PROCESSING",
                "message": "The same request is already being processed.",
                "retry_after_seconds": 3,
                "idempotency_key_status": "processing",
            },
            processed=False,
            duplicated=True,
        )

    def _process_started(
        self,
        idempotency_key: str,
        request: TransactionEventCreateRequest,
        payload: dict[str, Any],
    ) -> TransactionProcessingResult:
        try:
            self._active_event = None
            log_event(
                logger,
                logging.INFO,
                "transaction_processing_started",
                external_event_id=request.external_event_id,
                event_type=request.event_type.value,
                idempotency_key=idempotency_key,
                account_no=request.account_no,
                operation="transaction_event_process",
                dependency="postgres",
                fallback_used=False,
            )
            result = self._apply_started_request(idempotency_key, request)
            self.idempotency_service.complete(
                idempotency_key,
                result.status_code,
                result.body,
                payload=payload,
            )
            return result
        except Exception as exc:
            if self._is_domain_failure(exc):
                self._mark_active_event_failed(exc)
            response_body = self._error_body(exc)
            status_code = self._status_code_for_exception(exc)
            self.idempotency_service.fail(
                idempotency_key,
                status_code,
                response_body,
                error_message=str(exc),
                payload=payload,
            )
            if self._is_domain_failure(exc):
                log_event(
                    logger,
                    logging.WARNING,
                    "transaction_processing_failed",
                    external_event_id=request.external_event_id,
                    event_type=request.event_type.value,
                    transaction_status=TransactionStatus.FAILED.value,
                    idempotency_key=idempotency_key,
                    account_no=request.account_no,
                    operation="transaction_event_process",
                    dependency="postgres",
                    fallback_used=False,
                    error_type=type(exc).__name__,
                )
                return TransactionProcessingResult(
                    status_code=status_code,
                    body=response_body,
                    processed=False,
                    duplicated=False,
                )
            raise
        finally:
            self._active_event = None

    def _apply_started_request(
        self,
        idempotency_key: str,
        request: TransactionEventCreateRequest,
    ) -> TransactionProcessingResult:
        account = self.account_repository.get_by_account_no_for_update(
            request.account_no
        )
        if account is None:
            raise AccountNotFound()

        existing_event = self.transaction_event_repository.get_by_external_event_id(
            request.external_event_id
        )
        if existing_event is not None:
            self._ensure_duplicate_matches_request(existing_event, request, account.id)
            log_event(
                logger,
                logging.INFO,
                "duplicate_external_event_detected",
                external_event_id=request.external_event_id,
                event_type=request.event_type.value,
                idempotency_key=idempotency_key,
                account_no=request.account_no,
                operation="duplicate_external_event_check",
                dependency="postgres",
                fallback_used=False,
            )
            record_duplicate_external_event(request.event_type.value)
            return self._duplicate_result(existing_event)

        original_event = self._get_original_event_for_cancel(request)
        event = self.transaction_event_repository.create_received(
            external_event_id=request.external_event_id,
            idempotency_key=idempotency_key,
            account_id=account.id,
            event_type=request.event_type.value,
            amount=request.amount,
            currency=request.currency,
            occurred_at=request.occurred_at,
        )
        self._active_event = event
        try:
            self.transaction_state_service.change_status(
                event, TransactionStatus.VALIDATED, "basic validation succeeded"
            )
            self.transaction_state_service.change_status(
                event, TransactionStatus.PROCESSING, "ledger processing started"
            )
            ledger = self.ledger_service.apply_event(account, event, original_event)
            if request.event_type == EventType.CANCEL and original_event is not None:
                self.transaction_state_service.change_status(
                    original_event,
                    TransactionStatus.CANCELLED,
                    "cancel event completed",
                )
            self.transaction_state_service.change_status(
                event, TransactionStatus.COMPLETED, "ledger processing completed"
            )
            log_event(
                logger,
                logging.INFO,
                "transaction_processing_completed",
                event_id=event.id,
                external_event_id=event.external_event_id,
                event_type=event.event_type,
                transaction_status=event.status,
                idempotency_key=idempotency_key,
                account_no=request.account_no,
                operation="transaction_event_process",
                dependency="postgres",
                fallback_used=False,
            )
            return self._success_result(event, ledger, processed=True, duplicated=False)
        except IntegrityError:
            # TODO(Phase 5/6): On concurrent unique conflict, rollback and re-read
            # existing TransactionEvent/LedgerEntry to return a duplicate response.
            raise

    def _get_original_event_for_cancel(
        self, request: TransactionEventCreateRequest
    ) -> TransactionEvent | None:
        if request.event_type != EventType.CANCEL:
            return None
        if request.original_external_event_id is None:
            raise InvalidTransactionEvent("CANCEL requires original_external_event_id")
        original_event = (
            self.transaction_event_repository.get_original_for_cancel_for_update(
                request.original_external_event_id
            )
        )
        if original_event is None:
            raise OriginalTransactionNotFound()
        return original_event

    def _ensure_duplicate_matches_request(
        self,
        existing_event: TransactionEvent,
        request: TransactionEventCreateRequest,
        account_id: int,
    ) -> None:
        if existing_event.account_id != account_id:
            raise InvalidTransactionEvent(
                "external_event_id already exists with different account"
            )
        if existing_event.event_type != request.event_type.value:
            raise InvalidTransactionEvent(
                "external_event_id already exists with different event_type"
            )
        if existing_event.amount != request.amount:
            raise InvalidTransactionEvent(
                "external_event_id already exists with different amount"
            )
        if existing_event.currency != request.currency:
            raise InvalidTransactionEvent(
                "external_event_id already exists with different currency"
            )
        if not self._datetimes_match(existing_event.occurred_at, request.occurred_at):
            raise InvalidTransactionEvent(
                "external_event_id already exists with different occurred_at"
            )

    def _datetimes_match(self, existing: datetime, incoming: datetime) -> bool:
        if existing.tzinfo is not None and incoming.tzinfo is not None:
            return existing.timestamp() == incoming.timestamp()
        return existing.replace(tzinfo=None) == incoming.replace(tzinfo=None)

    def _duplicate_result(self, event: TransactionEvent) -> TransactionProcessingResult:
        ledger = self.ledger_entry_repository.get_by_transaction_event_id(event.id)
        if ledger is None:
            raise InvalidTransactionEvent("Duplicate event has no ledger entry")
        return self._success_result(event, ledger, processed=False, duplicated=True)

    @property
    def ledger_entry_repository(self) -> LedgerEntryRepository:
        return self.ledger_service.ledger_entry_repository

    def _success_result(
        self,
        event: TransactionEvent,
        ledger: LedgerEntry,
        processed: bool,
        duplicated: bool,
    ) -> TransactionProcessingResult:
        body = {
            "event_id": str(event.id),
            "external_event_id": event.external_event_id,
            "status": event.status,
            "processed": processed,
            "duplicated": duplicated,
            "balance_after": ledger.balance_after,
        }
        return TransactionProcessingResult(
            status_code=200,
            body=body,
            processed=processed,
            duplicated=duplicated,
        )

    def _error_body(self, exc: Exception) -> dict[str, Any]:
        return {
            "status": "error",
            "code": type(exc).__name__,
            "message": str(exc),
        }

    def _status_code_for_exception(self, exc: Exception) -> int:
        if isinstance(exc, (AccountNotFound, OriginalTransactionNotFound)):
            return 404
        if isinstance(
            exc,
            (
                IdempotencyConflict,
                TransactionAlreadyCancelled,
                TransactionAlreadySettled,
            ),
        ):
            return 409
        if isinstance(exc, (InsufficientBalance, InvalidTransactionEvent)):
            return 422
        return 500

    def _mark_active_event_failed(self, exc: Exception) -> None:
        if self._active_event is None:
            return
        if self._active_event.status == TransactionStatus.FAILED.value:
            return
        try:
            self.transaction_state_service.change_status(
                self._active_event,
                TransactionStatus.FAILED,
                reason=str(exc),
            )
        except Exception:
            # If the state machine cannot move the active event to FAILED, keep the
            # original domain failure visible to the caller and idempotency record.
            return

    def _is_domain_failure(self, exc: Exception) -> bool:
        return isinstance(
            exc,
            (
                AccountNotFound,
                InsufficientBalance,
                InvalidTransactionEvent,
                OriginalTransactionNotFound,
                TransactionAlreadyCancelled,
                TransactionAlreadySettled,
            ),
        )

    def _record_process_result(
        self,
        request: TransactionEventCreateRequest,
        result: TransactionProcessingResult,
        started_at: float,
    ) -> None:
        duration = perf_counter() - started_at
        event_type = request.event_type.value
        status_value = str(result.body.get("status", "unknown"))
        if result.processed:
            outcome = "processed"
        elif result.duplicated:
            outcome = "duplicated"
        else:
            outcome = "failed"
        observe_transaction_duration(event_type, duration)
        record_transaction_processed(event_type, status_value, outcome)
