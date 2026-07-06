#!/usr/bin/env python3
"""Analyze PH2 incident artifacts with deterministic PH3 MVP rules."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INCIDENTS_DIR = ROOT_DIR / "reports/incidents"
ANALYZER_VERSION = "ph3-mvp-v1"
RESULT_FILE = "analyzer-result.json"
REPORT_FILE = "incident-analysis.md"

PH2_SPEC = importlib.util.spec_from_file_location(
    "ph2_incident_artifact", ROOT_DIR / "scripts/ph2_incident_artifact.py"
)
ph2_incident_artifact = importlib.util.module_from_spec(PH2_SPEC)
assert PH2_SPEC and PH2_SPEC.loader
PH2_SPEC.loader.exec_module(ph2_incident_artifact)

MANUAL_POSTGRES_DOWN = [
    "confirm PostgreSQL recovery",
    "review consistency gate",
    "approve write resume",
    "decide whether recovery case creation is required in PH4",
]
MANUAL_SANITIZATION_RISK = [
    "do not share artifact with AI or external documents",
    "rerun PH2 validation",
    "remove or regenerate unsafe artifact",
]
MANUAL_CONSISTENCY = [
    "keep write suspended",
    "create recovery case in PH4",
    "review affected account/event scope",
]
MANUAL_UNKNOWN_DEPENDENCY = [
    "identify dependency failure source",
    "review ready/health evidence",
    "do not resume write until consistency gate is reviewed",
]
MANUAL_INSUFFICIENT = [
    "rerun artifact collection",
    "check PH2 create/validate logs",
    "do not make recovery decision from this report alone",
]
DEFAULT_LIMITS = [
    "PH3 does not execute recovery actions",
    "PH3 does not approve write resume",
    "PH3 does not query live Prometheus metrics",
    "PH3 does not call AI APIs",
]


def analyze_incident(incident_dir: Path) -> dict[str, Any]:
    manifest = _read_json_or_empty(incident_dir / "manifest.json")
    write_state = _read_json_or_empty(incident_dir / "write-suspend-state.json")
    health_ready = _read_json_or_empty(incident_dir / "health-ready-summary.json")
    consistency = _read_json_or_empty(incident_dir / "consistency-summary.json")
    command_results = _read_json_or_empty(incident_dir / "command-results.json")
    validation_errors = ph2_incident_artifact.validate_artifact(incident_dir)

    context = {
        "incident_id": str(manifest.get("incident_id") or incident_dir.name),
        "manifest": manifest,
        "write_state": write_state,
        "health_ready": health_ready,
        "consistency": consistency,
        "command_results": command_results,
        "validation_errors": validation_errors,
        "missing_evidence_count": _missing_evidence_count(
            incident_dir,
            [
                "manifest.json",
                "write-suspend-state.json",
                "health-ready-summary.json",
                "consistency-summary.json",
                "command-results.json",
                "sanitized-report.md",
            ],
        ),
    }
    result = _classify(context)
    _write_json(incident_dir / RESULT_FILE, result)
    (incident_dir / REPORT_FILE).write_text(render_analysis(result), encoding="utf-8")
    return result


def validate_analysis(incident_dir: Path) -> list[str]:
    errors: list[str] = []
    result_path = incident_dir / RESULT_FILE
    report_path = incident_dir / REPORT_FILE
    if not result_path.exists():
        errors.append(f"missing {RESULT_FILE}")
        return errors
    if not report_path.exists():
        errors.append(f"missing {REPORT_FILE}")

    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{RESULT_FILE} is invalid JSON: {exc}"]

    required = {
        "incident_id",
        "analyzer_version",
        "analyzed_at",
        "classification",
        "severity_candidate",
        "confidence_candidate",
        "primary_signals",
        "auto_actions_observed",
        "manual_actions_required",
        "recommended_runbooks",
        "limits",
        "manual_review_required",
        "sensitive_data_included",
    }
    missing = sorted(required - set(result))
    if missing:
        errors.append(f"{RESULT_FILE} missing fields: {', '.join(missing)}")
    if result.get("incident_id") != incident_dir.name:
        errors.append("analyzer result incident_id does not match incident directory")
    if result.get("analyzer_version") != ANALYZER_VERSION:
        errors.append("unexpected analyzer_version")
    if result.get("manual_review_required") is not True:
        errors.append("manual_review_required must be true")
    if result.get("sensitive_data_included") is not False:
        errors.append("sensitive_data_included must be false")

    for path in [result_path, report_path]:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if ph2_incident_artifact.SENSITIVE_TEXT_RE.search(text):
                errors.append(f"sensitive value pattern found: {path.name}")
    return errors


def render_analysis(result: dict[str, Any]) -> str:
    return f"""# Incident Analysis Draft

## Summary

- Classification: {result["classification"]}
- Severity Candidate: {result["severity_candidate"]}
- Confidence Candidate: {result["confidence_candidate"]}
- Manual Review Required: true
- Sensitive Data Included: false

## Primary Signals

{_markdown_list(result["primary_signals"])}

## Why This Classification

{result["why_this_classification"]}

## Observed Auto Actions

{_markdown_list(result["auto_actions_observed"])}

## Manual Actions Required

{_markdown_list(result["manual_actions_required"])}

## Recommended Runbooks

{_markdown_list(result["recommended_runbooks"])}

## Limits

{_markdown_list(result["limits"])}

## Follow-up

- PH4 Recovery Case / Quarantine
"""


def latest_incident_dir(output_root: Path) -> Path:
    return ph2_incident_artifact.latest_incident_dir(output_root)


def _classify(context: dict[str, Any]) -> dict[str, Any]:
    rule = _select_rule(context)
    incident_id = str(context["incident_id"])
    primary_signals = _primary_signals(context, rule["classification"])
    return {
        "incident_id": incident_id,
        "analyzer_version": ANALYZER_VERSION,
        "analyzed_at": _now_kst(),
        "classification": rule["classification"],
        "severity_candidate": rule["severity_candidate"],
        "confidence_candidate": rule["confidence_candidate"],
        "primary_signals": primary_signals,
        "auto_actions_observed": _auto_actions_observed(context),
        "manual_actions_required": rule["manual_actions_required"],
        "recommended_runbooks": rule["recommended_runbooks"],
        "limits": DEFAULT_LIMITS,
        "manual_review_required": True,
        "sensitive_data_included": False,
        "why_this_classification": rule["why_this_classification"],
    }


def _select_rule(context: dict[str, Any]) -> dict[str, Any]:
    if _has_sanitization_risk(context):
        return _rule(
            "ARTIFACT_SANITIZATION_RISK",
            "SEV2",
            0.8,
            MANUAL_SANITIZATION_RISK,
            ["docs/39-sensitive-data-ai-governance-and-encryption-tradeoff.md"],
            "PH2 validation or manifest safety metadata indicates the artifact should not be shared before regeneration.",
        )
    if _has_consistency_issue(context):
        return _rule(
            "CONSISTENCY_ISSUE_CANDIDATE",
            "SEV1",
            0.85,
            MANUAL_CONSISTENCY,
            ["docs/runbooks/write-suspend-resume.md"],
            "Count-only consistency summary contains a non-zero duplicate or reconciliation failure count.",
        )
    if _is_postgres_down_write_suspended(context):
        return _rule(
            "POSTGRES_DOWN_WRITE_SUSPENDED",
            "SEV1",
            0.9,
            MANUAL_POSTGRES_DOWN,
            [
                "docs/runbooks/postgres-down.md",
                "docs/runbooks/write-suspend-resume.md",
            ],
            "Scenario and write-suspend evidence point to PostgreSQL write path unavailability.",
        )
    if _is_write_suspended_unknown(context):
        return _rule(
            "WRITE_SUSPENDED_UNKNOWN_DEPENDENCY",
            "SEV2",
            0.65,
            MANUAL_UNKNOWN_DEPENDENCY,
            ["docs/runbooks/write-suspend-resume.md"],
            "Write traffic is suspended, but the artifact does not identify PostgreSQL as the dependency.",
        )
    if _has_insufficient_evidence(context):
        return _rule(
            "INSUFFICIENT_EVIDENCE",
            "SEV2",
            0.4,
            MANUAL_INSUFFICIENT,
            ["docs/44-ph2-incident-artifact-sanitized-report.md"],
            "Required PH2 evidence is missing or too sparse for a reliable classification.",
        )
    return _rule(
        "UNKNOWN_INCIDENT",
        "SEV3",
        0.3,
        MANUAL_INSUFFICIENT,
        ["docs/37-incident-diagnosis-automation-design.md"],
        "No PH3 MVP rule matched the available sanitized artifact evidence.",
    )


def _rule(
    classification: str,
    severity: str,
    confidence: float,
    manual_actions: list[str],
    runbooks: list[str],
    why: str,
) -> dict[str, Any]:
    return {
        "classification": classification,
        "severity_candidate": severity,
        "confidence_candidate": confidence,
        "manual_actions_required": manual_actions,
        "recommended_runbooks": runbooks,
        "why_this_classification": why,
    }


def _has_sanitization_risk(context: dict[str, Any]) -> bool:
    manifest = context["manifest"]
    if not manifest:
        return False
    if manifest.get("sensitive_data_included") is not False:
        return True
    for error in context["validation_errors"]:
        lowered = error.lower()
        if "sensitive" in lowered or "sanitized must be true" in lowered:
            return True
    return False


def _has_consistency_issue(context: dict[str, Any]) -> bool:
    consistency = context["consistency"]
    for key in (
        "duplicate_ledger_count",
        "duplicate_external_event_count",
        "duplicate_event_count",
        "reconciliation_failure_count",
    ):
        if _positive_int(consistency.get(key)):
            return True
    return False


def _is_postgres_down_write_suspended(context: dict[str, Any]) -> bool:
    manifest = context["manifest"]
    write_state = context["write_state"]
    if manifest.get("scenario") == "POSTGRES_DOWN":
        return True
    if write_state.get("reason") == "postgres_unavailable":
        return True
    return bool(
        write_state.get("active") is True
        and write_state.get("source") == "postgres_probe"
    )


def _is_write_suspended_unknown(context: dict[str, Any]) -> bool:
    scenario = context["manifest"].get("scenario")
    return bool(
        context["write_state"].get("active") is True
        and scenario in {None, "", "unknown", "not_collected"}
    )


def _has_insufficient_evidence(context: dict[str, Any]) -> bool:
    if not context["manifest"]:
        return True
    if context["missing_evidence_count"] >= 3:
        return True
    return False


def _primary_signals(context: dict[str, Any], classification: str) -> list[str]:
    manifest = context["manifest"]
    write_state = context["write_state"]
    health_ready = context["health_ready"]
    consistency = context["consistency"]
    signals = [
        f"classification={classification}",
        f"scenario={manifest.get('scenario', 'unknown')}",
        f"write_suspend_state.active={write_state.get('active', 'not_collected')}",
        f"write_suspend_state.reason={write_state.get('reason', 'not_collected')}",
        f"ready_status={health_ready.get('ready_status', 'not_collected')}",
        f"consistency_result={consistency.get('result', 'not_collected')}",
        "sensitive_data_included=false",
    ]
    for key in (
        "duplicate_ledger_count",
        "duplicate_external_event_count",
        "duplicate_event_count",
        "reconciliation_failure_count",
    ):
        if key in consistency:
            signals.append(f"{key}={consistency[key]}")
    return signals


def _auto_actions_observed(context: dict[str, Any]) -> list[str]:
    actions = [
        "sanitized_artifact_created",
        "ph2_validation_checked",
    ]
    if context["write_state"]:
        actions.append("write_suspend_state_captured")
    if context["consistency"]:
        actions.append("count_only_consistency_summary_captured")
    if context["command_results"]:
        actions.append("command_result_summary_captured")
    return actions


def _read_json_or_empty(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _missing_evidence_count(incident_dir: Path, files: list[str]) -> int:
    return sum(1 for name in files if not (incident_dir / name).exists())


def _positive_int(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _markdown_list(items: list[str]) -> str:
    if not items:
        return "- not_collected"
    return "\n".join(f"- {item}" for item in items)


def _now_kst() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--incident-dir", type=Path)
    analyze_parser.add_argument("--latest", action="store_true")
    analyze_parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_INCIDENTS_DIR
    )

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--incident-dir", type=Path)
    validate_parser.add_argument("--latest", action="store_true")
    validate_parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_INCIDENTS_DIR
    )

    args = parser.parse_args()
    incident_dir = _select_incident_dir(args)
    if args.command == "analyze":
        result = analyze_incident(incident_dir)
        print(f"{incident_dir / RESULT_FILE}: {result['classification']}")
        return 0

    errors = validate_analysis(incident_dir)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated: {incident_dir}")
    return 0


def _select_incident_dir(args: argparse.Namespace) -> Path:
    if args.latest:
        return latest_incident_dir(args.output_root)
    if args.incident_dir is not None:
        return args.incident_dir
    raise SystemExit("--incident-dir or --latest is required")


if __name__ == "__main__":
    raise SystemExit(main())
