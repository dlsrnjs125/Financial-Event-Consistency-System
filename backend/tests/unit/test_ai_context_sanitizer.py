import importlib.util
import json
from pathlib import Path

import pytest

from app.security.ai_context_sanitizer import (
    sanitize_context,
    validate_sanitized_context,
)

ROOT_DIR = Path(__file__).resolve().parents[3]
PH6_SPEC = importlib.util.spec_from_file_location(
    "ph6_ai_context", ROOT_DIR / "scripts/ph6_ai_context.py"
)
ph6_ai_context = importlib.util.module_from_spec(PH6_SPEC)
assert PH6_SPEC and PH6_SPEC.loader
PH6_SPEC.loader.exec_module(ph6_ai_context)


def test_allowlisted_fields_are_kept() -> None:
    result = sanitize_context(
        {
            "incident_id": "inc-001",
            "classification": "POSTGRES_DOWN_WRITE_SUSPENDED",
            "severity": "SEV1",
            "confidence": 0.9,
            "consistency_counts": {"stale_processing_count": 2},
        }
    )

    assert result.sanitized_context == {
        "incident_id": "inc-001",
        "classification": "POSTGRES_DOWN_WRITE_SUSPENDED",
        "severity": "SEV1",
        "confidence": 0.9,
        "consistency_counts": {"stale_processing_count": 2},
    }


def test_unknown_fields_are_removed() -> None:
    result = sanitize_context({"incident_id": "inc-001", "debug_dump": "details"})

    assert result.sanitized_context == {"incident_id": "inc-001"}
    assert result.removed_fields[0].to_dict() == {
        "path": "$.debug_dump",
        "reason": "not_in_allowlist",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("account_no", "ACC-001"),
        ("idempotency_key", "idem-raw"),
        ("authorization", "Bearer REDACTED"),
        ("hmac_signature", "HMAC REDACTED"),
        ("raw_request_body", '{"amount": 1000}'),
    ],
)
def test_sensitive_fields_are_removed(field: str, value: str) -> None:
    result = sanitize_context({"incident_id": "inc-001", field: value})

    assert result.sanitized_context == {"incident_id": "inc-001"}
    assert result.removed_fields[0].path == f"$.{field}"
    assert result.removed_fields[0].reason == "sensitive_field_name"


def test_nested_sensitive_fields_are_removed_without_dropping_safe_siblings() -> None:
    result = sanitize_context(
        {
            "primary_signals": [
                {
                    "status": "WAITING_APPROVAL",
                    "authorization": "Bearer REDACTED",
                    "request_body": '{"amount": 1000}',
                }
            ],
            "metric_summary": {
                "stale_processing_count": 1,
                "account_no": "ACC-001",
            },
        }
    )

    assert result.sanitized_context == {
        "primary_signals": [{"status": "WAITING_APPROVAL"}],
        "metric_summary": {"stale_processing_count": 1},
    }
    removed_paths = {field.path for field in result.removed_fields}
    assert "$.primary_signals[0].authorization" in removed_paths
    assert "$.primary_signals[0].request_body" in removed_paths
    assert "$.metric_summary.account_no" in removed_paths


def test_redaction_summary_does_not_include_raw_values() -> None:
    result = sanitize_context(
        {
            "incident_id": "inc-001",
            "authorization": "Bearer REDACTED",
            "raw_request_body": '{"amount": 1000}',
        }
    )
    summary_text = json.dumps(result.to_dict()["redaction_summary"])

    assert "Bearer" not in summary_text
    assert "amount" not in summary_text


def test_tokens_and_hashes_are_allowed() -> None:
    result = sanitize_context(
        {
            "account_token": "acctok_safe_001",
            "event_token": "evttok_safe_001",
            "idempotency_key_hash": "a" * 64,
            "masked_target_id": "acct-****-001",
            "request_hash": "b" * 64,
        }
    )

    assert result.sanitized_context == {
        "account_token": "acctok_safe_001",
        "event_token": "evttok_safe_001",
        "idempotency_key_hash": "a" * 64,
        "masked_target_id": "acct-****-001",
        "request_hash": "b" * 64,
    }


def test_validate_fails_when_sensitive_pattern_remains() -> None:
    payload = {
        "sanitized_context": {
            "incident_id": "inc-001",
            "runbook_reference": "Authorization: REDACTED",
        },
        "redaction_summary": {"removed_field_count": 0, "removed_fields": []},
        "sensitive_data_included": False,
    }

    errors = validate_sanitized_context(payload)

    assert any("sensitive value pattern" in error for error in errors)


def test_empty_input_returns_empty_context() -> None:
    result = sanitize_context({})

    assert result.sanitized_context == {}
    assert result.removed_fields == ()


def test_list_root_is_supported() -> None:
    result = sanitize_context(
        [
            {"incident_id": "inc-001", "account_no": "ACC-001"},
            {"run_id": "run-001", "status": "WAITING_APPROVAL"},
        ]
    )

    assert result.sanitized_context == [
        {"incident_id": "inc-001"},
        {"run_id": "run-001", "status": "WAITING_APPROVAL"},
    ]


def test_malformed_json_is_handled_by_caller() -> None:
    with pytest.raises(json.JSONDecodeError):
        json.loads('{"incident_id": ')


def test_latest_source_dir_supports_recovery_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery_root = tmp_path / "reports" / "recovery-cases"
    old_case = recovery_root / "rc-20260707-010000"
    old_case.mkdir(parents=True)
    (old_case / "recovery-case.json").write_text(
        '{"case_type": "STALE_PROCESSING"}',
        encoding="utf-8",
    )
    sample_case = recovery_root / "sample-recovery-case.json"
    sample_case.write_text(
        '{"case_type": "STALE_PROCESSING", "masked_target_id": "acct-****-001"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(ph6_ai_context, "ROOT_DIR", tmp_path)

    assert ph6_ai_context._latest_source_dir("recovery-cases") == sample_case


def test_sanitize_latest_recovery_case_writes_valid_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery_root = tmp_path / "reports" / "recovery-cases"
    recovery_root.mkdir(parents=True)
    (recovery_root / "sample-recovery-case.json").write_text(
        json.dumps(
            {
                "case_type": "STALE_PROCESSING",
                "classification": "STALE_PROCESSING_DETECTED",
                "masked_target_id": "acct-****-001",
                "account_no": "ACC-001",
                "idempotency_key": "raw-idem-key",
            }
        ),
        encoding="utf-8",
    )
    output_root = tmp_path / "reports" / "ai-context"

    monkeypatch.setattr(ph6_ai_context, "ROOT_DIR", tmp_path)
    args = type(
        "Args",
        (),
        {
            "command": "sanitize-latest",
            "source": "recovery-cases",
            "output_dir": output_root,
        },
    )()

    result = ph6_ai_context._handle(args)

    payload = json.loads(Path(result["output"]).read_text(encoding="utf-8"))
    assert result["validation_errors"] == []
    assert payload["sanitized_context"]["masked_target_id"] == "acct-****-001"
    assert "account_no" not in payload["sanitized_context"]
    assert "idempotency_key" not in payload["sanitized_context"]
