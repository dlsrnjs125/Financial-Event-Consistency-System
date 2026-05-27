"""Service for processing transaction events atomically."""

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
from app.repositories.account_repository import AccountRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.transaction_event_repository import TransactionEventRepository
from app.schemas.transaction_event import TransactionEventCreateRequest
from app.services.idempotency_service import IdempotencyService
from app.services.ledger_service import LedgerService
from app.services.transaction_state_service import TransactionStateService


class TransactionEventService:
    def __init__(
        self,
        session: Session,
        idempotency_service: IdempotencyService,
        transaction_event_repository: TransactionEventRepository,
        account_repository: AccountRepository,
        ledger_service: LedgerService,
        transaction_state_service: TransactionStateService,
    ) -> None:
        self.session = session
        self.idempotency_service = idempotency_service
        self.transaction_event_repository = transaction_event_repository
        self.account_repository = account_repository
        self.ledger_service = ledger_service
        self.transaction_state_service = transaction_state_service

    def process(
        self,
        idempotency_key: str,
        request: TransactionEventCreateRequest,
    ) -> TransactionProcessingResult:
        payload = request.model_dump(mode="json")

        try:
            with self.session.begin():
                idem = self.idempotency_service.check_or_start(idempotency_key, payload)
                if idem.decision == IdempotencyDecision.ALREADY_PROCESSING:
                    return TransactionProcessingResult(
                        status_code=202,
                        body={
                            "status": "PROCESSING",
                            "message": "The same request is already being processed.",
                            "retry_after_seconds": 3,
                        },
                        processed=False,
                        duplicated=True,
                    )
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
        except Exception:
            self.session.rollback()
            raise

    def _process_started(
        self,
        idempotency_key: str,
        request: TransactionEventCreateRequest,
        payload: dict[str, Any],
    ) -> TransactionProcessingResult:
        try:
            result = self._apply_started_request(idempotency_key, request)
            self.idempotency_service.complete(
                idempotency_key,
                result.status_code,
                result.body,
                payload=payload,
            )
            return result
        except Exception as exc:
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
                return TransactionProcessingResult(
                    status_code=status_code,
                    body=response_body,
                    processed=False,
                    duplicated=False,
                )
            raise

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
        original_event = self.transaction_event_repository.get_original_for_cancel(
            request.original_external_event_id
        )
        if original_event is None:
            raise OriginalTransactionNotFound()
        return original_event

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
