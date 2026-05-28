"""Timestamp parsing and replay-window validation."""

from datetime import UTC, datetime

from app.security.exceptions import ExpiredTimestamp, InvalidTimestamp


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidTimestamp() from exc

    if parsed.tzinfo is None:
        raise InvalidTimestamp()
    return parsed


def validate_timestamp_window(
    timestamp: datetime,
    now: datetime | None = None,
    allowed_skew_seconds: int = 300,
) -> None:
    if timestamp.tzinfo is None:
        raise InvalidTimestamp()

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    delta_seconds = abs((timestamp - current).total_seconds())
    if delta_seconds > allowed_skew_seconds:
        raise ExpiredTimestamp()
