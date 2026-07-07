"""Allowlist-based sanitizer for AI-safe operational context."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

ALLOWED_KEYS = {
    "account_balance_mismatch_count",
    "account_token",
    "approval_required",
    "case_id",
    "case_type",
    "classification",
    "confidence",
    "confidence_candidate",
    "consistency_counts",
    "created_at",
    "duplicate_external_event_count",
    "duplicate_ledger_count",
    "event_token",
    "evidence_paths",
    "generated_at",
    "idempotency_key_hash",
    "incident_id",
    "ledger_without_transaction_event_count",
    "manual_action_candidates",
    "manual_actions_required",
    "manual_review_required",
    "masked_account_no",
    "masked_client_id",
    "masked_idempotency_key",
    "masked_target_id",
    "metric_summary",
    "primary_signals",
    "proposed_action",
    "recovery_case_link_count",
    "request_hash",
    "run_id",
    "runbook_reference",
    "severity",
    "severity_candidate",
    "source",
    "stale_processing_count",
    "status",
    "target_type",
    "transaction_event_without_ledger_count",
}

FORBIDDEN_KEYS = {
    "account_no",
    "api_key",
    "authorization",
    "client_secret",
    "connection_string",
    "cookie",
    "database_url",
    "db_url",
    "hmac_signature",
    "idempotency_key",
    "password",
    "raw_account_no",
    "raw_idempotency_key",
    "raw_request_body",
    "refresh_token",
    "request_body",
    "response_body",
    "secret",
    "set_cookie",
    "signature",
    "token",
    "access_token",
}

SENSITIVE_KEY_RE = re.compile(
    r"(authorization|cookie|database[-_]?url|db[-_]?url|password|secret|"
    r"signature|idempotency[-_]?key|account[-_]?no|account[-_]?number|"
    r"access[-_]?token|refresh[-_]?token|api[-_]?key|connection[-_]?string|"
    r"raw[-_]?body|request[-_]?body|response[-_]?body)",
    re.IGNORECASE,
)

SENSITIVE_VALUE_RE = re.compile(
    r"(Authorization\s*[:=]\s*\S+|Bearer\s+\S+|Basic\s+\S+|HMAC\s+\S+|"
    r"X-Signature\s*[:=]\s*\S+|idempotency_key\s*[:=]\s*\S+|"
    r"Idempotency-Key\s*[:=]\s*\S+|account_no\s*[:=]\s*\S+|"
    r"account_number\s*[:=]\s*\S+|client_secret\s*[:=]\s*\S+|"
    r"DATABASE_URL\s*=|postgresql://[^\s)]+|\bACC-\d{3,}\b|"
    r"synthetic-authorization-token|synthetic-signature-value|"
    r"synthetic-account-number|synthetic-idempotency-key)",
    re.IGNORECASE,
)

HASH_OR_TOKEN_KEYS = {
    "account_token",
    "event_token",
    "idempotency_key_hash",
    "request_hash",
}

LONG_SECRET_RE = re.compile(r"^[A-Za-z0-9+/=_-]{40,}$")


@dataclass(frozen=True)
class RemovedField:
    path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "reason": self.reason}


@dataclass(frozen=True)
class SanitizedContextResult:
    sanitized_context: Any
    removed_fields: tuple[RemovedField, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sanitized_context": self.sanitized_context,
            "redaction_summary": {
                "removed_field_count": len(self.removed_fields),
                "removed_fields": [field.to_dict() for field in self.removed_fields],
            },
            "sensitive_data_included": False,
        }


def sanitize_context(payload: Any) -> SanitizedContextResult:
    removed: list[RemovedField] = []
    sanitized = _sanitize_value(payload, "$", removed, parent_key=None)
    return SanitizedContextResult(
        sanitized_context=sanitized,
        removed_fields=tuple(removed),
    )


def validate_sanitized_context(payload: Any) -> list[str]:
    errors: list[str] = []
    _validate_payload(payload, "$", errors)
    return errors


def render_markdown_report(result: SanitizedContextResult) -> str:
    data = result.to_dict()
    context = data["sanitized_context"]
    summary = data["redaction_summary"]
    if isinstance(context, dict):
        incident_id = context.get("incident_id", "not_collected")
        run_id = context.get("run_id", "not_collected")
        classification = context.get("classification", "not_collected")
        severity = context.get(
            "severity", context.get("severity_candidate", "not_collected")
        )
    else:
        incident_id = "not_collected"
        run_id = "not_collected"
        classification = "not_collected"
        severity = "not_collected"

    return f"""# PH6 AI-safe Context Report

## Summary

- Incident ID: {incident_id}
- Run ID: {run_id}
- Classification: {classification}
- Severity: {severity}
- Removed Field Count: {summary["removed_field_count"]}
- Sensitive Data Included: false

## Boundaries

- AI context is generated from allowlisted fields only.
- Raw account numbers, raw idempotency keys, request bodies, signatures,
  authorization headers, and secrets are excluded.
- PH6 does not call external AI APIs or execute recovery actions.
"""


def _sanitize_value(
    value: Any,
    path: str,
    removed: list[RemovedField],
    parent_key: str | None,
) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path != "$" else f"$.{key_text}"
            reason = _removal_reason_for_key(key_text)
            if reason:
                removed.append(RemovedField(child_path, reason))
                continue
            if key_text not in ALLOWED_KEYS:
                removed.append(RemovedField(child_path, "not_in_allowlist"))
                continue
            if not isinstance(item, (dict, list)) and _contains_sensitive_value(
                item, key_text
            ):
                removed.append(RemovedField(child_path, "sensitive_value_pattern"))
                continue
            sanitized[key_text] = _sanitize_value(
                item,
                child_path,
                removed,
                parent_key=key_text,
            )
        return sanitized

    if isinstance(value, list):
        return [
            _sanitize_value(item, f"{path}[{index}]", removed, parent_key=parent_key)
            for index, item in enumerate(value)
        ]

    if _contains_sensitive_value(value, parent_key):
        removed.append(RemovedField(path, "sensitive_value_pattern"))
        return None
    return value


def _removal_reason_for_key(key: str) -> str | None:
    normalized = key.lower().replace("-", "_")
    if key in ALLOWED_KEYS:
        return None
    if normalized in FORBIDDEN_KEYS or SENSITIVE_KEY_RE.search(key):
        return "sensitive_field_name"
    return None


def _contains_sensitive_value(value: Any, key: str | None) -> bool:
    if isinstance(value, str):
        stripped = value.strip()
        if SENSITIVE_VALUE_RE.search(stripped):
            return True
        if _looks_like_raw_json_body(stripped):
            return True
        if key not in HASH_OR_TOKEN_KEYS and LONG_SECRET_RE.fullmatch(stripped):
            return True
        return False
    if isinstance(value, dict):
        return any(
            _removal_reason_for_key(str(item_key)) is not None
            or _contains_sensitive_value(item_value, str(item_key))
            for item_key, item_value in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_value(item, key) for item in value)
    return False


def _looks_like_raw_json_body(value: str) -> bool:
    if not (
        (value.startswith("{") and value.endswith("}"))
        or (value.startswith("[") and value.endswith("]"))
    ):
        return False
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, (dict, list))


def _validate_payload(payload: Any, path: str, errors: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path != "$" else f"$.{key_text}"
            if _removal_reason_for_key(key_text):
                errors.append(f"sensitive key found at {child_path}")
            if key_text not in ALLOWED_KEYS and key_text not in {
                "sanitized_context",
                "redaction_summary",
                "removed_field_count",
                "removed_fields",
                "path",
                "reason",
                "sensitive_data_included",
            }:
                errors.append(f"non-allowlisted key found at {child_path}")
            if _contains_sensitive_value(value, key_text):
                errors.append(f"sensitive value pattern found at {child_path}")
            if isinstance(value, (dict, list)):
                _validate_payload(value, child_path, errors)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _validate_payload(item, f"{path}[{index}]", errors)
    elif _contains_sensitive_value(payload, None):
        errors.append(f"sensitive value pattern found at {path}")
