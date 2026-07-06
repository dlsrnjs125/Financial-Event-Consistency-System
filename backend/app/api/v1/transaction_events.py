"""Transaction event API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.idempotency import get_idempotency_key
from app.api.dependencies.security import verify_external_request_signature
from app.api.dependencies.write_suspension import guard_financial_write
from app.cache.idempotency_cache import IdempotencyResponseCache
from app.cache.redis_errors import REDIS_FALLBACK_EXCEPTIONS, redis_failure_reason
from app.cache.redis_lock import RedisLock
from app.core.config import settings
from app.db.session import get_db
from app.domain.exceptions import AccountNotFound
from app.observability.logging import log_event
from app.observability.metrics import record_redis_fallback, record_redis_operation_v2
from app.redis.client import get_redis_client
from app.repositories.account_repository import AccountRepository
from app.repositories.idempotency_record_repository import IdempotencyRecordRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.quarantine_repository import QuarantineRepository
from app.repositories.transaction_event_repository import TransactionEventRepository
from app.schemas.transaction_event import (
    AccountBalanceResponse,
    TransactionEventCreateRequest,
    TransactionEventStatusResponse,
    mask_account_no,
)
from app.services.cached_idempotency_service import CachedIdempotencyService
from app.services.idempotency_service import IdempotencyService
from app.services.ledger_service import LedgerService
from app.services.quarantine_service import QuarantineService
from app.services.transaction_event_service import TransactionEventService
from app.services.transaction_state_service import TransactionStateService

router = APIRouter(tags=["Transaction Events"])
logger = logging.getLogger(__name__)


def build_idempotency_service(session: Session):
    idempotency_service = IdempotencyService(IdempotencyRecordRepository(session))
    if not settings.redis_enabled or not settings.idempotency_cache_enabled:
        return idempotency_service
    try:
        redis_client = get_redis_client()
    except REDIS_FALLBACK_EXCEPTIONS as exc:
        reason = redis_failure_reason(exc)
        record_redis_operation_v2("cache_get", "failure", reason)
        record_redis_fallback("cache_get", reason)
        log_event(
            logger,
            logging.WARNING,
            "redis_cache_client_fallback",
            operation="cache_get",
            dependency="redis",
            fallback_used=True,
            error_type=type(exc).__name__,
        )
        return idempotency_service
    return CachedIdempotencyService(
        idempotency_service=idempotency_service,
        response_cache=IdempotencyResponseCache(
            redis_client,
            ttl_seconds=settings.redis_idempotency_cache_ttl_seconds,
        ),
    )


def build_redis_lock() -> RedisLock | None:
    if not settings.redis_enabled or not settings.redis_lock_enabled:
        return None
    try:
        return RedisLock(get_redis_client(), ttl_ms=settings.redis_lock_ttl_ms)
    except REDIS_FALLBACK_EXCEPTIONS as exc:
        reason = redis_failure_reason(exc)
        record_redis_operation_v2("lock_acquire", "failure", reason)
        record_redis_fallback("lock_acquire", reason)
        log_event(
            logger,
            logging.WARNING,
            "redis_lock_client_fallback",
            operation="lock_acquire",
            dependency="redis",
            fallback_used=True,
            error_type=type(exc).__name__,
        )
        return None


def build_transaction_event_service(session: Session) -> TransactionEventService:
    account_repository = AccountRepository(session)
    ledger_entry_repository = LedgerEntryRepository(session)
    transaction_event_repository = TransactionEventRepository(session)
    ledger_service = LedgerService(account_repository, ledger_entry_repository)
    return TransactionEventService(
        session=session,
        idempotency_service=build_idempotency_service(session),
        transaction_event_repository=transaction_event_repository,
        account_repository=account_repository,
        ledger_service=ledger_service,
        transaction_state_service=TransactionStateService(session),
        redis_lock=build_redis_lock(),
        quarantine_service=QuarantineService(QuarantineRepository(session)),
    )


@router.post("/transaction-events")
def create_transaction_event(
    request: TransactionEventCreateRequest,
    response: Response,
    _: None = Depends(verify_external_request_signature),
    __: None = Depends(guard_financial_write),
    idempotency_key: str = Depends(get_idempotency_key),
    db: Session = Depends(get_db),
):
    service = build_transaction_event_service(db)
    result = service.process(idempotency_key, request)
    response.status_code = result.status_code
    return result.body


@router.get(
    "/transaction-events/{event_id}",
    response_model=TransactionEventStatusResponse,
)
def get_transaction_event(event_id: int, db: Session = Depends(get_db)):
    event = TransactionEventRepository(db).get_by_id(event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction event not found",
        )
    return TransactionEventStatusResponse(
        event_id=str(event.id),
        external_event_id=event.external_event_id,
        event_type=event.event_type,
        status=event.status,
        amount=event.amount,
        currency=event.currency,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
    )


@router.get(
    "/accounts/{account_no}/balance",
    response_model=AccountBalanceResponse,
)
def get_account_balance(account_no: str, db: Session = Depends(get_db)):
    account = AccountRepository(db).get_by_account_no(account_no)
    if account is None:
        raise AccountNotFound()
    return AccountBalanceResponse(
        account_no=mask_account_no(account.account_no),
        balance=account.balance,
        as_of=account.updated_at,
    )
