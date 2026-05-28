"""Unit tests for security timestamp validation."""

from datetime import UTC, datetime, timedelta

import pytest

from app.security.exceptions import ExpiredTimestamp, InvalidTimestamp
from app.security.timestamp import parse_timestamp, validate_timestamp_window


def test_parse_timezone_aware_iso_timestamp():
    parsed = parse_timestamp("2026-05-28T10:00:00+09:00")

    assert parsed.tzinfo is not None


def test_parse_rejects_timezone_naive_timestamp():
    with pytest.raises(InvalidTimestamp):
        parse_timestamp("2026-05-28T10:00:00")


def test_parse_rejects_invalid_string():
    with pytest.raises(InvalidTimestamp):
        parse_timestamp("not-a-timestamp")


def test_allowed_skew_window_accepts_current_past_and_future():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)

    validate_timestamp_window(now, now=now, allowed_skew_seconds=300)
    validate_timestamp_window(now - timedelta(seconds=299), now=now)
    validate_timestamp_window(now + timedelta(seconds=299), now=now)


def test_allowed_skew_window_rejects_too_old_timestamp():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)

    with pytest.raises(ExpiredTimestamp):
        validate_timestamp_window(now - timedelta(seconds=301), now=now)


def test_allowed_skew_window_rejects_too_far_future_timestamp():
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)

    with pytest.raises(ExpiredTimestamp):
        validate_timestamp_window(now + timedelta(seconds=301), now=now)


def test_window_rejects_timezone_naive_datetime():
    with pytest.raises(InvalidTimestamp):
        validate_timestamp_window(datetime(2026, 5, 28, 10, 0))
