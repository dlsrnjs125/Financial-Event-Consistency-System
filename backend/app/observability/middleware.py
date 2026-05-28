"""Request context and HTTP observability middleware."""

from time import perf_counter
from uuid import uuid4

from fastapi import Request

from app.metrics.prometheus import metrics_middleware
from app.observability.context import clear_request_context, set_request_context


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or request.headers.get(
        "X-Request-Id"
    )
    if not request_id:
        request_id = f"req-{uuid4().hex}"
    trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Trace-Id")
    if not trace_id:
        trace_id = f"trace-{uuid4().hex}"

    set_request_context(trace_id=trace_id, request_id=request_id)
    request.state.request_id = request_id
    request.state.trace_id = trace_id
    start = perf_counter()
    try:
        response = await metrics_middleware(request, call_next, start=start)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        return response
    finally:
        clear_request_context()
