#!/usr/bin/env python3
"""Generate and validate PH11 latency drill evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import ph10_latency_attribution  # noqa: E402

MAKEFILE = ROOT_DIR / "Makefile"
DEFAULT_REPORT_DIR = ROOT_DIR / "reports/latency/ph11-drill-evidence"
SAMPLE_REPORT = DEFAULT_REPORT_DIR / "sample-latency-drill-plan.json"
SAMPLE_PH10_INPUT = DEFAULT_REPORT_DIR / "sample-ph10-input-evidence.json"
SAMPLE_PH10_REPORT = DEFAULT_REPORT_DIR / "sample-ph10-attribution-report.json"
FIXED_GENERATED_AT = "2026-07-08T00:00:00+00:00"

REQUIRED_DRILLS = {"LAT-001", "LAT-002", "LAT-003", "LAT-004", "LAT-005", "LAT-006"}
REQUIRED_TOP_LEVEL_FIELDS = {
    "run_id",
    "generated_at",
    "phase",
    "scope",
    "current_status",
    "drill_count",
    "drills",
    "safe_demo_scenarios",
    "manual_drill_candidates",
    "ph10_analyzer_link",
    "consistency_policy",
    "sensitive_data_policy",
    "metric_label_policy",
    "validation_summary",
    "follow_up_candidates",
}
REQUIRED_DRILL_FIELDS = {
    "drill_id",
    "name",
    "goal",
    "scenario_type",
    "safe_to_auto_run",
    "manual_run_required",
    "requires_docker",
    "requires_k6",
    "requires_database",
    "requires_redis",
    "requires_nginx",
    "requires_mock_partner",
    "commands",
    "manual_commands",
    "candidate_commands",
    "expected_k6_evidence",
    "expected_server_evidence",
    "expected_consistency_evidence",
    "expected_ph10_classification",
    "actual_ph10_classification",
    "ph10_input_scenario",
    "success_criteria",
    "failure_signals",
    "safety_boundary",
    "manual_approval_required_for",
    "linked_docs",
    "status",
}
SCENARIOS = {
    "baseline",
    "db_pool_pressure",
    "db_lock_contention",
    "redis_degraded",
    "redis_unavailable",
    "external_endpoint_slow",
    "app_http_client_path_issue",
    "nginx_edge_latency",
    "insufficient_evidence",
}
FORBIDDEN_METRIC_LABELS = {
    "account_id",
    "event_id",
    "idempotency_key",
    "trace_id",
    "request_id",
    "raw_url",
    "customer_id",
    "customer_identifier",
    "account_no",
    "external_event_id",
}
FORBIDDEN_KEYS = {
    "account_no",
    "raw_account_no",
    "idempotency_key",
    "raw_idempotency_key",
    "authorization",
    "authorization_header",
    "signature",
    "x_signature",
    "client_secret",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "raw_request_body",
    "database_url",
    "raw_url",
}
SENSITIVE_TEXT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"Authorization\s*[:=]\s*\S+",
        r"Bearer\s+\S+",
        r"Basic\s+\S+",
        r"X-Signature\s*[:=]\s*\S+",
        r"Idempotency-Key\s*[:=]\s*\S+",
        r"\baccount_no\b",
        r"\braw_account_no\b",
        r"\bidempotency_key\b",
        r"\braw_idempotency_key\b",
        r"\bauthorization\b",
        r"\bsignature\b",
        r"\bclient_secret\b",
        r"\baccess_token\b",
        r"\brefresh_token\b",
        r"\bpassword\b",
        r"\bsecret\b",
        r"\braw_request_body\b",
        r"\bdatabase_url\b",
        r"\braw_url\b",
        r"https?://[^\s)]+",
        r"postgresql://\S+",
    )
]
DESTRUCTIVE_COMMAND_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"docker\s+compose\s+(down|stop|pause|rm|kill)",
        r"\brm\s+-",
        r"\bdelete\b",
        r"\btruncate\b",
        r"\bdrop\b",
        r"\bstop\b.*redis",
        r"\bstop\b.*postgres",
        r"db-lock",
        r"db-pool",
        r"redis-down",
        r"redis-delay",
        r"toxiproxy",
        r"netem",
        r"failover",
        r"promote",
        r"write-resume",
        r"ledger.*compensation",
        r"partner.*approval",
    )
]
FORBIDDEN_CLAIMS = [
    "k6 proves postgres root cause",
    "k6 alone proves postgres",
    "k6 alone proves redis",
    "k6 alone proves external",
    "production fault injection is automatically executed",
    "PH11 automatically runs production fault injection",
    "AI confirmed the root cause",
    "AI automatically fixes latency",
    "AI가 latency 원인을 확정한다",
    "AI가 복구를 자동 실행한다",
]
MANUAL_APPROVAL_TERMS = [
    "db lock",
    "db pool",
    "redis down",
    "redis delay",
    "network delay",
    "mock partner",
    "toxiproxy",
    "netem",
    "write resume",
    "failover promote",
    "ledger compensation",
    "partner secret rotation approval",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    demo_parser.add_argument(
        "--scenario", default="db_lock_contention", choices=sorted(SCENARIOS)
    )

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, default=SAMPLE_REPORT)

    subparsers.add_parser("list")

    generate_parser = subparsers.add_parser("generate-ph10-input")
    generate_parser.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    generate_parser.add_argument("--output", type=Path, default=SAMPLE_PH10_INPUT)

    args = parser.parse_args()
    try:
        result = _handle(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"PH11 latency drill error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "demo":
        report = build_report()
        ph10_input = generate_ph10_input(args.scenario)
        ph10_report = ph10_latency_attribution.analyze_evidence(ph10_input)
        _write_outputs(args.output_dir, report, ph10_input, ph10_report)
        validation_errors = validate_report_payload(report)
        ph10_errors = ph10_latency_attribution.validate_report_payload(ph10_report)
        if validation_errors or ph10_errors:
            raise ValueError(
                json.dumps(
                    {
                        "ph11_validation_errors": validation_errors,
                        "ph10_validation_errors": ph10_errors,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        return {
            "output": str(args.output_dir / "sample-latency-drill-plan.json"),
            "report": str(args.output_dir / "sample-latency-drill-plan.md"),
            "ph10_input": str(args.output_dir / "sample-ph10-input-evidence.json"),
            "ph10_report": str(args.output_dir / "sample-ph10-attribution-report.json"),
            "ph10_report_markdown": str(
                args.output_dir / "sample-ph10-attribution-report.md"
            ),
            "drill_count": report["drill_count"],
            "sample_ph10_classification": ph10_report["classification"],
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

    if args.command == "generate-ph10-input":
        evidence = generate_ph10_input(args.scenario)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        report = ph10_latency_attribution.analyze_evidence(evidence)
        return {
            "output": str(args.output),
            "scenario": args.scenario,
            "ph10_classification": report["classification"],
        }

    raise SystemExit(f"unknown command: {args.command}")


def build_report() -> dict[str, Any]:
    drills = _drill_catalog()
    return {
        "run_id": "ph11-latency-drill-evidence-runner-sample",
        "generated_at": FIXED_GENERATED_AT,
        "phase": "PH11 Latency Drill Test Plan & Safe Evidence Runner",
        "scope": [
            "LAT-001~LAT-006 latency drill catalog",
            "safe sample evidence generation",
            "PH10 analyzer input generation and expected/actual comparison",
            "consistency evidence boundary validation",
            "manual/opt-in boundary for destructive or environment-changing drills",
        ],
        "current_status": (
            "Implemented as a safe catalog, synthetic evidence generator, PH10 "
            "analyzer integration, and validator. Default demo does not execute "
            "DB lock holders, Redis down/delay, Nginx delay, mock partner, "
            "Toxiproxy, netem, or production fault injection."
        ),
        "drill_count": len(drills),
        "drills": drills,
        "safe_demo_scenarios": [
            "baseline",
            "db_pool_pressure",
            "db_lock_contention",
            "redis_degraded",
            "redis_unavailable",
            "external_endpoint_slow",
            "app_http_client_path_issue",
            "nginx_edge_latency",
            "insufficient_evidence",
        ],
        "manual_drill_candidates": [
            "DB pool pressure with altered pool size",
            "controlled DB lock holder",
            "Redis down or Redis delay with network tooling",
            "mock partner slow endpoint",
            "Nginx edge/client network latency profile",
        ],
        "ph10_analyzer_link": {
            "script": "scripts/ph10_latency_attribution.py",
            "input_contract": "reports/latency/ph11-drill-evidence/sample-ph10-input-evidence.json",
            "expected_actual_policy": (
                "Each drill records expected_ph10_classification and validates it "
                "against actual_ph10_classification from the PH10 analyzer."
            ),
        },
        "consistency_policy": {
            "duplicate_ledger_count": 0,
            "duplicate_external_event_count": 0,
            "reconciliation_failure_count": 0,
            "invalid_state_transition_count": 0,
            "violation_priority": (
                "Any non-zero consistency counter is treated as a consistency "
                "incident candidate before latency classification."
            ),
        },
        "sensitive_data_policy": {
            "plain_financial_identifiers": "prohibited",
            "plain_retry_identifiers": "prohibited",
            "request_payload_contents": "prohibited",
            "auth_material": "prohibited",
            "signing_material": "prohibited",
            "endpoint_values": "prohibited",
        },
        "metric_label_policy": {
            "allowed": [
                "route_group",
                "endpoint_group",
                "partner_alias",
                "method",
                "status_code_family",
                "result",
                "phase",
                "operation",
            ],
            "forbidden": sorted(FORBIDDEN_METRIC_LABELS),
        },
        "validation_summary": {
            "required_drills": sorted(REQUIRED_DRILLS),
            "safe_demo_runs_fault_injection": False,
            "ph10_expected_actual_mismatch_allowed": False,
            "sensitive_data_included": False,
            "k6_only_root_cause_claim_allowed": False,
            "consistency_violation_downgraded_to_latency": False,
        },
        "follow_up_candidates": [
            "Toxiproxy or netem latency profiles",
            "OpenTelemetry full tracing",
            "Grafana latency attribution dashboard",
            "mock partner service compose profile",
            "controlled DB lock holder script",
        ],
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

    drill_ids = {drill.get("drill_id") for drill in drills if isinstance(drill, dict)}
    missing_drills = sorted(REQUIRED_DRILLS - drill_ids)
    if missing_drills:
        errors.append(f"missing required latency drills: {', '.join(missing_drills)}")

    make_targets = _make_targets()
    for index, drill in enumerate(drills):
        if not isinstance(drill, dict):
            errors.append(f"drills[{index}] must be an object")
            continue
        _validate_drill(drill, index, make_targets, errors)

    _validate_consistency_policy(payload, errors)
    _validate_sensitive_content(payload, errors)
    _validate_metric_labels(payload, errors)
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for claim in FORBIDDEN_CLAIMS:
        if claim.lower() in rendered.lower():
            errors.append(f"forbidden claim found: {claim}")
    return sorted(set(errors))


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# PH11 Latency Drill Evidence Runner",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Phase: `{report['phase']}`",
        f"- Current status: {report['current_status']}",
        f"- Drill count: `{report['drill_count']}`",
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
            "| Drill | Name | Safe Demo | Manual Required | Expected PH10 | Actual PH10 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for drill in report["drills"]:
        lines.append(
            "| `{drill_id}` | {name} | {safe} | {manual} | `{expected}` | `{actual}` |".format(
                drill_id=drill["drill_id"],
                name=drill["name"],
                safe=str(drill["safe_to_auto_run"]).lower(),
                manual=str(drill["manual_run_required"]).lower(),
                expected=drill["expected_ph10_classification"],
                actual=drill["actual_ph10_classification"],
            )
        )

    lines.extend(["", "## PH10 Analyzer Link", ""])
    link = report["ph10_analyzer_link"]
    lines.append(f"- Script: `{link['script']}`")
    lines.append(f"- Input contract: `{link['input_contract']}`")
    lines.append(f"- Policy: {link['expected_actual_policy']}")

    lines.extend(["", "## Safe Demo / Manual Boundary", ""])
    lines.append("- Safe demo scenarios:")
    lines.extend(f"  - `{item}`" for item in report["safe_demo_scenarios"])
    lines.append("- Manual drill candidates:")
    lines.extend(f"  - {item}" for item in report["manual_drill_candidates"])

    lines.extend(["", "## Consistency Policy", ""])
    lines.append(f"- {report['consistency_policy']['violation_priority']}")
    lines.append("- Required sample consistency counters stay at zero.")

    lines.extend(["", "## Sensitive Data Policy", ""])
    lines.append(
        "- Plain financial identifiers, retry identifiers, payload contents, auth material, signing material, and endpoint values are prohibited."
    )
    lines.append(
        "- Metric labels are limited to bounded route, endpoint, partner, method, status, result, phase, and operation fields."
    )

    lines.extend(["", "## Follow-up Candidates", ""])
    lines.extend(f"- {item}" for item in report["follow_up_candidates"])
    return "\n".join(lines) + "\n"


def list_catalog_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "drill_id": drill["drill_id"],
            "name": drill["name"],
            "safe_to_auto_run": drill["safe_to_auto_run"],
            "manual_run_required": drill["manual_run_required"],
            "expected_ph10_classification": drill["expected_ph10_classification"],
        }
        for drill in report["drills"]
    ]


def generate_ph10_input(scenario: str) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown PH11 latency scenario: {scenario}")

    baseline = {
        "k6_p95_ms": 180,
        "k6_p99_ms": 420,
        "server_handler_p95_ms": 120,
        "server_handler_p99_ms": 300,
    }
    consistency = {
        "duplicate_ledger_count": 0,
        "duplicate_external_event_count": 0,
        "reconciliation_failure_count": 0,
        "invalid_state_transition_count": 0,
    }
    evidence = {
        "run_id": f"ph11-{scenario}-sample",
        "generated_at": FIXED_GENERATED_AT,
        "scenario": scenario,
        "route_group": "financial_event_write",
        "method": "POST",
        "status_code_family": "2xx",
        "baseline": baseline,
        "observed": {},
        "consistency": consistency,
    }
    observed_by_scenario = {
        "baseline": {
            "k6_p95_ms": 190,
            "k6_p99_ms": 430,
            "nginx_request_p95_ms": 180,
            "nginx_upstream_p95_ms": 160,
            "fastapi_handler_p95_ms": 130,
            "postgres_phase_p95_ms": 70,
            "redis_phase_p95_ms": 20,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0,
        },
        "db_pool_pressure": {
            "k6_p95_ms": 700,
            "k6_p99_ms": 1500,
            "nginx_request_p95_ms": 680,
            "nginx_upstream_p95_ms": 640,
            "fastapi_handler_p95_ms": 600,
            "db_pool_wait_p95_ms": 260,
            "postgres_phase_p95_ms": 210,
            "redis_phase_p95_ms": 20,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0.01,
        },
        "db_lock_contention": {
            "k6_p95_ms": 760,
            "k6_p99_ms": 1800,
            "nginx_request_p95_ms": 730,
            "nginx_upstream_p95_ms": 700,
            "fastapi_handler_p95_ms": 650,
            "db_lock_wait_p95_ms": 300,
            "postgres_phase_p95_ms": 260,
            "redis_phase_p95_ms": 20,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0.01,
        },
        "redis_degraded": {
            "k6_p95_ms": 650,
            "k6_p99_ms": 1400,
            "nginx_request_p95_ms": 630,
            "nginx_upstream_p95_ms": 600,
            "fastapi_handler_p95_ms": 560,
            "postgres_phase_p95_ms": 120,
            "redis_phase_p95_ms": 260,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0.01,
        },
        "redis_unavailable": {
            "k6_p95_ms": 540,
            "k6_p99_ms": 1100,
            "nginx_request_p95_ms": 520,
            "nginx_upstream_p95_ms": 500,
            "fastapi_handler_p95_ms": 460,
            "postgres_phase_p95_ms": 170,
            "redis_phase_p95_ms": 0,
            "redis_unavailable": True,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0.02,
        },
        "external_endpoint_slow": {
            "k6_p95_ms": 900,
            "k6_p99_ms": 1900,
            "nginx_request_p95_ms": 860,
            "nginx_upstream_p95_ms": 830,
            "fastapi_handler_p95_ms": 800,
            "postgres_phase_p95_ms": 100,
            "redis_phase_p95_ms": 30,
            "outbound_http_p95_ms": 520,
            "blackbox_probe_p95_ms": 900,
            "error_rate": 0.02,
        },
        "app_http_client_path_issue": {
            "k6_p95_ms": 780,
            "k6_p99_ms": 1600,
            "nginx_request_p95_ms": 730,
            "nginx_upstream_p95_ms": 700,
            "fastapi_handler_p95_ms": 680,
            "postgres_phase_p95_ms": 90,
            "redis_phase_p95_ms": 30,
            "outbound_http_p95_ms": 500,
            "blackbox_probe_p95_ms": 180,
            "error_rate": 0.01,
        },
        "nginx_edge_latency": {
            "k6_p95_ms": 900,
            "k6_p99_ms": 1600,
            "nginx_request_p95_ms": 850,
            "nginx_upstream_p95_ms": 180,
            "fastapi_handler_p95_ms": 140,
            "postgres_phase_p95_ms": 70,
            "redis_phase_p95_ms": 20,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0,
        },
    }
    if scenario == "insufficient_evidence":
        return {
            "run_id": "ph11-insufficient-evidence-sample",
            "generated_at": FIXED_GENERATED_AT,
            "scenario": scenario,
            "baseline": baseline,
        }
    evidence["observed"] = observed_by_scenario[scenario]
    return evidence


def _write_outputs(
    output_dir: Path,
    report: dict[str, Any],
    ph10_input: dict[str, Any],
    ph10_report: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "sample-latency-drill-plan.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_path.with_suffix(".md").write_text(
        render_markdown_report(report), encoding="utf-8"
    )
    (output_dir / "sample-ph10-input-evidence.json").write_text(
        json.dumps(ph10_input, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    ph10_report_path = output_dir / "sample-ph10-attribution-report.json"
    ph10_report_path.write_text(
        json.dumps(ph10_report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    ph10_report_path.with_suffix(".md").write_text(
        ph10_latency_attribution.render_markdown_report(ph10_report),
        encoding="utf-8",
    )


def _validate_drill(
    drill: dict[str, Any],
    index: int,
    make_targets: set[str],
    errors: list[str],
) -> None:
    label = str(drill.get("drill_id", index))
    missing_fields = sorted(REQUIRED_DRILL_FIELDS - set(drill))
    if missing_fields:
        errors.append(f"{label} missing fields: {', '.join(missing_fields)}")

    expected = drill.get("expected_ph10_classification")
    actual = drill.get("actual_ph10_classification")
    if expected not in ph10_latency_attribution.CLASSIFICATIONS:
        errors.append(f"{label} expected PH10 classification is invalid: {expected}")
    if actual not in ph10_latency_attribution.CLASSIFICATIONS:
        errors.append(f"{label} actual PH10 classification is invalid: {actual}")
    if expected != actual:
        errors.append(
            f"{label} PH10 classification mismatch: expected {expected}, actual {actual}"
        )

    commands = drill.get("commands", [])
    if not isinstance(commands, list):
        errors.append(f"{label} commands must be a list")
        commands = []
    for command in commands:
        if not isinstance(command, str):
            errors.append(f"{label} command must be a string")
            continue
        _validate_default_command(label, command, make_targets, errors)

    for field in ("manual_commands", "candidate_commands"):
        values = drill.get(field, [])
        if not isinstance(values, list):
            errors.append(f"{label} {field} must be a list")
            values = []
        for command in values:
            if not isinstance(command, str):
                errors.append(f"{label} {field} item must be a string")
                continue
            _validate_manual_or_candidate_command(label, field, command, errors)

    if drill.get("safe_to_auto_run") is True:
        rendered = json.dumps(
            {
                "commands": drill.get("commands", []),
                "safety_boundary": drill.get("safety_boundary", ""),
            },
            ensure_ascii=False,
        )
        for pattern in DESTRUCTIVE_COMMAND_PATTERNS:
            if pattern.search(rendered):
                errors.append(
                    f"{label} safe auto-run drill contains manual action terms"
                )

    if drill.get("manual_run_required") is True and not drill.get(
        "manual_approval_required_for"
    ):
        errors.append(f"{label} manual drill must document manual approval boundary")

    if drill.get("manual_run_required") is True and not drill.get("safety_boundary"):
        errors.append(f"{label} manual drill must document safety_boundary")

    for field in (
        "expected_k6_evidence",
        "expected_server_evidence",
        "expected_consistency_evidence",
        "success_criteria",
        "failure_signals",
        "linked_docs",
    ):
        if not drill.get(field):
            errors.append(f"{label} {field} must not be empty")

    _validate_k6_root_cause_language(label, drill, errors)


def _validate_default_command(
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
        errors.append(f"{label} command must use make: {command}")
        return
    parts = command.split()
    if len(parts) < 2 or parts[1] not in make_targets:
        errors.append(f"{label} command target does not exist: {command}")


def _validate_manual_or_candidate_command(
    label: str,
    field: str,
    command: str,
    errors: list[str],
) -> None:
    if not command.startswith("make "):
        errors.append(f"{label} {field} must use make: {command}")
        return
    target = command.split()[1] if len(command.split()) >= 2 else ""
    if not (
        "manual" in target
        or "candidate" in target
        or "demo" in target
        or target in {"k6-normal", "k6-peak", "k6-redis-down"}
    ):
        errors.append(f"{label} {field} must be marked manual/candidate: {command}")


def _validate_k6_root_cause_language(
    label: str, drill: dict[str, Any], errors: list[str]
) -> None:
    rendered = json.dumps(drill, ensure_ascii=False).lower()
    if "k6" in rendered and (
        "k6 proves" in rendered
        or "k6 alone proves" in rendered
        or "k6 root cause" in rendered
    ):
        errors.append(f"{label} k6-only root cause claim is not allowed")


def _validate_consistency_policy(payload: dict[str, Any], errors: list[str]) -> None:
    policy = payload.get("consistency_policy", {})
    if not isinstance(policy, dict):
        errors.append("consistency_policy must be an object")
        return
    counters = [
        "duplicate_ledger_count",
        "duplicate_external_event_count",
        "reconciliation_failure_count",
        "invalid_state_transition_count",
    ]
    if any(policy.get(counter) not in (0, "0") for counter in counters):
        if "consistency" not in str(policy.get("violation_priority", "")).lower():
            errors.append("consistency violation cannot be reported as clean latency")


def _validate_sensitive_content(value: Any, errors: list[str], path: str = "$") -> None:
    if path.startswith("$.sensitive_data_policy") or path.startswith(
        "$.metric_label_policy"
    ):
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            key_lower = str(key).lower()
            if _matching_forbidden_key(key_lower) is not None:
                errors.append(f"sensitive key found at {path}.{key}")
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


def _validate_metric_labels(value: Any, errors: list[str], path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_lower = str(key).lower()
            if key_lower in {
                "metric_labels",
                "labels",
                "label_candidates",
                "prometheus_labels",
            }:
                labels = _extract_label_names(nested)
                forbidden = sorted(labels & FORBIDDEN_METRIC_LABELS)
                if forbidden:
                    errors.append(
                        f"forbidden metric label at {path}.{key}: {', '.join(forbidden)}"
                    )
            _validate_metric_labels(nested, errors, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_metric_labels(nested, errors, f"{path}[{index}]")


def _extract_label_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key).lower() for key in value}
    if isinstance(value, list):
        return {str(item).lower() for item in value}
    if isinstance(value, str):
        return {value.lower()}
    return set()


def _matching_forbidden_key(key: str) -> Optional[str]:
    for forbidden in FORBIDDEN_KEYS:
        if key == forbidden or forbidden in key:
            return forbidden
    return None


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
    definitions = [
        {
            "drill_id": "LAT-001",
            "name": "Baseline Latency Drill",
            "goal": "Create normal/peak local latency baselines and keep consistency counters clean.",
            "scenario_type": "safe_sample_baseline",
            "safe_to_auto_run": True,
            "manual_run_required": False,
            "requires_docker": False,
            "requires_k6": False,
            "requires_database": False,
            "requires_redis": False,
            "requires_nginx": False,
            "requires_mock_partner": False,
            "commands": [
                "make ph11-latency-drill-generate-ph10-input",
                "make ph11-latency-drill-validate",
            ],
            "manual_commands": ["make k6-normal", "make k6-peak"],
            "candidate_commands": ["make ph11-latency-baseline-demo"],
            "expected_k6_evidence": ["baseline p95/p99", "error rate"],
            "expected_server_evidence": ["handler p95 near baseline"],
            "expected_consistency_evidence": [
                "duplicate ledger count 0",
                "duplicate external event count 0",
                "reconciliation failure count 0",
            ],
            "expected_ph10_classification": "baseline_normal_latency",
            "ph10_input_scenario": "baseline",
            "success_criteria": [
                "PH10 returns baseline_normal_latency",
                "local baseline is not presented as production SLO",
            ],
            "failure_signals": [
                "baseline p95/p99 is missing",
                "consistency counter is non-zero",
            ],
            "safety_boundary": "Default command only generates sample evidence.",
            "manual_approval_required_for": [],
            "linked_docs": ["docs/42-latency-drill-test-plan.md"],
            "status": "implemented_safe_evidence",
        },
        {
            "drill_id": "LAT-002",
            "name": "PostgreSQL Pool Pressure Drill",
            "goal": "Represent DB pool wait or pressure evidence without changing pool size by default.",
            "scenario_type": "manual_db_pool_candidate",
            "safe_to_auto_run": False,
            "manual_run_required": True,
            "requires_docker": True,
            "requires_k6": True,
            "requires_database": True,
            "requires_redis": False,
            "requires_nginx": False,
            "requires_mock_partner": False,
            "commands": ["make ph11-latency-drill-generate-ph10-input"],
            "manual_commands": ["make ph11-latency-db-pool-manual"],
            "candidate_commands": [],
            "expected_k6_evidence": ["p95/p99 increase"],
            "expected_server_evidence": [
                "DB pool wait p95",
                "FastAPI handler p95 increase",
            ],
            "expected_consistency_evidence": ["duplicate ledger count 0"],
            "expected_ph10_classification": "internal_postgres_pool_pressure",
            "ph10_input_scenario": "db_pool_pressure",
            "success_criteria": [
                "PH10 returns internal_postgres_pool_pressure",
                "pool pressure remains candidate evidence without supporting DB timing",
            ],
            "failure_signals": [
                "p99 alone is used as DB proof",
                "manual pool change is in default command",
            ],
            "safety_boundary": "Changing pool size is manual/opt-in only.",
            "manual_approval_required_for": ["DB pool pressure drill"],
            "linked_docs": ["docs/42-latency-drill-test-plan.md"],
            "status": "implemented_safe_evidence_manual_drill_candidate",
        },
        {
            "drill_id": "LAT-003",
            "name": "PostgreSQL Lock Contention Drill",
            "goal": "Represent row lock contention evidence without running a lock holder by default.",
            "scenario_type": "manual_db_lock_candidate",
            "safe_to_auto_run": False,
            "manual_run_required": True,
            "requires_docker": True,
            "requires_k6": True,
            "requires_database": True,
            "requires_redis": False,
            "requires_nginx": False,
            "requires_mock_partner": False,
            "commands": ["make ph11-latency-drill-demo"],
            "manual_commands": ["make ph11-latency-db-lock-manual"],
            "candidate_commands": [],
            "expected_k6_evidence": ["p95/p99 increase", "timeout candidate"],
            "expected_server_evidence": [
                "DB lock wait p95",
                "FastAPI handler p95 increase",
            ],
            "expected_consistency_evidence": ["invalid state transition count 0"],
            "expected_ph10_classification": "internal_postgres_lock_contention",
            "ph10_input_scenario": "db_lock_contention",
            "success_criteria": [
                "PH10 returns internal_postgres_lock_contention",
                "lock holder remains manual with timeout and cleanup notes",
            ],
            "failure_signals": [
                "lock holder runs in default demo",
                "write path can hang without timeout",
            ],
            "safety_boundary": "DB lock holder is manual/opt-in and must have timeout cleanup.",
            "manual_approval_required_for": ["DB lock holder"],
            "linked_docs": ["docs/42-latency-drill-test-plan.md"],
            "status": "implemented_safe_evidence_manual_drill_candidate",
        },
        {
            "drill_id": "LAT-004",
            "name": "Redis Delay / Redis Down Drill",
            "goal": "Separate Redis slow evidence from Redis unavailable fallback evidence.",
            "scenario_type": "manual_redis_candidate",
            "safe_to_auto_run": False,
            "manual_run_required": True,
            "requires_docker": True,
            "requires_k6": True,
            "requires_database": True,
            "requires_redis": True,
            "requires_nginx": False,
            "requires_mock_partner": False,
            "commands": ["make ph11-latency-drill-generate-ph10-input"],
            "manual_commands": ["make ph11-latency-redis-down-manual"],
            "candidate_commands": ["make ph11-latency-redis-delay-candidate"],
            "expected_k6_evidence": [
                "p95/p99 increase",
                "fallback availability candidate",
            ],
            "expected_server_evidence": ["Redis phase p95", "Redis unavailable flag"],
            "expected_consistency_evidence": ["duplicate external event count 0"],
            "expected_ph10_classification": "redis_degraded_latency",
            "ph10_input_scenario": "redis_degraded",
            "success_criteria": [
                "PH10 returns redis_degraded_latency for slow evidence",
                "redis_unavailable scenario can generate redis_unavailable_fallback",
            ],
            "failure_signals": ["test-only Redis delay is added to production code"],
            "safety_boundary": "Redis down/delay is manual or candidate only.",
            "manual_approval_required_for": ["Redis down", "Redis delay"],
            "linked_docs": ["docs/42-latency-drill-test-plan.md"],
            "status": "implemented_safe_evidence_manual_drill_candidate",
        },
        {
            "drill_id": "LAT-005",
            "name": "External Dependency Slow Response Drill",
            "goal": "Separate provider endpoint slowness from local HTTP client path problems.",
            "scenario_type": "manual_external_candidate",
            "safe_to_auto_run": False,
            "manual_run_required": True,
            "requires_docker": True,
            "requires_k6": True,
            "requires_database": False,
            "requires_redis": False,
            "requires_nginx": False,
            "requires_mock_partner": True,
            "commands": ["make ph11-latency-drill-generate-ph10-input"],
            "manual_commands": ["make ph11-latency-external-slow-manual"],
            "candidate_commands": [],
            "expected_k6_evidence": ["p95/p99 increase", "timeout candidate"],
            "expected_server_evidence": ["outbound HTTP p95", "blackbox probe p95"],
            "expected_consistency_evidence": ["reconciliation failure count 0"],
            "expected_ph10_classification": "external_endpoint_slow",
            "ph10_input_scenario": "external_endpoint_slow",
            "success_criteria": [
                "PH10 returns external_endpoint_slow",
                "mock evidence is not claimed as full provider outage proof",
            ],
            "failure_signals": ["mock partner is described as complete provider proof"],
            "safety_boundary": "Mock partner and slow endpoint behavior are manual/follow-up candidates.",
            "manual_approval_required_for": ["mock partner"],
            "linked_docs": ["docs/42-latency-drill-test-plan.md"],
            "status": "implemented_safe_evidence_manual_drill_candidate",
        },
        {
            "drill_id": "LAT-006",
            "name": "Nginx Edge / Client Network Latency Drill",
            "goal": "Identify high Nginx request time with normal upstream/FastAPI handler evidence.",
            "scenario_type": "manual_nginx_edge_candidate",
            "safe_to_auto_run": False,
            "manual_run_required": True,
            "requires_docker": True,
            "requires_k6": True,
            "requires_database": False,
            "requires_redis": False,
            "requires_nginx": True,
            "requires_mock_partner": False,
            "commands": ["make ph11-latency-drill-generate-ph10-input"],
            "manual_commands": [],
            "candidate_commands": ["make ph11-latency-nginx-edge-candidate"],
            "expected_k6_evidence": ["client-side p95/p99 increase"],
            "expected_server_evidence": [
                "Nginx request time high",
                "upstream and handler normal",
            ],
            "expected_consistency_evidence": ["duplicate ledger count 0"],
            "expected_ph10_classification": "edge_or_client_network_latency",
            "ph10_input_scenario": "nginx_edge_latency",
            "success_criteria": [
                "PH10 returns edge_or_client_network_latency",
                "request_id remains log correlation only, not metric label",
            ],
            "failure_signals": [
                "request_id is used as metric label",
                "network delay runs by default",
            ],
            "safety_boundary": "Nginx edge/network delay remains candidate/manual only.",
            "manual_approval_required_for": ["network delay"],
            "linked_docs": ["docs/42-latency-drill-test-plan.md"],
            "status": "implemented_safe_evidence_manual_drill_candidate",
        },
    ]

    drills = []
    for item in definitions:
        scenario = item["ph10_input_scenario"]
        actual = ph10_latency_attribution.analyze_evidence(
            generate_ph10_input(scenario)
        )["classification"]
        drills.append({**item, "actual_ph10_classification": actual})
    return drills


if __name__ == "__main__":
    raise SystemExit(main())
