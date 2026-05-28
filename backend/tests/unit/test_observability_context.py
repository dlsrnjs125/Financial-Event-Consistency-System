"""Unit tests for observability request context."""

from app.observability.context import (
    clear_request_context,
    get_request_id,
    get_trace_id,
    set_request_context,
)


def test_context_returns_none_when_not_set():
    clear_request_context()

    assert get_trace_id() is None
    assert get_request_id() is None


def test_set_get_and_clear_request_context():
    set_request_context(trace_id="trace-001", request_id="req-001")

    assert get_trace_id() == "trace-001"
    assert get_request_id() == "req-001"

    clear_request_context()
    assert get_trace_id() is None
    assert get_request_id() is None


def test_context_values_can_be_replaced():
    set_request_context(trace_id="trace-001", request_id="req-001")
    set_request_context(trace_id="trace-002", request_id="req-002")

    assert get_trace_id() == "trace-002"
    assert get_request_id() == "req-002"

    clear_request_context()
