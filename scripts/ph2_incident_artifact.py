#!/usr/bin/env python3
"""Create and validate PH2 out-of-band incident artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INCIDENTS_DIR = ROOT_DIR / "reports/incidents"
DEFAULT_WRITE_SUSPEND_STATE = ROOT_DIR / "reports/runtime/write-suspend-state.json"

ALLOWED_KEYS = {
    "active",
    "activated_at",
    "activated_by",
    "command_name",
    "confidence_candidate",
    "container_name",
    "count",
    "created_at",
    "created_by",
    "dependency",
    "duration_ms",
    "error_code",
    "evidence_files",
    "exit_code",
    "finished_at",
    "health_status",
    "http_status",
    "incident_id",
    "manual_required",
    "manual_review_required",
    "ready_status",
    "reason",
    "result",
    "resume_reason",
    "resumed_at",
    "resumed_by",
    "retry_after_seconds",
    "retryable",
    "route_group",
    "run_id",
    "sanitized",
    "scenario",
    "sensitive_data_included",
    "service_name",
    "severity_candidate",
    "source",
    "started_at",
    "state",
    "write_suspended",
}

SENSITIVE_KEY_RE = re.compile(
    r"(authorization|cookie|database_url|db_password|password|secret|signature|"
    r"idempotency[-_]?key|account[-_]?no|account[-_]?number|access[-_]?token|"
    r"refresh[-_]?token|private[-_]?key|connection[-_]?string|raw[-_]?body|"
    r"request[-_]?body|response[-_]?body)",
    re.IGNORECASE,
)
SENSITIVE_TEXT_RE = re.compile(
    r"(Authorization\s*[:=]\s*\S+|X-Signature\s*[:=]\s*\S+|"
    r"x_signature\s*=\s*\S+|Idempotency-Key\s*[:=]\s*\S+|"
    r"idempotency_key\s*=\s*\S+|account_no\s*=\s*\S+|"
    r"account_number\s*=\s*\S+|DATABASE_URL\s*=|Bearer\s+\S+|"
    r"Basic\s+\S+|postgresql://[^\\s)]+|synthetic-authorization-token|"
    r"synthetic-signature-value|synthetic-account-number-1234|"
    r"synthetic-idempotency-key)",
    re.IGNORECASE,
)

MANUAL_REQUIRED = [
    "confirm DB recovery",
    "approve write resume",
    "review consistency result",
]
EVIDENCE_FILES = [
    "write-suspend-state.json",
    "health-ready-summary.json",
    "docker-compose-status.txt",
    "consistency-summary.json",
    "command-results.json",
    "sanitized-report.md",
]


def sanitize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key)
            if SENSITIVE_KEY_RE.search(key_text):
                continue
            if key_text not in ALLOWED_KEYS:
                continue
            sanitized[key_text] = sanitize_payload(value)
        return sanitized
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str) and SENSITIVE_TEXT_RE.search(payload):
        return "[REDACTED]"
    return payload


def create_artifact(
    *,
    scenario: str,
    run_id: str | None,
    source: str,
    output_root: Path,
    write_suspend_state: Path,
    ph1_report_dir: Path | None,
) -> Path:
    created_at = _now_kst()
    incident_dir = _create_unique_incident_dir(
        output_root, _incident_id(created_at, scenario)
    )
    incident_id = incident_dir.name
    (incident_dir / "raw").mkdir()
    (incident_dir / "raw" / "README.md").write_text(
        "# Raw Evidence\n\nRaw logs are not collected by PH2 by default.\n",
        encoding="utf-8",
    )

    manifest = {
        "incident_id": incident_id,
        "scenario": scenario,
        "severity_candidate": _severity_for(scenario),
        "confidence_candidate": 0.8 if scenario == "POSTGRES_DOWN" else 0.6,
        "created_at": created_at.isoformat(),
        "created_by": "ph2_incident_artifact",
        "source": source,
        "run_id": run_id or "not_collected",
        "sanitized": True,
        "sensitive_data_included": False,
        "manual_review_required": True,
        "evidence_files": EVIDENCE_FILES,
        "manual_required": MANUAL_REQUIRED,
    }
    _write_json(incident_dir / "manifest.json", manifest)

    _write_json(
        incident_dir / "write-suspend-state.json",
        _load_sanitized_write_suspend_state(write_suspend_state),
    )
    _write_json(
        incident_dir / "health-ready-summary.json",
        {
            "service_name": "financial-event-api",
            "health_status": "not_collected",
            "ready_status": "not_collected",
            "http_status": "not_collected",
            "dependency": "postgres",
        },
    )
    _write_json(
        incident_dir / "consistency-summary.json",
        _consistency_summary(ph1_report_dir),
    )
    _write_json(
        incident_dir / "command-results.json",
        {
            "command_name": "ph2_incident_artifact_create",
            "exit_code": 0,
            "result": "created",
            "sensitive_data_included": False,
        },
    )
    (incident_dir / "docker-compose-status.txt").write_text(
        _docker_compose_status(),
        encoding="utf-8",
    )
    (incident_dir / "sanitized-report.md").write_text(
        render_report(manifest, _consistency_summary(ph1_report_dir)),
        encoding="utf-8",
    )
    return incident_dir


def render_report(manifest: dict[str, Any], consistency: dict[str, Any]) -> str:
    retry_after_present = consistency.get("retry_after_present", "unknown")
    consistency_check = consistency.get("result", "not_collected")
    return f"""# Incident Report Draft

## Incident Metadata

- Incident ID: {manifest["incident_id"]}
- Scenario: {manifest["scenario"]}
- Severity Candidate: {manifest["severity_candidate"]}
- Confidence Candidate: {manifest["confidence_candidate"]}
- Source: {manifest["source"]}
- Run ID: {manifest["run_id"]}
- Created At: {manifest["created_at"]}
- Manual Review Required: {str(manifest["manual_review_required"]).lower()}
- Sensitive Data Included: false

## Summary

PostgreSQL write path was unavailable or write traffic was suspended.
Financial write requests were expected to fail closed with 503 + Retry-After.

## Primary Signals

- readiness: not_collected
- write_suspended: captured_if_state_file_exists
- retry_after_present: {retry_after_present}
- consistency_check: {consistency_check}

## Auto Actions Captured

- write suspend state captured
- count-only consistency summary captured
- command result summary captured

## Manual Actions Required

- confirm DB recovery
- review consistency gate
- approve write resume
- review whether recovery case creation is required in PH3

## Evidence Files

- manifest.json
- write-suspend-state.json
- health-ready-summary.json
- consistency-summary.json
- docker-compose-status.txt
- command-results.json

## Sanitization

- raw account number: not included
- raw idempotency key: not included
- HMAC signature: not included
- Authorization header: not included
- raw request body: not included
- sensitive_data_included: false

## Follow-up

- PH3 Incident Analyzer MVP
- PH4 Recovery Case / Quarantine
"""


def validate_artifact(incident_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = incident_dir / "manifest.json"
    if not manifest_path.exists():
        return [f"missing {manifest_path}"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"manifest is invalid JSON: {exc}"]

    required = {
        "incident_id",
        "scenario",
        "severity_candidate",
        "confidence_candidate",
        "created_at",
        "created_by",
        "source",
        "run_id",
        "sanitized",
        "sensitive_data_included",
        "manual_review_required",
        "evidence_files",
        "manual_required",
    }
    missing = sorted(required - set(manifest))
    if missing:
        errors.append(f"manifest missing fields: {', '.join(missing)}")
    if manifest.get("incident_id") != incident_dir.name:
        errors.append("manifest incident_id does not match incident directory")
    if manifest.get("sanitized") is not True:
        errors.append("manifest sanitized must be true")
    if manifest.get("sensitive_data_included") is not False:
        errors.append("manifest sensitive_data_included must be false")

    for relative in EVIDENCE_FILES:
        if not (incident_dir / relative).exists():
            errors.append(f"missing evidence file: {relative}")

    for path in incident_dir.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if SENSITIVE_TEXT_RE.search(text):
            errors.append(
                f"sensitive value pattern found: {path.relative_to(incident_dir)}"
            )
        if path.suffix == ".json":
            try:
                _validate_json_keys(
                    json.loads(text), path.relative_to(incident_dir), errors
                )
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON {path.relative_to(incident_dir)}: {exc}")

    report_path = incident_dir / "sanitized-report.md"
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
        if f"- Incident ID: {manifest.get('incident_id')}" not in report_text:
            errors.append("report incident_id does not match manifest")
        if "Sensitive Data Included: false" not in report_text:
            errors.append("report must declare Sensitive Data Included: false")
    return errors


def latest_incident_dir(output_root: Path) -> Path:
    candidates = [path for path in output_root.glob("inc-*") if path.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"no incident directories found in {output_root}")
    return max(candidates, key=lambda path: path.name)


def _validate_json_keys(payload: Any, label: Path, errors: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                errors.append(f"sensitive key found in {label}: {key}")
            _validate_json_keys(value, label, errors)
    elif isinstance(payload, list):
        for item in payload:
            _validate_json_keys(item, label, errors)


def _load_sanitized_write_suspend_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {
            "active": False,
            "reason": "not_collected",
            "retry_after_seconds": "not_collected",
            "source": "not_collected",
            "run_id": "not_collected",
            "sensitive_data_included": False,
        }
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "active": True,
            "reason": "state_file_invalid",
            "source": "artifact_parse_failed",
            "result": "invalid_state_json",
            "sensitive_data_included": False,
        }
    sanitized = sanitize_payload(payload)
    if isinstance(sanitized, dict):
        sanitized["sensitive_data_included"] = False
        return sanitized
    return {"result": "invalid_state_payload", "sensitive_data_included": False}


def _consistency_summary(ph1_report_dir: Path | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "result": "not_collected",
        "retry_after_present": "unknown",
        "count": "not_collected",
        "sensitive_data_included": False,
    }
    if ph1_report_dir is None:
        return summary
    report_path = ph1_report_dir / "report.md"
    if not report_path.exists():
        summary["result"] = "ph1_report_not_found"
        return summary
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    for key in (
        "duplicate_event_count",
        "duplicate_ledger_count",
        "blocked_event_record_count_after_replay",
        "blocked_ledger_count_after_replay",
    ):
        match = re.search(rf"- {key}: ([0-9]+)", text)
        if match:
            summary[key] = int(match.group(1))
    summary["retry_after_present"] = (
        "yes" if "retry_after_header_present: yes" in text else "unknown"
    )
    summary["result"] = "captured"
    return sanitize_payload(summary)


def _docker_compose_status() -> str:
    command = [
        "docker",
        "compose",
        "ps",
        "--format",
        "table {{.Name}}\t{{.State}}\t{{.Health}}",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "docker_compose_status: not_collected\n"
    if result.returncode != 0:
        return "docker_compose_status: not_collected\n"
    return result.stdout or "docker_compose_status: not_collected\n"


def _severity_for(scenario: str) -> str:
    if scenario in {"POSTGRES_DOWN", "CONSISTENCY_VIOLATION"}:
        return "SEV1"
    return "SEV2"


def _incident_id(created_at: dt.datetime, scenario: str) -> str:
    slug = scenario.lower().replace("_", "-")
    return f"inc-{created_at.strftime('%Y%m%d-%H%M%S')}-{slug}"


def _create_unique_incident_dir(output_root: Path, incident_id: str) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    for suffix in [""] + [f"-{index:03d}" for index in range(1, 1000)]:
        incident_dir = output_root / f"{incident_id}{suffix}"
        try:
            incident_dir.mkdir()
        except FileExistsError:
            continue
        return incident_dir
    raise FileExistsError(
        f"could not allocate unique incident directory for {incident_id}"
    )


def _now_kst() -> dt.datetime:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--scenario", required=True)
    create_parser.add_argument("--run-id")
    create_parser.add_argument("--source", default="manual")
    create_parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_INCIDENTS_DIR
    )
    create_parser.add_argument(
        "--write-suspend-state", type=Path, default=DEFAULT_WRITE_SUSPEND_STATE
    )
    create_parser.add_argument("--ph1-report-dir", type=Path)

    sanitize_parser = subparsers.add_parser("sanitize")
    sanitize_parser.add_argument("--input", type=Path, required=True)
    sanitize_parser.add_argument("--output", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--incident-dir", type=Path)
    validate_parser.add_argument("--latest", action="store_true")
    validate_parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_INCIDENTS_DIR
    )

    args = parser.parse_args()
    if args.command == "create":
        incident_dir = create_artifact(
            scenario=args.scenario,
            run_id=args.run_id,
            source=args.source,
            output_root=args.output_root,
            write_suspend_state=args.write_suspend_state,
            ph1_report_dir=args.ph1_report_dir,
        )
        print(incident_dir)
        return 0
    if args.command == "sanitize":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _write_json(args.output, sanitize_payload(_load_json(args.input)))
        print(args.output)
        return 0

    if args.latest:
        incident_dir = latest_incident_dir(args.output_root)
    elif args.incident_dir is not None:
        incident_dir = args.incident_dir
    else:
        print("--incident-dir or --latest is required", file=sys.stderr)
        return 2

    errors = validate_artifact(incident_dir)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated: {incident_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
