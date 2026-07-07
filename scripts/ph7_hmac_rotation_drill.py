#!/usr/bin/env python3
"""Generate and validate PH7 partner HMAC rotation evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
DEFAULT_REPORT_DIR = ROOT_DIR / "reports/security/ph7-hmac-rotation"
SAMPLE_REPORT = DEFAULT_REPORT_DIR / "sample-hmac-rotation-report.json"
FIXED_NOW = dt.datetime(2026, 7, 7, 0, 0, tzinfo=dt.timezone.utc)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.security.partner_hmac import (  # noqa: E402
    PartnerSecret,
    PartnerSecretRegistry,
    SecretStatus,
    build_partner_canonical_request,
    generate_partner_hmac_signature,
    verify_partner_hmac_request,
)

REQUIRED_CASES = {
    "current_secret_success",
    "previous_secret_inside_window_success",
    "previous_secret_expired_reject",
    "revoked_secret_reject",
    "disabled_client_reject",
    "timestamp_skew_reject",
    "missing_nonce_reject",
    "invalid_signature_reject",
    "next_secret_dry_run_success",
}
FORBIDDEN_TEXT_PATTERNS = [
    re.compile(r"Authorization\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"Basic\s+\S+", re.IGNORECASE),
    re.compile(r"HMAC\s+\S+", re.IGNORECASE),
    re.compile(r"X-Signature\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"raw_request_body\s*[:=]", re.IGNORECASE),
    re.compile(r"client_secret\s*[:=]", re.IGNORECASE),
    re.compile(r"access_token\s*[:=]", re.IGNORECASE),
    re.compile(r"refresh_token\s*[:=]", re.IGNORECASE),
    re.compile(r"database_url\s*[:=]", re.IGNORECASE),
]
FORBIDDEN_KEYS = {
    "authorization",
    "cookie",
    "set_cookie",
    "raw_body",
    "raw_request_body",
    "raw_signature",
    "raw_secret",
    "client_secret",
    "access_token",
    "refresh_token",
    "database_url",
}
ALLOWED_SECURITY_FLAG_KEYS = {
    "raw_secret_included",
    "raw_signature_included",
    "raw_body_included",
    "signature_present",
    "signature_algorithm",
    "secret_status",
}
ALLOWED_CASE_KEYS = {
    "client_token",
    "client_status",
    "key_id",
    "key_version",
    "secret_status",
    "request_case",
    "expected_result",
    "actual_result",
    "decision",
    "decision_reason",
    "timestamp_skew_seconds",
    "nonce_present",
    "canonical_request_hash",
    "body_hash",
    "signature_present",
    "signature_algorithm",
    "rotation_window_status",
    "raw_secret_included",
    "raw_signature_included",
    "raw_body_included",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, default=SAMPLE_REPORT)

    subparsers.add_parser("smoke")

    args = parser.parse_args()
    try:
        result = _handle(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"PH7 HMAC rotation drill error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "demo":
        report = build_report()
        output_path = args.output_dir / "sample-hmac-rotation-report.json"
        markdown_path = output_path.with_suffix(".md")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
        validation_errors = validate_report(output_path)
        if validation_errors:
            raise ValueError(json.dumps(validation_errors, ensure_ascii=False))
        return {
            "output": str(output_path),
            "report": str(markdown_path),
            "case_count": len(report["cases"]),
            "validation_errors": [],
        }

    if args.command == "validate":
        errors = validate_report(args.input)
        if errors:
            raise SystemExit(
                json.dumps(
                    {"input": str(args.input), "validation_errors": errors},
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
        return {"input": str(args.input), "validation_errors": []}

    if args.command == "smoke":
        report = build_report()
        errors = validate_report_payload(report)
        if errors:
            raise SystemExit(json.dumps({"validation_errors": errors}, indent=2))
        return {
            "run_id": report["run_id"],
            "case_count": len(report["cases"]),
            "validation_errors": [],
        }

    raise SystemExit(f"unknown command: {args.command}")


def build_report() -> dict[str, Any]:
    cases = [
        _case(
            "current_secret_success",
            key_id="key-current",
            signing_value="demo-current-value",
            expected_result="ACCEPT",
        ),
        _case(
            "previous_secret_inside_window_success",
            key_id="key-previous",
            signing_value="demo-previous-value",
            expected_result="ACCEPT",
        ),
        _case(
            "previous_secret_expired_reject",
            key_id="key-previous-expired",
            signing_value="demo-expired-previous-value",
            expected_result="REJECT",
        ),
        _case(
            "revoked_secret_reject",
            key_id="key-revoked",
            signing_value="demo-revoked-value",
            expected_result="REJECT",
        ),
        _case(
            "disabled_client_reject",
            client_id="bank-disabled",
            key_id="key-current",
            signing_value="demo-disabled-value",
            expected_result="REJECT",
        ),
        _case(
            "timestamp_skew_reject",
            key_id="key-current",
            signing_value="demo-current-value",
            timestamp=(FIXED_NOW - dt.timedelta(minutes=10)).isoformat(),
            expected_result="REJECT",
        ),
        _case(
            "missing_nonce_reject",
            key_id="key-current",
            signing_value="demo-current-value",
            nonce="",
            expected_result="REJECT",
        ),
        _case(
            "invalid_signature_reject",
            key_id="key-current",
            signing_value="demo-current-value",
            signature="0" * 64,
            expected_result="REJECT",
        ),
        _case(
            "next_secret_dry_run_success",
            key_id="key-next",
            signing_value="demo-next-value",
            expected_result="ACCEPT",
            allow_next_for_dry_run=True,
        ),
    ]
    return {
        "run_id": "ph7-hmac-rotation-sample",
        "generated_at": FIXED_NOW.isoformat(),
        "scenario": "partner_secret_rotation_hmac_hardening",
        "policy": {
            "signature_algorithm": "HMAC-SHA256",
            "canonical_request": "{method}\\n{path}\\n{timestamp}\\n{nonce}\\n{body_sha256}",
            "timestamp_skew_seconds": 300,
            "nonce_required": True,
            "nonce_persistence": "follow_up_candidate",
            "raw_secret_included": False,
            "raw_signature_included": False,
            "raw_body_included": False,
        },
        "cases": cases,
        "sensitive_data_included": False,
        "runbook_reference": "docs/49-ph7-partner-secret-rotation-hmac-hardening.md",
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# PH7 HMAC Rotation Drill Report",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Sensitive data included: `{report['sensitive_data_included']}`",
        f"- Nonce persistence: `{report['policy']['nonce_persistence']}`",
        "",
        "| Case | Result | Reason | Secret Status | Window |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        lines.append(
            "| {case} | {result} | {reason} | {status} | {window} |".format(
                case=case["request_case"],
                result=case["actual_result"],
                reason=case["decision_reason"],
                status=case["secret_status"],
                window=case["rotation_window_status"],
            )
        )
    lines.extend(
        [
            "",
            "Raw secret, raw signature, Authorization header, and raw request body are not included.",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_report(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_report_payload(payload)


def validate_report_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cases = payload.get("cases")
    if not isinstance(cases, list):
        errors.append("cases must be a list")
        cases = []

    found_cases = {case.get("request_case") for case in cases if isinstance(case, dict)}
    missing_cases = sorted(REQUIRED_CASES - found_cases)
    if missing_cases:
        errors.append(f"missing required cases: {', '.join(missing_cases)}")

    if payload.get("sensitive_data_included") is not False:
        errors.append("sensitive_data_included must be false")

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case[{index}] must be an object")
            continue
        extra_keys = sorted(set(case) - ALLOWED_CASE_KEYS)
        if extra_keys:
            errors.append(
                f"{case.get('request_case', index)} has unexpected keys: "
                f"{', '.join(extra_keys)}"
            )
        for flag in (
            "raw_secret_included",
            "raw_signature_included",
            "raw_body_included",
        ):
            if case.get(flag) is not False:
                errors.append(f"{case.get('request_case', index)} {flag} must be false")
        if case.get("actual_result") != case.get("expected_result"):
            errors.append(f"{case.get('request_case', index)} result mismatch")

    _validate_keys(payload, errors)
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"forbidden text pattern found: {pattern.pattern}")
    return sorted(set(errors))


def _case(
    request_case: str,
    *,
    key_id: str,
    signing_value: str,
    expected_result: str,
    client_id: str = "bank-a",
    timestamp: str = FIXED_NOW.isoformat(),
    nonce: str = "nonce-001",
    signature: str | None = None,
    allow_next_for_dry_run: bool = False,
) -> dict[str, Any]:
    raw_body = b'{"amount":1000,"currency":"KRW"}'
    canonical = build_partner_canonical_request(
        "POST",
        "/api/v1/transaction-events",
        timestamp,
        nonce,
        raw_body,
    )
    provided_signature = signature
    if provided_signature is None:
        provided_signature = generate_partner_hmac_signature(signing_value, canonical)
    result = verify_partner_hmac_request(
        registry=_registry(),
        method="POST",
        path="/api/v1/transaction-events",
        timestamp=timestamp,
        nonce=nonce,
        raw_body=raw_body,
        client_id=client_id,
        key_id=key_id,
        signature=provided_signature,
        now=FIXED_NOW,
        allowed_skew_seconds=300,
        allow_next_for_dry_run=allow_next_for_dry_run,
        request_case=request_case,
        expected_result=expected_result,
    )
    return result.to_report_dict()


def _registry() -> PartnerSecretRegistry:
    return PartnerSecretRegistry(
        [
            PartnerSecret(
                "bank-a", "key-current", "demo-current-value", SecretStatus.CURRENT
            ),
            PartnerSecret(
                "bank-a",
                "key-previous",
                "demo-previous-value",
                SecretStatus.PREVIOUS,
                previous_valid_until=FIXED_NOW + dt.timedelta(minutes=5),
            ),
            PartnerSecret(
                "bank-a",
                "key-previous-expired",
                "demo-expired-previous-value",
                SecretStatus.PREVIOUS,
                previous_valid_until=FIXED_NOW - dt.timedelta(seconds=1),
            ),
            PartnerSecret(
                "bank-a", "key-revoked", "demo-revoked-value", SecretStatus.REVOKED
            ),
            PartnerSecret("bank-a", "key-next", "demo-next-value", SecretStatus.NEXT),
            PartnerSecret(
                "bank-disabled",
                "key-current",
                "demo-disabled-value",
                SecretStatus.DISABLED,
                client_enabled=False,
            ),
        ]
    )


def _validate_keys(value: Any, errors: list[str], path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.replace("-", "_").lower()
            if (
                normalized in FORBIDDEN_KEYS
                and normalized not in ALLOWED_SECURITY_FLAG_KEYS
            ):
                errors.append(f"forbidden key at {path}.{key}")
            _validate_keys(nested, errors, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_keys(nested, errors, f"{path}[{index}]")


if __name__ == "__main__":
    raise SystemExit(main())
