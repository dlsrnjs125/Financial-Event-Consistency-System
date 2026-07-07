#!/usr/bin/env python3
"""Generate and validate PH9 production hardening drill evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT_DIR / "Makefile"
DEFAULT_REPORT_DIR = ROOT_DIR / "reports/production-hardening/ph9-drill-plan"
SAMPLE_REPORT = DEFAULT_REPORT_DIR / "sample-production-hardening-drill-plan.json"
FIXED_GENERATED_AT = "2026-07-07T00:00:00+00:00"

REQUIRED_TOP_LEVEL_FIELDS = {
    "run_id",
    "generated_at",
    "phase",
    "scope",
    "current_status",
    "drill_count",
    "drills",
    "manual_approval_boundaries",
    "automation_boundaries",
    "candidate_commands_note",
    "follow_up_candidates",
    "validation_summary",
}
REQUIRED_DRILL_FIELDS = {
    "phase",
    "drill_id",
    "name",
    "goal",
    "linked_docs",
    "safe_to_auto_run",
    "manual_run_required",
    "requires_docker",
    "requires_k6",
    "requires_database",
    "commands",
    "candidate_commands",
    "expected_evidence",
    "safety_boundary",
    "manual_approval_required_for",
    "success_criteria",
    "failure_signals",
    "sensitive_data_policy",
    "status",
}
REQUIRED_PHASES = {"PH1", "PH2", "PH3", "PH4", "PH5", "PH6", "PH7", "PH8"}
MANUAL_APPROVAL_TERMS = [
    "write resume",
    "failover promote",
    "ledger compensation",
    "ledger correction",
    "customer impact",
    "partner secret rotation approval",
    "ai recovery adoption",
]
DESTRUCTIVE_COMMAND_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"docker\s+compose\s+(down|stop|pause|rm)",
        r"\brm\s+-",
        r"\bdelete\b",
        r"\btruncate\b",
        r"\bdrop\b",
        r"ph1-db-down-drill",
        r"ph2-db-down-incident-artifact",
        r"ph3-db-down-incident-analysis",
        r"ph1-write-suspend-resume",
        r"release-quarantine",
        r"\bapprove\b",
        r"failover",
        r"promote",
        r"compensation",
        r"k6-",
        r"latency-",
    )
]
CANDIDATE_COMMAND_ALLOW_TARGETS = {
    "ph1-db-down-drill",
    "ph2-db-down-incident-artifact",
    "ph3-db-down-incident-analysis",
    "ph4-recovery-case-from-latest",
    "ph5-reconciliation-run",
    "ph6-ai-context-sanitize-latest",
    "ph6-ai-context-recovery",
    "ph7-hmac-rotation-smoke",
}
SENSITIVE_TEXT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"Authorization\s*[:=]\s*\S+",
        r"Bearer\s+\S+",
        r"Basic\s+\S+",
        r"X-Signature\s*[:=]\s*\S+",
        r"Idempotency-Key\s*[:=]\s*\S+",
        r"\bclient_secret\b",
        r"\braw_secret\b",
        r"\braw_signature\b",
        r"\bhmac_signature\b",
        r"\braw_request_body\b",
        r"raw request body",
        r"\braw_account_no\b",
        r"\baccount_no\b",
        r"\braw_idempotency_key\b",
        r"\bdatabase_url\b",
        r"postgresql://\S+",
    )
]
FORBIDDEN_CLAIMS = [
    "queue 도입 시 바로 원장 반영 완료를 보장한다",
    "queue-first guarantees ledger completion",
    "HA 도입 시 consistency gate가 불필요하다",
    "HA removes the need for consistency gate",
    "AI automatically executes recovery",
    "AI가 복구안을 자동 채택한다",
    "AI가 금전 상태 변경을 승인한다",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, default=SAMPLE_REPORT)

    subparsers.add_parser("list")

    args = parser.parse_args()
    try:
        result = _handle(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"PH9 hardening drill error: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "demo":
        report = build_report()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = args.output_dir / "sample-production-hardening-drill-plan.json"
        markdown_path = output_path.with_suffix(".md")
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
        validation_errors = validate_report_payload(report)
        if validation_errors:
            raise ValueError(json.dumps(validation_errors, ensure_ascii=False))
        return {
            "output": str(output_path),
            "report": str(markdown_path),
            "drill_count": report["drill_count"],
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

    if args.command == "list":
        return {"drills": list_catalog_rows(build_report())}

    raise SystemExit(f"unknown command: {args.command}")


def build_report() -> dict[str, Any]:
    drills = _drill_catalog()
    return {
        "run_id": "ph9-production-hardening-drill-plan-sample",
        "generated_at": FIXED_GENERATED_AT,
        "phase": "PH9 Production Hardening Drill Plan & Evidence Runner",
        "scope": [
            "PH1~PH8 hardening drill catalog",
            "safe evidence report generation",
            "validation of automation and manual approval boundaries",
            "PH10/PH11 latency work linked only as follow-up candidates",
        ],
        "current_status": (
            "Implemented as a safe catalog/report/validator. Destructive drills, "
            "write resume, failover promote, financial correction, partner key "
            "retirement, and AI recovery adoption remain human-approved."
        ),
        "drill_count": len(drills),
        "drills": drills,
        "manual_approval_boundaries": [
            "PostgreSQL failover promote",
            "write resume after DB recovery or failover",
            "ledger correction or compensation",
            "customer or partner impact confirmation",
            "partner secret rotation approval",
            "queue replay or DLQ redrive",
            "AI-assisted recovery proposal adoption",
        ],
        "automation_boundaries": [
            "generate deterministic drill catalog",
            "validate required evidence and safety boundaries",
            "create sanitized JSON and Markdown reports",
            "run safe validators and read-only evidence checks",
            "leave state-changing drills as manual-run candidates",
        ],
        "candidate_commands_note": (
            "candidate_commands are not default auto-run commands. Operators must "
            "read the linked drill document and confirm the manual boundary before "
            "running them."
        ),
        "follow_up_candidates": [
            {
                "phase": "PH10",
                "name": "Latency attribution instrumentation",
                "linked_docs": [
                    "docs/41-latency-attribution-and-external-dependency-diagnosis.md"
                ],
                "status": "follow_up_candidate",
                "note": (
                    "PH9 does not implement latency attribution. k6 symptoms must "
                    "be correlated with Nginx, FastAPI, PostgreSQL, Redis, and "
                    "external dependency metrics in a later phase."
                ),
            },
            {
                "phase": "PH11",
                "name": "Latency drill test plan execution",
                "linked_docs": ["docs/42-latency-drill-test-plan.md"],
                "status": "follow_up_candidate",
                "note": (
                    "Latency drill targets remain candidate commands, not PH9 "
                    "completed drill commands."
                ),
            },
        ],
        "validation_summary": {
            "required_phases": sorted(REQUIRED_PHASES),
            "sensitive_data_included": False,
            "destructive_commands_allowed": False,
            "latency_drills_completed_in_ph9": False,
        },
    }


def validate_report(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_report_payload(payload)


def validate_report_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing_fields = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(payload))
    if missing_fields:
        errors.append(f"missing top-level fields: {', '.join(missing_fields)}")

    drills = payload.get("drills")
    if not isinstance(drills, list):
        errors.append("drills must be a list")
        drills = []

    if payload.get("drill_count") != len(drills):
        errors.append("drill_count must match drills length")

    phases = {drill.get("phase") for drill in drills if isinstance(drill, dict)}
    missing_phases = sorted(REQUIRED_PHASES - phases)
    if missing_phases:
        errors.append(f"missing required PH drills: {', '.join(missing_phases)}")

    make_targets = _make_targets()
    for index, drill in enumerate(drills):
        if not isinstance(drill, dict):
            errors.append(f"drills[{index}] must be an object")
            continue
        _validate_drill(drill, index, make_targets, errors)

    _validate_follow_up_candidates(payload, errors)
    _validate_sensitive_content(payload, errors)
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for claim in FORBIDDEN_CLAIMS:
        if claim.lower() in rendered.lower():
            errors.append(f"forbidden claim found: {claim}")

    return sorted(set(errors))


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# PH9 Production Hardening Drill Plan",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Phase: `{report['phase']}`",
        f"- Current status: {report['current_status']}",
        f"- Drill count: {report['drill_count']}",
        "",
        "## Scope",
        "",
    ]
    lines.extend(f"- {item}" for item in report["scope"])
    lines.extend(
        [
            "",
            "## Drill Catalog",
            "",
            "| Phase | Drill ID | Name | Safe Auto Run | Manual Run | Evidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for drill in report["drills"]:
        lines.append(
            "| {phase} | `{drill_id}` | {name} | {safe} | {manual} | {evidence} |".format(
                phase=drill["phase"],
                drill_id=drill["drill_id"],
                name=drill["name"],
                safe=str(drill["safe_to_auto_run"]).lower(),
                manual=str(drill["manual_run_required"]).lower(),
                evidence=", ".join(drill["expected_evidence"][:2]),
            )
        )

    lines.extend(
        [
            "",
            "## Automation Boundary",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["automation_boundaries"])
    lines.extend(
        [
            "",
            "## Manual Approval Boundary",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["manual_approval_boundaries"])
    lines.extend(
        [
            "",
            "## Safety Notes",
            "",
            "- PH9 does not run destructive drills by default.",
            "- PH10/PH11 latency work is listed only as follow-up candidates.",
            "- AI-safe context generation does not authorize recovery execution.",
            "- Queue-first architecture must split `ACCEPTED` and `COMPLETED`.",
            f"- Candidate commands note: {report['candidate_commands_note']}",
            "",
            "## Follow-up Candidates",
            "",
        ]
    )
    for candidate in report["follow_up_candidates"]:
        lines.append(
            "- {phase}: {name} ({status})".format(
                phase=candidate["phase"],
                name=candidate["name"],
                status=candidate["status"],
            )
        )
    lines.extend(
        [
            "",
            "## Validation Summary",
            "",
            "- Sensitive data included: false",
            "- Destructive commands allowed: false",
            "- PH10/PH11 latency drills completed in PH9: false",
        ]
    )
    return "\n".join(lines) + "\n"


def list_catalog_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "phase": drill["phase"],
            "drill_id": drill["drill_id"],
            "name": drill["name"],
            "safe_to_auto_run": drill["safe_to_auto_run"],
            "manual_run_required": drill["manual_run_required"],
        }
        for drill in report["drills"]
    ]


def _validate_drill(
    drill: dict[str, Any],
    index: int,
    make_targets: set[str],
    errors: list[str],
) -> None:
    label = drill.get("drill_id", index)
    missing_fields = sorted(REQUIRED_DRILL_FIELDS - set(drill))
    if missing_fields:
        errors.append(f"{label} missing fields: {', '.join(missing_fields)}")

    if drill.get("phase") in {"PH10", "PH11"} or str(label).startswith(
        ("ph10", "ph11")
    ):
        errors.append(f"{label} must be a follow-up candidate, not a completed drill")

    for field in ("linked_docs", "success_criteria", "sensitive_data_policy"):
        value = drill.get(field)
        if not value:
            errors.append(f"{label} {field} must not be empty")

    commands = drill.get("commands", [])
    if not isinstance(commands, list):
        errors.append(f"{label} commands must be a list")
        commands = []
    for command in commands:
        if not isinstance(command, str):
            errors.append(f"{label} command must be a string")
            continue
        _validate_command(label, command, make_targets, errors)

    candidate_commands = drill.get("candidate_commands", [])
    if not isinstance(candidate_commands, list):
        errors.append(f"{label} candidate_commands must be a list")
        candidate_commands = []
    for command in candidate_commands:
        if not isinstance(command, str):
            errors.append(f"{label} candidate command must be a string")
            continue
        _validate_candidate_command(label, command, errors)

    if drill.get("safe_to_auto_run") is True:
        approval_terms = _manual_terms(drill.get("manual_approval_required_for", []))
        if approval_terms:
            errors.append(
                f"{label} safe_to_auto_run cannot include manual approval actions: "
                f"{', '.join(approval_terms)}"
            )


def _validate_command(
    label: str,
    command: str,
    make_targets: set[str],
    errors: list[str],
) -> None:
    for pattern in DESTRUCTIVE_COMMAND_PATTERNS:
        if pattern.search(command):
            errors.append(
                f"{label} destructive/manual command is not allowed: {command}"
            )
    if not command.startswith("make "):
        errors.append(
            f"{label} command must use an existing Makefile target: {command}"
        )
        return
    parts = command.split()
    if len(parts) < 2 or parts[1] not in make_targets:
        errors.append(f"{label} command target does not exist: {command}")


def _validate_candidate_command(
    label: str,
    command: str,
    errors: list[str],
) -> None:
    if not command.startswith("make "):
        errors.append(f"{label} candidate command must use make: {command}")
        return
    parts = command.split()
    target = parts[1] if len(parts) >= 2 else ""
    if target not in CANDIDATE_COMMAND_ALLOW_TARGETS:
        errors.append(f"{label} candidate command is not allowlisted: {command}")


def _validate_follow_up_candidates(payload: dict[str, Any], errors: list[str]) -> None:
    candidates = payload.get("follow_up_candidates", [])
    if not isinstance(candidates, list):
        errors.append("follow_up_candidates must be a list")
        return
    candidate_phases = {
        candidate.get("phase")
        for candidate in candidates
        if isinstance(candidate, dict)
    }
    for phase in ("PH10", "PH11"):
        if phase not in candidate_phases:
            errors.append(f"{phase} must be listed as a follow-up candidate")


def _manual_terms(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    rendered = json.dumps(values, ensure_ascii=False).lower()
    return [term for term in MANUAL_APPROVAL_TERMS if term in rendered]


def _validate_sensitive_content(value: Any, errors: list[str], path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _validate_sensitive_content(nested, errors, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_sensitive_content(nested, errors, f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in SENSITIVE_TEXT_PATTERNS:
            if pattern.search(value):
                errors.append(
                    f"sensitive text pattern found at {path}: {pattern.pattern}"
                )


def _make_targets() -> set[str]:
    if not MAKEFILE.exists():
        return set()
    targets = set()
    pattern = re.compile(r"^([A-Za-z0-9_.-]+):")
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            targets.add(match.group(1))
    return targets


def _drill_catalog() -> list[dict[str, Any]]:
    return [
        {
            "phase": "PH1",
            "drill_id": "ph1-postgres-write-suspend-db-down",
            "name": "PostgreSQL Write Suspend / DB Down Drill",
            "goal": (
                "Confirm that unavailable PostgreSQL write path returns "
                "503 + Retry-After and never reports financial completion."
            ),
            "linked_docs": [
                "docs/36-postgres-failure-and-write-suspend-policy.md",
                "docs/43-ph1-write-suspend-db-down-drill.md",
            ],
            "safe_to_auto_run": False,
            "manual_run_required": True,
            "requires_docker": True,
            "requires_k6": False,
            "requires_database": True,
            "commands": ["make ph1-write-suspend-status"],
            "candidate_commands": ["make ph1-db-down-drill"],
            "expected_evidence": [
                "write suspend mode",
                "Retry-After response",
                "DB readiness failure",
                "post-recovery consistency check",
            ],
            "safety_boundary": (
                "The drill may stop PostgreSQL locally, so PH9 records it as a "
                "manual-run candidate instead of running it by default."
            ),
            "manual_approval_required_for": [
                "write resume after DB recovery",
                "failover promote",
            ],
            "success_criteria": [
                "new financial writes are not successful while DB writes are unavailable",
                "503 + Retry-After is returned",
                "resume is not automatic",
            ],
            "failure_signals": [
                "successful write while write path is unavailable",
                "missing Retry-After",
                "automatic write resume",
            ],
            "sensitive_data_policy": (
                "Plain financial identifiers, request payload content, signing "
                "material, authorization headers, and database URLs are prohibited."
            ),
            "status": "implemented_manual_drill",
        },
        {
            "phase": "PH2",
            "drill_id": "ph2-incident-artifact-sanitized-report",
            "name": "Incident Artifact / Sanitized Report Drill",
            "goal": (
                "Create out-of-band incident evidence during DB failure without "
                "depending on the database."
            ),
            "linked_docs": ["docs/44-ph2-incident-artifact-sanitized-report.md"],
            "safe_to_auto_run": True,
            "manual_run_required": False,
            "requires_docker": False,
            "requires_k6": False,
            "requires_database": False,
            "commands": [
                "make ph2-incident-artifact",
                "make ph2-incident-artifact-validate",
            ],
            "candidate_commands": ["make ph2-db-down-incident-artifact"],
            "expected_evidence": [
                "incident artifact",
                "sanitized report",
                "sensitive scan result",
            ],
            "safety_boundary": "PH2 default command creates sanitized local evidence only.",
            "manual_approval_required_for": [],
            "success_criteria": [
                "artifact exists outside PostgreSQL",
                "sanitized report validates",
                "sensitive scan passes",
            ],
            "failure_signals": [
                "unsafe evidence value",
                "missing manifest",
                "validation error",
            ],
            "sensitive_data_policy": (
                "Plain financial identifiers, retry keys, request payload content, "
                "signing material, authorization headers, and database URLs are prohibited."
            ),
            "status": "implemented_safe_drill",
        },
        {
            "phase": "PH3",
            "drill_id": "ph3-incident-analyzer-mvp",
            "name": "Incident Analyzer MVP Drill",
            "goal": (
                "Classify incident artifacts with deterministic rules and "
                "count-only consistency summaries."
            ),
            "linked_docs": ["docs/45-ph3-incident-analyzer-mvp.md"],
            "safe_to_auto_run": True,
            "manual_run_required": False,
            "requires_docker": False,
            "requires_k6": False,
            "requires_database": False,
            "commands": [
                "make ph3-incident-analyze",
                "make ph3-incident-analyze-validate",
            ],
            "candidate_commands": ["make ph3-db-down-incident-analysis"],
            "expected_evidence": [
                "analyzer output",
                "classification",
                "severity candidate",
                "recommended action candidate",
            ],
            "safety_boundary": "Analyzer output is advisory and never executes recovery.",
            "manual_approval_required_for": [],
            "success_criteria": [
                "classification is deterministic",
                "manual review remains required",
                "no recovery action is executed",
            ],
            "failure_signals": [
                "missing classification",
                "unsafe artifact",
                "automatic recovery language",
            ],
            "sensitive_data_policy": (
                "Only sanitized PH2 evidence and count summaries are allowed."
            ),
            "status": "implemented_safe_drill",
        },
        {
            "phase": "PH4",
            "drill_id": "ph4-recovery-case-quarantine-manual-approval",
            "name": "Recovery Case / Quarantine / Manual Approval Drill",
            "goal": (
                "Record recovery cases and quarantine evidence while keeping "
                "execution blocked until operator approval."
            ),
            "linked_docs": ["docs/46-ph4-recovery-case-quarantine-manual-approval.md"],
            "safe_to_auto_run": False,
            "manual_run_required": True,
            "requires_docker": False,
            "requires_k6": False,
            "requires_database": True,
            "commands": ["make ph4-recovery-cases", "make ph4-quarantines"],
            "candidate_commands": ["make ph4-recovery-case-from-latest"],
            "expected_evidence": [
                "recovery case report",
                "quarantine record",
                "approval boundary",
            ],
            "safety_boundary": "PH4 list commands are safe; case creation needs prepared evidence.",
            "manual_approval_required_for": [
                "recovery execution",
                "quarantine release",
                "ledger correction",
            ],
            "success_criteria": [
                "wrong-state transition is blocked",
                "quarantine is visible as evidence",
                "execution remains approval-gated",
            ],
            "failure_signals": [
                "case execution without approval",
                "quarantine duplicate ambiguity",
                "unsafe identifier exposure",
            ],
            "sensitive_data_policy": (
                "Recovery evidence uses masked or internal identifiers only."
            ),
            "status": "implemented_manual_drill",
        },
        {
            "phase": "PH5",
            "drill_id": "ph5-stale-processing-reconciliation",
            "name": "Stale PROCESSING Reconciliation Drill",
            "goal": (
                "Detect stale processing and count-only reconciliation issues "
                "without automatically completing or failing financial events."
            ),
            "linked_docs": ["docs/47-ph5-stale-processing-reconciliation.md"],
            "safe_to_auto_run": False,
            "manual_run_required": True,
            "requires_docker": False,
            "requires_k6": False,
            "requires_database": True,
            "commands": ["make ph5-reconciliation-validate"],
            "candidate_commands": ["make ph5-reconciliation-run"],
            "expected_evidence": [
                "stale processing count",
                "reconciliation summary",
                "manual action candidate",
            ],
            "safety_boundary": "PH5 proposes recovery cases and does not mutate money state.",
            "manual_approval_required_for": [
                "mark completed decision",
                "mark failed decision",
                "ledger correction",
            ],
            "success_criteria": [
                "stale records are counted after threshold",
                "fresh processing is excluded",
                "manual action candidate is generated only as evidence",
            ],
            "failure_signals": [
                "automatic completion",
                "automatic failure",
                "missing count summary",
            ],
            "sensitive_data_policy": (
                "Reports contain counts and masked recovery references only."
            ),
            "status": "implemented_manual_drill",
        },
        {
            "phase": "PH6",
            "drill_id": "ph6-ai-safe-context-sanitizer",
            "name": "AI-safe Context Sanitizer Drill",
            "goal": (
                "Convert incident, recovery, and reconciliation evidence into "
                "allowlist-based AI-safe context."
            ),
            "linked_docs": ["docs/48-ph6-ai-safe-context-sanitizer.md"],
            "safe_to_auto_run": True,
            "manual_run_required": False,
            "requires_docker": False,
            "requires_k6": False,
            "requires_database": False,
            "commands": ["make ph6-ai-context-demo", "make ph6-ai-context-validate"],
            "candidate_commands": [
                "make ph6-ai-context-sanitize-latest",
                "make ph6-ai-context-recovery",
            ],
            "expected_evidence": [
                "sanitized context JSON",
                "sanitized context Markdown",
                "validate result",
            ],
            "safety_boundary": (
                "PH6 creates context only; it does not call external AI APIs or "
                "execute recovery."
            ),
            "manual_approval_required_for": [],
            "success_criteria": [
                "allowlist keeps safe evidence",
                "redaction summary contains no original unsafe value",
                "validator rejects unsafe input",
            ],
            "failure_signals": [
                "unsafe value remains",
                "redaction summary leaks value",
                "AI execution language appears",
            ],
            "sensitive_data_policy": (
                "Only approved masked values, tokens, hashes, counts, and statuses "
                "are allowed."
            ),
            "status": "implemented_safe_drill",
        },
        {
            "phase": "PH7",
            "drill_id": "ph7-partner-hmac-rotation",
            "name": "Partner HMAC Rotation Drill",
            "goal": (
                "Verify current, previous, revoked, disabled, and next dry-run "
                "HMAC cases without exposing signing material."
            ),
            "linked_docs": ["docs/49-ph7-partner-secret-rotation-hmac-hardening.md"],
            "safe_to_auto_run": True,
            "manual_run_required": False,
            "requires_docker": False,
            "requires_k6": False,
            "requires_database": False,
            "commands": [
                "make ph7-hmac-rotation-demo",
                "make ph7-hmac-rotation-validate",
            ],
            "candidate_commands": ["make ph7-hmac-rotation-smoke"],
            "expected_evidence": [
                "HMAC rotation report",
                "next dry-run rejection on write API",
                "validate result",
            ],
            "safety_boundary": (
                "The drill verifies rotation cases only. Final key retirement "
                "remains an approval decision."
            ),
            "manual_approval_required_for": [],
            "success_criteria": [
                "current and bounded previous cases pass",
                "revoked and disabled cases fail",
                "next staged key cannot write",
            ],
            "failure_signals": [
                "staged key accepted on write path",
                "unbounded previous key",
                "signing material exposure",
            ],
            "sensitive_data_policy": (
                "Evidence may include key status and hashes, but never signing "
                "material or request payload content."
            ),
            "status": "implemented_safe_drill",
        },
        {
            "phase": "PH8",
            "drill_id": "ph8-postgres-ha-queue-decision-evidence",
            "name": "PostgreSQL HA / Durable Queue Decision Evidence",
            "goal": (
                "Explain why direct PostgreSQL transaction plus fail-closed remains "
                "current behavior and why queue-first needs ACCEPTED/COMPLETED split."
            ),
            "linked_docs": [
                "docs/40-postgres-ha-and-queue-tradeoff-adr.md",
                "docs/50-ph8-postgres-ha-queue-decision-evidence.md",
            ],
            "safe_to_auto_run": True,
            "manual_run_required": False,
            "requires_docker": False,
            "requires_k6": False,
            "requires_database": False,
            "commands": [
                "make ph8-ha-queue-decision-demo",
                "make ph8-ha-queue-decision-validate",
            ],
            "candidate_commands": [],
            "expected_evidence": [
                "decision matrix report",
                "validator result",
                "API contract boundary",
            ],
            "safety_boundary": (
                "PH8 creates architecture evidence only; it does not provision HA "
                "or queue middleware."
            ),
            "manual_approval_required_for": [],
            "success_criteria": [
                "direct PostgreSQL remains current decision",
                "queue-first splits ACCEPTED and COMPLETED",
                "HA still requires consistency gate and write resume approval",
            ],
            "failure_signals": [
                "enqueue described as ledger completion",
                "HA described as replacing consistency gate",
                "score treated as benchmark",
            ],
            "sensitive_data_policy": "Architecture evidence contains no runtime data.",
            "status": "implemented_safe_drill",
        },
    ]


if __name__ == "__main__":
    raise SystemExit(main())
