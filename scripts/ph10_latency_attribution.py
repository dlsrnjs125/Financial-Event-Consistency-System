#!/usr/bin/env python3
"""Generate and validate PH10 latency attribution evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT_DIR / "reports/latency/ph10-attribution"
SAMPLE_INPUT = DEFAULT_REPORT_DIR / "sample-input-evidence.json"
SAMPLE_REPORT = DEFAULT_REPORT_DIR / "sample-latency-attribution-report.json"
FIXED_GENERATED_AT = "2026-07-07T00:00:00+00:00"

CLASSIFICATIONS = {
    "baseline_normal_latency",
    "internal_application_latency",
    "internal_postgres_latency",
    "internal_postgres_pool_pressure",
    "internal_postgres_lock_contention",
    "redis_degraded_latency",
    "redis_unavailable_fallback",
    "external_dependency_latency",
    "external_endpoint_slow",
    "app_http_client_path_issue",
    "edge_or_client_network_latency",
    "partner_specific_latency",
    "route_specific_latency_candidate",
    "insufficient_evidence",
}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}
CONSISTENCY_STATUSES = {"CLEAN", "VIOLATION_DETECTED", "UNKNOWN"}
REQUIRED_REPORT_FIELDS = {
    "run_id",
    "generated_at",
    "phase",
    "scenario",
    "input_summary",
    "classification",
    "confidence",
    "primary_suspect",
    "secondary_suspects",
    "evidence",
    "recommended_next_checks",
    "manual_confirmation_required",
    "consistency_status",
    "sensitive_data_policy",
    "non_scope",
    "follow_up_candidates",
    "validation_summary",
}
ALLOWED_REPORT_FIELDS = REQUIRED_REPORT_FIELDS
REQUIRED_EVIDENCE_FIELDS = {"run_id", "scenario", "baseline", "observed", "consistency"}
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
FORBIDDEN_CLAIMS = [
    "k6 proves postgres root cause",
    "k6 alone proves postgres",
    "k6 alone proves redis",
    "k6 alone proves external",
    "PH11 latency drill completed",
    "make k6-latency-baseline completed",
    "make latency-drill-db-pool completed",
    "AI confirmed the root cause",
    "AI automatically fixes latency",
    "AI가 latency 원인을 확정한다",
    "AI가 복구를 자동 실행한다",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--input", type=Path, required=True)
    analyze_parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, default=SAMPLE_REPORT)

    subparsers.add_parser("list-rules")

    args = parser.parse_args()
    try:
        result = _handle(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"PH10 latency attribution error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "demo":
        evidence = sample_evidence()
        report = analyze_evidence(evidence)
        _write_outputs(args.output_dir, evidence, report)
        validation_errors = validate_report_payload(report)
        if validation_errors:
            raise ValueError(json.dumps(validation_errors, ensure_ascii=False))
        return {
            "input": str(args.output_dir / "sample-input-evidence.json"),
            "output": str(args.output_dir / "sample-latency-attribution-report.json"),
            "report": str(args.output_dir / "sample-latency-attribution-report.md"),
            "classification": report["classification"],
            "validation_errors": [],
        }

    if args.command == "analyze":
        evidence = json.loads(args.input.read_text(encoding="utf-8"))
        report = analyze_evidence(evidence)
        _write_outputs(args.output_dir, evidence, report)
        return {
            "input": str(args.input),
            "output": str(args.output_dir / "sample-latency-attribution-report.json"),
            "classification": report["classification"],
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

    if args.command == "list-rules":
        return {"rules": list_rules()}

    raise SystemExit(f"unknown command: {args.command}")


def sample_evidence() -> dict[str, Any]:
    return {
        "run_id": "ph10-sample-latency-attribution",
        "generated_at": FIXED_GENERATED_AT,
        "scenario": "db_phase_dominant",
        "route_group": "financial_event_write",
        "method": "POST",
        "status_code_family": "2xx",
        "baseline": {
            "k6_p95_ms": 180,
            "k6_p99_ms": 420,
            "server_handler_p95_ms": 120,
            "server_handler_p99_ms": 300,
        },
        "observed": {
            "k6_p95_ms": 620,
            "k6_p99_ms": 1800,
            "nginx_request_p95_ms": 600,
            "nginx_upstream_p95_ms": 570,
            "fastapi_handler_p95_ms": 540,
            "hmac_phase_p95_ms": 5,
            "idempotency_phase_p95_ms": 20,
            "redis_phase_p95_ms": 30,
            "postgres_phase_p95_ms": 390,
            "business_logic_p95_ms": 50,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0.01,
        },
        "consistency": {
            "duplicate_ledger_count": 0,
            "duplicate_external_event_count": 0,
            "reconciliation_failure_count": 0,
            "invalid_state_transition_count": 0,
        },
    }


def analyze_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_EVIDENCE_FIELDS - set(evidence))
    if missing:
        return _report(
            evidence,
            "insufficient_evidence",
            "LOW",
            "unknown",
            [],
            [f"missing evidence fields: {', '.join(missing)}"],
            ["collect baseline, observed phase, and consistency evidence"],
        )

    baseline = evidence.get("baseline", {})
    observed = evidence.get("observed", {})
    if not isinstance(baseline, dict) or not isinstance(observed, dict):
        return _report(
            evidence,
            "insufficient_evidence",
            "LOW",
            "unknown",
            [],
            ["baseline and observed evidence must be objects"],
            ["regenerate structured latency evidence"],
        )

    k6_p95 = _num(observed, "k6_p95_ms")
    k6_p99 = _num(observed, "k6_p99_ms")
    base_p95 = _num(baseline, "k6_p95_ms")
    base_p99 = _num(baseline, "k6_p99_ms")
    handler = _num(observed, "fastapi_handler_p95_ms")
    base_handler = _num(baseline, "server_handler_p95_ms")
    nginx_request = _num(observed, "nginx_request_p95_ms")
    nginx_upstream = _num(observed, "nginx_upstream_p95_ms")
    postgres = _num(observed, "postgres_phase_p95_ms")
    db_pool = _num(observed, "db_pool_wait_p95_ms")
    db_lock = _num(observed, "db_lock_wait_p95_ms")
    redis = _num(observed, "redis_phase_p95_ms")
    outbound = _num(observed, "outbound_http_p95_ms")
    blackbox = _num(observed, "blackbox_probe_p95_ms")
    error_rate = _num(observed, "error_rate")

    if not all(value is not None for value in (k6_p95, k6_p99, base_p95, base_p99)):
        return _report(
            evidence,
            "insufficient_evidence",
            "LOW",
            "unknown",
            [],
            ["missing k6 or baseline percentile evidence"],
            ["collect k6 p95/p99 and baseline p95/p99"],
        )

    consistency_status = consistency_status_from(evidence.get("consistency"))
    normal_k6 = k6_p95 < base_p95 * 2 and k6_p99 < base_p99 * 2 and k6_p95 <= 300
    if normal_k6 and error_rate <= 0.01 and consistency_status == "CLEAN":
        return _report(
            evidence,
            "baseline_normal_latency",
            "HIGH",
            "none",
            [],
            [
                "k6 p95/p99 are below 2x baseline and below initial absolute threshold",
                "error rate is low",
                "consistency counters are clean",
            ],
            ["continue baseline collection and watch for route-specific changes"],
        )

    if handler is None or base_handler is None:
        return _report(
            evidence,
            "insufficient_evidence",
            "LOW",
            "unknown",
            [],
            ["missing FastAPI handler baseline or observed evidence"],
            ["collect server handler p95 and phase timing evidence"],
        )

    handler_high = handler > base_handler * 2 or handler > 300
    upstream_normal = nginx_upstream is not None and nginx_upstream <= max(
        base_handler * 2, 250
    )
    handler_normal = handler <= max(base_handler * 2, 250)
    if (
        nginx_request is not None
        and nginx_request > max(base_p95 * 2, 500)
        and upstream_normal
        and handler_normal
    ):
        return _report(
            evidence,
            "edge_or_client_network_latency",
            "MEDIUM",
            "edge_or_client_network",
            ["nginx_edge", "partner_network"],
            [
                "Nginx request time is high while upstream and FastAPI handler remain near baseline",
                "k6 latency is a symptom and does not prove an internal dependency bottleneck",
            ],
            ["compare Nginx access timing with partner-side timestamps"],
        )

    if (
        outbound
        and blackbox
        and blackbox > max(base_p95 * 2, 500)
        and outbound >= handler * 0.5
    ):
        return _report(
            evidence,
            "external_endpoint_slow",
            "HIGH",
            "external_endpoint",
            ["outbound_http_client"],
            ["blackbox probe and app outbound HTTP phase are both high"],
            ["confirm provider status and compare blackbox probe history"],
        )

    if (
        outbound
        and outbound >= handler * 0.7
        and blackbox
        and blackbox <= max(base_p95, 250)
    ):
        return _report(
            evidence,
            "app_http_client_path_issue",
            "MEDIUM",
            "app_http_client_path",
            ["dns_tls_pool"],
            ["app outbound HTTP is high while blackbox probe is normal"],
            ["inspect HTTP client pool, DNS, TLS, timeout, and retry settings"],
        )

    if db_pool and handler_high and db_pool >= handler * 0.35:
        return _report(
            evidence,
            "internal_postgres_pool_pressure",
            "MEDIUM",
            "postgres_pool_wait",
            ["postgres"],
            ["DB pool wait is a large share of FastAPI handler time"],
            ["check DB connection usage and pool timeout logs"],
        )

    if db_lock and handler_high and db_lock >= handler * 0.35:
        return _report(
            evidence,
            "internal_postgres_lock_contention",
            "MEDIUM",
            "postgres_lock_wait",
            ["postgres"],
            ["DB lock wait is a large share of FastAPI handler time"],
            ["inspect lock holder queries and transaction duration"],
        )

    if postgres and handler_high and postgres >= handler * 0.6:
        return _report(
            evidence,
            "internal_postgres_latency",
            "HIGH",
            "postgres",
            ["db_query_or_transaction"],
            [
                "FastAPI handler p95 increased",
                "PostgreSQL phase is at least 60% of handler time",
                "Redis and outbound phases are not dominant",
            ],
            ["check DB pool, lock wait, slow query, and consistency SQL evidence"],
        )

    if observed.get("redis_unavailable") is True:
        return _report(
            evidence,
            "redis_unavailable_fallback",
            "MEDIUM",
            "redis_unavailable",
            ["db_fallback"],
            ["Redis is unavailable and fallback path is active"],
            ["confirm PostgreSQL consistency and Redis recovery status"],
        )

    if (
        redis
        and handler_high
        and redis >= handler * 0.4
        and not (postgres and postgres >= handler * 0.6)
    ):
        return _report(
            evidence,
            "redis_degraded_latency",
            "MEDIUM",
            "redis",
            ["redis_timeout_or_fallback"],
            [
                "Redis phase is at least 40% of handler time while PostgreSQL is not dominant"
            ],
            ["check Redis latency, timeout, and fallback metrics"],
        )

    if outbound and handler_high and outbound >= handler * 0.7:
        return _report(
            evidence,
            "external_dependency_latency",
            "MEDIUM",
            "outbound_dependency",
            ["external_partner"],
            ["outbound HTTP phase is at least 70% of handler time"],
            ["compare app outbound metric with blackbox probe and provider status"],
        )

    if evidence.get("partner_alias") and k6_p95 > base_p95 * 2:
        return _report(
            evidence,
            "partner_specific_latency",
            "LOW",
            "partner_specific",
            ["partner_network_or_payload"],
            [
                "latency is associated with a bounded partner_alias evidence field",
                "candidate scope only, not final root cause",
            ],
            ["compare with other partner_alias groups without using raw identifiers"],
        )

    if evidence.get("route_group") and k6_p95 > base_p95 * 2 and not handler_high:
        return _report(
            evidence,
            "route_specific_latency_candidate",
            "LOW",
            "route_group",
            ["route_specific"],
            [
                "latency is tied to route_group but phase evidence is not yet dominant",
                "candidate scope only, not final root cause",
            ],
            ["collect per-phase timing for the route_group"],
        )

    if handler_high:
        return _report(
            evidence,
            "internal_application_latency",
            "LOW",
            "fastapi_handler",
            ["application_logic"],
            ["FastAPI handler increased but no dependency phase is dominant"],
            ["collect finer phase timing and route-specific logs"],
        )

    return _report(
        evidence,
        "insufficient_evidence",
        "LOW",
        "unknown",
        [],
        ["available evidence is contradictory or not specific enough"],
        [
            "collect Nginx, FastAPI phase, Redis, PostgreSQL, outbound, blackbox, and consistency evidence"
        ],
    )


def validate_report(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_report_payload(payload)


def validate_report_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing_fields = sorted(REQUIRED_REPORT_FIELDS - set(payload))
    if missing_fields:
        errors.append(f"missing top-level fields: {', '.join(missing_fields)}")
    extra_fields = sorted(set(payload) - ALLOWED_REPORT_FIELDS)
    if extra_fields:
        errors.append(f"unexpected top-level fields: {', '.join(extra_fields)}")

    classification = payload.get("classification")
    if classification not in CLASSIFICATIONS:
        errors.append(
            f"classification must be one of: {', '.join(sorted(CLASSIFICATIONS))}"
        )
    if payload.get("confidence") not in CONFIDENCE_LEVELS:
        errors.append("confidence must be LOW, MEDIUM, or HIGH")
    if payload.get("consistency_status") not in CONSISTENCY_STATUSES:
        errors.append(
            "consistency_status must be CLEAN, VIOLATION_DETECTED, or UNKNOWN"
        )
    if classification != "insufficient_evidence" and not payload.get("evidence"):
        errors.append("non-insufficient classification must include evidence")
    if classification != "insufficient_evidence" and not payload.get(
        "recommended_next_checks"
    ):
        errors.append(
            "non-insufficient classification must include recommended_next_checks"
        )

    _validate_k6_only_claim(payload, errors)
    _validate_consistency_boundary(payload, errors)
    _validate_sensitive_content(payload, errors)
    _validate_metric_labels(payload, errors)

    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for claim in FORBIDDEN_CLAIMS:
        if claim.lower() in rendered.lower():
            errors.append(f"forbidden claim found: {claim}")
    return sorted(set(errors))


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# PH10 Latency Attribution Report",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Scenario: `{report['scenario']}`",
        f"- Classification: `{report['classification']}`",
        f"- Confidence: `{report['confidence']}`",
        f"- Primary suspect: `{report['primary_suspect']}`",
        f"- Consistency status: `{report['consistency_status']}`",
        "",
        "## Interpretation Boundary",
        "",
        "- k6 p95/p99 are symptom evidence, not standalone root-cause proof.",
        "- Attribution compares Nginx timing, FastAPI phase timing, Redis/PostgreSQL, outbound HTTP, blackbox probe, and consistency evidence.",
        "- PH10 implements an analyzer/report, not PH11 latency drill execution.",
        "- Consistency violations remain separate SEV1 candidates and are not downgraded to latency warnings.",
        "",
        "## Evidence",
        "",
    ]
    lines.extend(f"- {item}" for item in report["evidence"])
    lines.extend(["", "## Recommended Next Checks", ""])
    lines.extend(f"- {item}" for item in report["recommended_next_checks"])
    lines.extend(["", "## Manual Confirmation Required", ""])
    lines.extend(f"- {item}" for item in report["manual_confirmation_required"])
    lines.extend(["", "## Follow-up Candidates", ""])
    for candidate in report["follow_up_candidates"]:
        lines.append(f"- {candidate}")
    return "\n".join(lines) + "\n"


def list_rules() -> list[dict[str, str]]:
    return [
        {"classification": name, "meaning": _rule_meaning(name)}
        for name in sorted(CLASSIFICATIONS)
    ]


def consistency_status_from(consistency: Any) -> str:
    if not isinstance(consistency, dict):
        return "UNKNOWN"
    counters = [
        "duplicate_ledger_count",
        "duplicate_external_event_count",
        "reconciliation_failure_count",
        "invalid_state_transition_count",
    ]
    values = [consistency.get(counter) for counter in counters]
    if any(isinstance(value, (int, float)) and value > 0 for value in values):
        return "VIOLATION_DETECTED"
    if all(isinstance(value, (int, float)) and value == 0 for value in values):
        return "CLEAN"
    return "UNKNOWN"


def _report(
    evidence: dict[str, Any],
    classification: str,
    confidence: str,
    primary_suspect: str,
    secondary_suspects: list[str],
    evidence_lines: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    consistency_status = consistency_status_from(evidence.get("consistency"))
    return {
        "run_id": evidence.get("run_id", "ph10-latency-attribution"),
        "generated_at": evidence.get("generated_at", FIXED_GENERATED_AT),
        "phase": "PH10 Latency Attribution / External Dependency Diagnosis",
        "scenario": evidence.get("scenario", "unknown"),
        "input_summary": {
            "route_group": evidence.get("route_group", "not_collected"),
            "method": evidence.get("method", "not_collected"),
            "status_code_family": evidence.get("status_code_family", "not_collected"),
            "consistency": evidence.get("consistency", "not_collected"),
            "k6_is_symptom_only": True,
            "raw_identifiers_included": False,
        },
        "classification": classification,
        "confidence": confidence,
        "primary_suspect": primary_suspect,
        "secondary_suspects": secondary_suspects,
        "evidence": evidence_lines,
        "recommended_next_checks": next_checks,
        "manual_confirmation_required": [
            "operator must confirm with dashboard, logs, and runbook evidence",
            "do not treat deterministic classification as final root cause",
            "if consistency_status is VIOLATION_DETECTED, follow consistency incident flow first",
        ],
        "consistency_status": consistency_status,
        "sensitive_data_policy": {
            "financial_identifier_policy": "plain values prohibited",
            "retry_identifier_policy": "plain values prohibited",
            "request_payload_policy": "payload contents prohibited",
            "auth_material_policy": "headers and signing material prohibited",
            "endpoint_value_policy": "plain endpoint values prohibited",
            "metric_label_policy": "bounded route_group, endpoint_group, partner_alias, method, status_code, result, phase, operation only",
        },
        "non_scope": [
            "PH11 k6 latency drill execution",
            "Toxiproxy or netem fault injection",
            "mock partner service",
            "OpenTelemetry full tracing",
            "production network fault injection",
            "AI root-cause confirmation or automatic recovery",
        ],
        "follow_up_candidates": [
            "PH11 k6 latency scenarios and fault injection",
            "mock partner service",
            "Toxiproxy or netem latency profile",
            "OpenTelemetry trace expansion",
            "Grafana latency attribution dashboard",
        ],
        "validation_summary": {
            "classification_is_candidate": True,
            "k6_only_root_cause_claim_allowed": False,
            "ph11_drill_completed": False,
            "sensitive_data_included": False,
        },
    }


def _write_outputs(
    output_dir: Path, evidence: dict[str, Any], report: dict[str, Any]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sample-input-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_path = output_dir / "sample-latency-attribution-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_path.with_suffix(".md").write_text(
        render_markdown_report(report), encoding="utf-8"
    )


def _num(mapping: dict[str, Any], key: str) -> Optional[float]:
    value = mapping.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _validate_k6_only_claim(payload: dict[str, Any], errors: list[str]) -> None:
    classification = payload.get("classification")
    if classification in {
        "internal_postgres_latency",
        "redis_degraded_latency",
        "external_dependency_latency",
        "external_endpoint_slow",
        "app_http_client_path_issue",
    }:
        evidence_text = " ".join(
            str(item).lower() for item in payload.get("evidence", [])
        )
        has_supporting_signal = any(
            term in evidence_text
            for term in (
                "nginx",
                "fastapi",
                "postgres",
                "redis",
                "outbound",
                "blackbox",
            )
        )
        if "k6" in evidence_text and not has_supporting_signal:
            errors.append("k6-only evidence cannot assert DB/Redis/external root cause")


def _validate_consistency_boundary(payload: dict[str, Any], errors: list[str]) -> None:
    summary = payload.get("input_summary", {})
    consistency = summary.get("consistency") if isinstance(summary, dict) else None
    if consistency_status_from(consistency) == "VIOLATION_DETECTED":
        if payload.get("consistency_status") == "CLEAN":
            errors.append("consistency violation cannot be reported as CLEAN")
    evidence_text = json.dumps(payload.get("evidence", []), ensure_ascii=False).lower()
    if (
        "duplicate ledger" in evidence_text
        and payload.get("consistency_status") == "CLEAN"
    ):
        errors.append("consistency violation evidence cannot be reported as CLEAN")


def _validate_sensitive_content(value: Any, errors: list[str], path: str = "$") -> None:
    if path.startswith("$.sensitive_data_policy") or path.startswith("$.non_scope"):
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            key_lower = str(key).lower()
            forbidden_key = _matching_forbidden_key(key_lower)
            if forbidden_key is not None:
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


def _rule_meaning(classification: str) -> str:
    meanings = {
        "baseline_normal_latency": "k6 and server timings are near baseline and consistency is clean",
        "internal_postgres_latency": "PostgreSQL phase dominates FastAPI handler time",
        "internal_postgres_pool_pressure": "DB pool wait is a material share of handler time",
        "internal_postgres_lock_contention": "DB lock wait is a material share of handler time",
        "redis_degraded_latency": "Redis phase dominates without PostgreSQL dominance",
        "redis_unavailable_fallback": "Redis unavailable and fallback path is active",
        "external_dependency_latency": "app outbound HTTP dominates handler time",
        "external_endpoint_slow": "blackbox probe and app outbound are both high",
        "app_http_client_path_issue": "blackbox probe is normal but app outbound is high",
        "edge_or_client_network_latency": "Nginx request is high while upstream/app are normal",
        "partner_specific_latency": "bounded partner_alias evidence narrows candidate scope",
        "internal_application_latency": "handler is high without a dominant dependency phase",
        "route_specific_latency_candidate": "bounded route_group candidate without enough phase evidence",
        "insufficient_evidence": "evidence is missing or contradictory",
    }
    return meanings[classification]


if __name__ == "__main__":
    raise SystemExit(main())
