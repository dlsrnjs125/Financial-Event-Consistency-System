from __future__ import annotations

from importlib import util
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts/ph2_incident_artifact.py"
SPEC = util.spec_from_file_location("ph2_incident_artifact", SCRIPT_PATH)
ph2_incident_artifact = util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(ph2_incident_artifact)


def sanitize_payload(payload: Any) -> Any:
    return ph2_incident_artifact.sanitize_payload(payload)


def test_sanitizer_keeps_allowlisted_fields() -> None:
    payload = {
        "incident_id": "inc-20260706-153000-postgres-down",
        "scenario": "POSTGRES_DOWN",
        "http_status": 503,
        "retryable": True,
        "unknown_debug_field": "drop-me",
    }

    assert sanitize_payload(payload) == {
        "incident_id": "inc-20260706-153000-postgres-down",
        "scenario": "POSTGRES_DOWN",
        "http_status": 503,
        "retryable": True,
    }


def test_sanitizer_removes_sensitive_keys() -> None:
    payload = {
        "Authorization": "synthetic-authorization-token",
        "X-Signature": "synthetic-signature-value",
        "Idempotency-Key": "synthetic-idempotency-key",
        "account_no": "synthetic-account-number-1234",
        "account_number": "synthetic-account-number-1234",
        "DATABASE_URL": "postgresql://user:pass@example/db",
        "scenario": "POSTGRES_DOWN",
    }

    sanitized = sanitize_payload(payload)

    assert sanitized == {"scenario": "POSTGRES_DOWN"}


def test_sanitizer_redacts_sensitive_values_in_allowed_fields() -> None:
    payload = {
        "result": "Authorization: synthetic-authorization-token",
        "command_name": "check",
    }

    assert sanitize_payload(payload) == {
        "result": "[REDACTED]",
        "command_name": "check",
    }
