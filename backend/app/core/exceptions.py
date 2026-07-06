"""Common exception handlers."""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.domain.exceptions import (
    AccountNotFound,
    IdempotencyConflict,
    InsufficientBalance,
    InvalidIdempotencyKey,
    InvalidIdempotencyState,
    InvalidRecoveryCaseTransition,
    InvalidStateTransition,
    InvalidTransactionEvent,
    MissingIdempotencyKey,
    OriginalTransactionNotFound,
    QuarantineRecordNotFound,
    RecoveryApprovalMissingActor,
    RecoveryApprovalRequired,
    RecoveryCaseNotFound,
    TargetQuarantined,
    TransactionAlreadyCancelled,
    TransactionAlreadySettled,
    UnsafeAnalyzerResult,
)
from app.observability.metrics import record_write_suspended
from app.schemas.common import ErrorDetail, ErrorResponse
from app.security.exceptions import (
    DisabledClient,
    ExpiredTimestamp,
    InvalidSignature,
    InvalidTimestamp,
    MissingSecurityHeader,
    UnknownClient,
)
from app.services.write_suspension_service import (
    WriteSuspended,
    get_write_suspension_service,
)

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _trace_id(request: Request) -> str | None:
    return getattr(request.state, "trace_id", None)


def _observability_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    request_id = _request_id(request)
    trace_id = _trace_id(request)
    if request_id:
        headers["X-Request-ID"] = request_id
    if trace_id:
        headers["X-Trace-ID"] = trace_id
    return headers


def error_response(
    code: str, message: str, request_id: str | None
) -> dict[str, dict[str, str | None]]:
    return ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    ).model_dump()


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    code = "HTTP_ERROR"
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"
    elif exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        code = "SERVICE_UNAVAILABLE"

    headers = dict(getattr(exc, "headers", None) or {})
    headers.update(_observability_headers(request))
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code, message, _request_id(request)),
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception",
        extra={"request_id": _request_id(request)},
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            "INTERNAL_SERVER_ERROR",
            "Unexpected server error",
            _request_id(request),
        ),
        headers=_observability_headers(request),
    )


async def domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = type(exc).__name__

    if isinstance(exc, MissingIdempotencyKey):
        status_code = status.HTTP_400_BAD_REQUEST
        code = "MISSING_IDEMPOTENCY_KEY"
    elif isinstance(exc, InvalidIdempotencyKey):
        status_code = status.HTTP_400_BAD_REQUEST
        code = "INVALID_IDEMPOTENCY_KEY"
    elif isinstance(exc, (AccountNotFound, OriginalTransactionNotFound)):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, (RecoveryCaseNotFound, QuarantineRecordNotFound)):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(
        exc,
        (
            IdempotencyConflict,
            TargetQuarantined,
            TransactionAlreadyCancelled,
            TransactionAlreadySettled,
        ),
    ):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(
        exc,
        (
            InsufficientBalance,
            InvalidIdempotencyState,
            InvalidRecoveryCaseTransition,
            InvalidStateTransition,
            InvalidTransactionEvent,
            RecoveryApprovalMissingActor,
            RecoveryApprovalRequired,
            UnsafeAnalyzerResult,
        ),
    ):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    return JSONResponse(
        status_code=status_code,
        content=error_response(code, str(exc), _request_id(request)),
        headers=_observability_headers(request),
    )


async def security_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = status.HTTP_401_UNAUTHORIZED
    code = type(exc).__name__
    message = str(exc)

    if isinstance(exc, MissingSecurityHeader):
        status_code = status.HTTP_400_BAD_REQUEST
        code = "MISSING_SECURITY_HEADER"
    elif isinstance(exc, (UnknownClient, DisabledClient)):
        status_code = status.HTTP_403_FORBIDDEN
        code = "UNKNOWN_CLIENT" if isinstance(exc, UnknownClient) else "DISABLED_CLIENT"
    elif isinstance(exc, InvalidTimestamp):
        code = "INVALID_TIMESTAMP"
        message = "The request timestamp is invalid or expired."
    elif isinstance(exc, ExpiredTimestamp):
        code = "EXPIRED_TIMESTAMP"
        message = "The request timestamp is invalid or expired."
    elif isinstance(exc, InvalidSignature):
        code = "INVALID_SIGNATURE"

    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message, _request_id(request)),
        headers=_observability_headers(request),
    )


async def write_suspended_exception_handler(
    request: Request, exc: WriteSuspended
) -> JSONResponse:
    headers = {
        "Retry-After": str(exc.state.retry_after_seconds),
        **_observability_headers(request),
    }
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error_code": "WRITE_SUSPENDED",
            "message": "Financial write traffic is temporarily suspended.",
            "retryable": True,
            "request_id": _request_id(request),
            "trace_id": _trace_id(request),
        },
        headers=headers,
    )


async def database_exception_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    state = get_write_suspension_service().enable(
        reason="postgres_unavailable",
        activated_by="api",
        source="sqlalchemy_exception",
    )
    record_write_suspended("postgres_unavailable", "unknown")
    return await write_suspended_exception_handler(request, WriteSuspended(state))


def register_exception_handlers(app: FastAPI) -> None:
    for exception_type in (
        AccountNotFound,
        IdempotencyConflict,
        InvalidRecoveryCaseTransition,
        InsufficientBalance,
        InvalidIdempotencyKey,
        InvalidIdempotencyState,
        InvalidStateTransition,
        InvalidTransactionEvent,
        MissingIdempotencyKey,
        OriginalTransactionNotFound,
        QuarantineRecordNotFound,
        RecoveryApprovalMissingActor,
        RecoveryApprovalRequired,
        RecoveryCaseNotFound,
        TargetQuarantined,
        TransactionAlreadyCancelled,
        TransactionAlreadySettled,
        UnsafeAnalyzerResult,
    ):
        app.add_exception_handler(exception_type, domain_exception_handler)
    for exception_type in (
        DisabledClient,
        ExpiredTimestamp,
        InvalidSignature,
        InvalidTimestamp,
        MissingSecurityHeader,
        UnknownClient,
    ):
        app.add_exception_handler(exception_type, security_exception_handler)
    app.add_exception_handler(WriteSuspended, write_suspended_exception_handler)
    app.add_exception_handler(OperationalError, database_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
