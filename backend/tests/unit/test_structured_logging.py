"""Unit tests for structured logging helpers."""

import json
import logging

from app.core.logging import JsonFormatter
from app.observability.context import clear_request_context, set_request_context
from app.observability.logging import RequestContextFilter, sanitize_log_extra


def test_request_context_filter_adds_trace_and_request_id():
    clear_request_context()
    set_request_context("trace-001", "req-001")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    RequestContextFilter().filter(record)

    assert record.trace_id == "trace-001"
    assert record.request_id == "req-001"
    clear_request_context()


def test_json_formatter_includes_trace_and_request_id():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.trace_id = "trace-001"
    record.request_id = "req-001"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["trace_id"] == "trace-001"
    assert payload["request_id"] == "req-001"


def test_sanitize_log_extra_masks_sensitive_values():
    sanitized = sanitize_log_extra(
        {
            "account_no": "1234567890",
            "idempotency_key": "idem-20260528-001",
            "signature": "a" * 64,
            "secret": "super-secret",
            "expected_signature": "b" * 64,
            "raw_body": '{"account_no":"1234567890"}',
        }
    )

    rendered = json.dumps(sanitized)
    assert "1234567890" not in rendered
    assert "idem-20260528-001" not in rendered
    assert "super-secret" not in rendered
    assert "raw_body" not in sanitized
    assert sanitized["account_no_masked"] == "******7890"
    assert sanitized["secret"] == "<redacted>"
