"""Common exception handlers."""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AccountNotFound,
    IdempotencyConflict,
    InsufficientBalance,
    InvalidIdempotencyKey,
    InvalidIdempotencyState,
    InvalidStateTransition,
    InvalidTransactionEvent,
    MissingIdempotencyKey,
    OriginalTransactionNotFound,
    TransactionAlreadyCancelled,
    TransactionAlreadySettled,
)
from app.schemas.common import ErrorDetail, ErrorResponse
from app.security.exceptions import (
    DisabledClient,
    ExpiredTimestamp,
    InvalidSignature,
    InvalidTimestamp,
    MissingSecurityHeader,
    UnknownClient,
)

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


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

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code, message, _request_id(request)),
        headers=getattr(exc, "headers", None),
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
    elif isinstance(
        exc,
        (
            IdempotencyConflict,
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
            InvalidStateTransition,
            InvalidTransactionEvent,
        ),
    ):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    return JSONResponse(
        status_code=status_code,
        content=error_response(code, str(exc), _request_id(request)),
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
    )


def register_exception_handlers(app: FastAPI) -> None:
    for exception_type in (
        AccountNotFound,
        IdempotencyConflict,
        InsufficientBalance,
        InvalidIdempotencyKey,
        InvalidIdempotencyState,
        InvalidStateTransition,
        InvalidTransactionEvent,
        MissingIdempotencyKey,
        OriginalTransactionNotFound,
        TransactionAlreadyCancelled,
        TransactionAlreadySettled,
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
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
