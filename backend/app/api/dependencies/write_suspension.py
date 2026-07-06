"""Guards for runtime write suspension."""

import logging

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.observability.logging import log_event
from app.observability.metrics import record_write_suspended
from app.services.write_suspension_service import (
    WriteSuspendState,
    WriteSuspended,
    get_write_suspension_service,
)

logger = logging.getLogger(__name__)
ROUTE_GROUP = "transaction_events"


def guard_financial_write(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    service = get_write_suspension_service()
    state = service.status()
    if state.active:
        _record_suspended_write(request, state)
        raise WriteSuspended(state)

    try:
        db.execute(text("SELECT 1"))
        _rollback_probe_transaction(db)
    except SQLAlchemyError:
        _rollback_probe_transaction(db)
        state = service.enable(
            reason="postgres_unavailable",
            activated_by="api",
            source="postgres_probe",
        )
        _record_suspended_write(request, state)
        raise WriteSuspended(state)


def _rollback_probe_transaction(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        return


def _record_suspended_write(request: Request, state: WriteSuspendState) -> None:
    record_write_suspended(state.reason, ROUTE_GROUP)
    log_event(
        logger,
        logging.WARNING,
        "write_suspended",
        reason=state.reason,
        route_group=ROUTE_GROUP,
        retry_after_seconds=state.retry_after_seconds,
        trace_id=getattr(request.state, "trace_id", None),
        request_id=getattr(request.state, "request_id", None),
        sensitive_data_included=False,
    )
