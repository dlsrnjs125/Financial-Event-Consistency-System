"""Request-scoped observability context."""

from contextvars import ContextVar

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_context(trace_id: str, request_id: str) -> None:
    trace_id_var.set(trace_id)
    request_id_var.set(request_id)


def clear_request_context() -> None:
    trace_id_var.set(None)
    request_id_var.set(None)


def get_trace_id() -> str | None:
    return trace_id_var.get()


def get_request_id() -> str | None:
    return request_id_var.get()
