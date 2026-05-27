"""Transaction event API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.idempotency import get_idempotency_key
from app.db.session import get_db
from app.domain.exceptions import AccountNotFound
from app.repositories.account_repository import AccountRepository
from app.repositories.idempotency_record_repository import IdempotencyRecordRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.transaction_event_repository import TransactionEventRepository
from app.schemas.transaction_event import (
    AccountBalanceResponse,
    TransactionEventCreateRequest,
    TransactionEventStatusResponse,
    mask_account_no,
)
from app.services.idempotency_service import IdempotencyService
from app.services.ledger_service import LedgerService
from app.services.transaction_event_service import TransactionEventService
from app.services.transaction_state_service import TransactionStateService

router = APIRouter(tags=["Transaction Events"])


def build_transaction_event_service(session: Session) -> TransactionEventService:
    account_repository = AccountRepository(session)
    ledger_entry_repository = LedgerEntryRepository(session)
    transaction_event_repository = TransactionEventRepository(session)
    ledger_service = LedgerService(account_repository, ledger_entry_repository)
    idempotency_service = IdempotencyService(
        IdempotencyRecordRepository(session),
    )
    return TransactionEventService(
        session=session,
        idempotency_service=idempotency_service,
        transaction_event_repository=transaction_event_repository,
        account_repository=account_repository,
        ledger_service=ledger_service,
        transaction_state_service=TransactionStateService(session),
    )


@router.post("/transaction-events")
def create_transaction_event(
    request: TransactionEventCreateRequest,
    response: Response,
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
