"""Idempotency domain helpers."""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class IdempotencyDecision(StrEnum):
    STARTED = "STARTED"
    REPLAY_COMPLETED = "REPLAY_COMPLETED"
    ALREADY_PROCESSING = "ALREADY_PROCESSING"
    REPLAY_FAILED = "REPLAY_FAILED"


@dataclass(frozen=True)
class IdempotencyCheckResult:
    decision: IdempotencyDecision
    record_id: int | None
    response_code: int | None = None
    response_body: Any | None = None


def canonicalize_payload(payload: Any) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def generate_request_hash(payload: Any) -> str:
    return hashlib.sha256(canonicalize_payload(payload)).hexdigest()
