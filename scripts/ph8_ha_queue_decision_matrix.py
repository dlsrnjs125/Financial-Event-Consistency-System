#!/usr/bin/env python3
"""Generate and validate PH8 PostgreSQL HA / queue trade-off evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT_DIR / "reports/architecture/ph8-ha-queue-tradeoff"
SAMPLE_REPORT = DEFAULT_REPORT_DIR / "sample-ha-queue-decision-report.json"
FIXED_GENERATED_AT = "2026-07-07T00:00:00+00:00"
REQUIRED_TOP_LEVEL_FIELDS = {
    "run_id",
    "generated_at",
    "phase",
    "current_decision",
    "options",
    "decision_matrix",
    "recommendation",
    "manual_approval_required",
    "non_scope",
    "follow_up_candidates",
    "sensitive_data_included",
}
REQUIRED_OPTIONS = {
    "direct_postgres_fail_closed",
    "postgres_primary_standby_ha",
    "synchronous_replication",
    "managed_db_ha",
    "durable_queue_first",
}
OPTION_FIELDS = {
    "option_id",
    "name",
    "api_response_semantics",
    "write_durability_model",
    "availability_score",
    "consistency_explainability_score",
    "operational_complexity_score",
    "cost_score",
    "local_portfolio_fit_score",
    "risk_summary",
    "required_new_controls",
    "decision",
}
DECISION_MATRIX_FIELDS = {
    "option_id",
    "total_context_score",
    "decision",
    "note",
}
SCORE_FIELDS = (
    "availability_score",
    "consistency_explainability_score",
    "operational_complexity_score",
    "cost_score",
    "local_portfolio_fit_score",
)
SENSITIVE_KEY_PATTERNS = re.compile(
    r"(account_no|raw_account_no|idempotency_key|raw_idempotency_key|"
    r"authorization|signature|client_secret|access_token|refresh_token|"
    r"password|raw_request_body|database_url)",
    re.IGNORECASE,
)
SENSITIVE_TEXT_PATTERNS = [
    re.compile(r"Authorization\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"Basic\s+\S+", re.IGNORECASE),
    re.compile(r"X-Signature\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"Idempotency-Key\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"raw_request_body", re.IGNORECASE),
    re.compile(r"raw_account_no", re.IGNORECASE),
    re.compile(r"raw_idempotency_key", re.IGNORECASE),
    re.compile(r"postgresql://\S+", re.IGNORECASE),
]
FORBIDDEN_CLAIMS = [
    "queue 도입 시 바로 원장 반영 완료를 보장한다",
    "queue-first guarantees ledger completion",
    "HA 도입 시 consistency gate가 불필요하다",
    "HA removes the need for consistency gate",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, default=SAMPLE_REPORT)

    args = parser.parse_args()
    try:
        result = _handle(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"PH8 HA/Queue decision error: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "demo":
        report = build_report()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = args.output_dir / "sample-ha-queue-decision-report.json"
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
            "option_count": len(report["options"]),
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

    raise SystemExit(f"unknown command: {args.command}")


def build_report() -> dict[str, Any]:
    options = _options()
    return {
        "run_id": "ph8-ha-queue-tradeoff-sample",
        "generated_at": FIXED_GENERATED_AT,
        "phase": "PH8 PostgreSQL HA / Durable Queue Trade-off ADR",
        "current_decision": (
            "Maintain direct PostgreSQL transaction + fail-closed/write suspend now; "
            "treat PostgreSQL HA and durable queue-first architecture as follow-up "
            "availability and V2 contract candidates."
        ),
        "options": options,
        "decision_matrix": _decision_matrix(options),
        "recommendation": {
            "recommended_now": [
                "Direct PostgreSQL transaction",
                "Fail-closed 503 + Retry-After when PostgreSQL write path is unavailable",
                "Write suspend, recovery case, and consistency gate before write resume",
            ],
            "recommended_later": [
                "Managed DB HA for production availability after failover drills",
                "Queue-first V2 only after ACCEPTED/COMPLETED API contract split",
                "Consumer idempotency, DLQ, replay, offset evidence, and reconciliation",
            ],
        },
        "manual_approval_required": [
            "PostgreSQL failover promote",
            "write resume after failover or restore",
            "ledger correction or compensation",
            "customer or partner impact confirmation",
            "queue replay and DLQ redrive",
        ],
        "non_scope": [
            "Patroni or repmgr cluster implementation",
            "Kafka, RabbitMQ, SQS, or cloud resource provisioning",
            "automatic failover promote",
            "automatic write resume",
            "queue-first API contract implementation",
        ],
        "follow_up_candidates": [
            "managed DB HA runbook and failover drill",
            "stale connection readiness drill",
            "queue-first API V2 ADR",
            "consumer idempotency and DLQ replay design",
            "RPO/RTO split for API accept and ledger posting",
        ],
        "sensitive_data_included": False,
    }


def validate_report(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_report_payload(payload)


def validate_report_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing_fields = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(payload))
    if missing_fields:
        errors.append(f"missing top-level fields: {', '.join(missing_fields)}")
    if not payload.get("current_decision"):
        errors.append("current_decision must not be empty")
    if payload.get("sensitive_data_included") is not False:
        errors.append("sensitive_data_included must be false")

    options = payload.get("options")
    if not isinstance(options, list):
        errors.append("options must be a list")
        options = []

    found_options = {
        option.get("option_id") for option in options if isinstance(option, dict)
    }
    missing_options = sorted(REQUIRED_OPTIONS - found_options)
    if missing_options:
        errors.append(f"missing required options: {', '.join(missing_options)}")

    for index, option in enumerate(options):
        if not isinstance(option, dict):
            errors.append(f"options[{index}] must be an object")
            continue
        extra_keys = sorted(set(option) - OPTION_FIELDS)
        if extra_keys:
            errors.append(
                f"{option.get('option_id', index)} has unexpected keys: {extra_keys}"
            )
        missing_option_fields = sorted(OPTION_FIELDS - set(option))
        if missing_option_fields:
            errors.append(
                f"{option.get('option_id', index)} missing fields: "
                f"{', '.join(missing_option_fields)}"
            )
        _validate_scores(option, errors)
        _validate_option_policy(option, errors)

    _validate_decision_matrix(payload, errors)
    _validate_sensitive_content(payload, errors)
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for claim in FORBIDDEN_CLAIMS:
        if claim.lower() in rendered.lower():
            errors.append(f"forbidden claim found: {claim}")
    return sorted(set(errors))


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# PH8 PostgreSQL HA / Queue Decision Report",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Phase: `{report['phase']}`",
        f"- Current decision: {report['current_decision']}",
        "",
        "## Contract Boundary",
        "",
        "- Direct PostgreSQL path: `COMPLETED` means PostgreSQL commit evidence exists.",
        "- Queue-first path: `ACCEPTED` means durable enqueue; `COMPLETED` means later ledger posting commit.",
        "",
        "## Score Note",
        "",
        "Scores are deterministic project-fit signals, not production benchmarks.",
        "",
        "## Decision Matrix",
        "",
        "| Option | Availability | Explainability | Complexity | Cost | Local Fit | Decision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for option in report["options"]:
        lines.append(
            "| {name} | {availability} | {explainability} | {complexity} | {cost} | {fit} | {decision} |".format(
                name=option["name"],
                availability=option["availability_score"],
                explainability=option["consistency_explainability_score"],
                complexity=option["operational_complexity_score"],
                cost=option["cost_score"],
                fit=option["local_portfolio_fit_score"],
                decision=option["decision"],
            )
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Recommended now (`recommended_now`):",
        ]
    )
    lines.extend(f"- {item}" for item in report["recommendation"]["recommended_now"])
    lines.append("")
    lines.append("Recommended later (`recommended_later`):")
    lines.extend(f"- {item}" for item in report["recommendation"]["recommended_later"])
    lines.append("")
    lines.append("Follow-up candidates (`follow_up_candidates`):")
    lines.extend(f"- {item}" for item in report["follow_up_candidates"])
    return "\n".join(lines) + "\n"


def _options() -> list[dict[str, Any]]:
    return [
        {
            "option_id": "direct_postgres_fail_closed",
            "name": "Current: Direct PostgreSQL Transaction + Fail-Closed",
            "api_response_semantics": (
                "COMPLETED only after PostgreSQL commit; 503 + Retry-After when "
                "write path is unavailable."
            ),
            "write_durability_model": "PostgreSQL commit is the durability boundary.",
            "availability_score": 2,
            "consistency_explainability_score": 5,
            "operational_complexity_score": 5,
            "cost_score": 5,
            "local_portfolio_fit_score": 5,
            "risk_summary": "Lower write availability during DB outage, but no ambiguous success response.",
            "required_new_controls": [
                "write suspend",
                "Retry-After contract",
                "recovery case",
                "consistency gate before write resume",
            ],
            "decision": "recommended_now",
        },
        {
            "option_id": "postgres_primary_standby_ha",
            "name": "PostgreSQL Primary/Standby HA",
            "api_response_semantics": (
                "COMPLETED remains primary commit based; failover windows return "
                "503 until consistency gate and write resume approval complete."
            ),
            "write_durability_model": "Primary write with standby replication.",
            "availability_score": 4,
            "consistency_explainability_score": 4,
            "operational_complexity_score": 3,
            "cost_score": 3,
            "local_portfolio_fit_score": 3,
            "risk_summary": "Stale connections, split brain risk, and replication lag during failover.",
            "required_new_controls": [
                "failover consistency gate",
                "write resume approval",
                "primary identity verification",
                "connection pool recycle",
            ],
            "decision": "follow_up_candidate",
        },
        {
            "option_id": "synchronous_replication",
            "name": "Synchronous Replication",
            "api_response_semantics": (
                "COMPLETED still means commit, but commit latency and standby availability "
                "become part of the write path."
            ),
            "write_durability_model": "Commit waits for synchronous standby or quorum acknowledgement.",
            "availability_score": 3,
            "consistency_explainability_score": 4,
            "operational_complexity_score": 2,
            "cost_score": 3,
            "local_portfolio_fit_score": 2,
            "risk_summary": "Lower RPO, higher commit latency, and possible write stalls.",
            "required_new_controls": [
                "commit timeout policy",
                "ledger-critical path classification",
                "write suspend on standby quorum loss",
            ],
            "decision": "follow_up_candidate",
        },
        {
            "option_id": "managed_db_ha",
            "name": "Managed DB HA",
            "api_response_semantics": (
                "COMPLETED remains database commit based; application still handles "
                "connection retry, readiness, consistency gate, and write resume approval."
            ),
            "write_durability_model": "Managed primary/standby or multi-AZ durability boundary.",
            "availability_score": 4,
            "consistency_explainability_score": 4,
            "operational_complexity_score": 4,
            "cost_score": 2,
            "local_portfolio_fit_score": 2,
            "risk_summary": "Cloud dependency, cost, and application-level failover handling remain.",
            "required_new_controls": [
                "managed failover runbook",
                "readiness and stale connection drill",
                "consistency gate",
                "write resume approval",
            ],
            "decision": "recommended_later",
        },
        {
            "option_id": "durable_queue_first",
            "name": "Durable Queue-First Architecture",
            "api_response_semantics": (
                "API returns ACCEPTED for durable enqueue; COMPLETED is emitted only "
                "after consumer idempotency, PostgreSQL commit, and reconciliation evidence."
            ),
            "write_durability_model": "Queue durability first, PostgreSQL ledger posting later.",
            "availability_score": 5,
            "consistency_explainability_score": 3,
            "operational_complexity_score": 1,
            "cost_score": 2,
            "local_portfolio_fit_score": 1,
            "risk_summary": "Accept/posting split, DLQ, replay, offset, and reconciliation complexity.",
            "required_new_controls": [
                "ACCEPTED vs COMPLETED API contract split",
                "consumer idempotency",
                "DLQ and replay approval",
                "offset checkpoint evidence",
                "reconciliation",
            ],
            "decision": "v2_candidate",
        },
    ]


def _decision_matrix(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for option in options:
        rows.append(
            {
                "option_id": option["option_id"],
                "total_context_score": sum(option[field] for field in SCORE_FIELDS),
                "decision": option["decision"],
                "note": "Scores are deterministic project-fit signals, not production benchmarks.",
            }
        )
    return rows


def _validate_scores(option: dict[str, Any], errors: list[str]) -> None:
    for field in SCORE_FIELDS:
        value = option.get(field)
        if not isinstance(value, int) or value < 1 or value > 5:
            errors.append(f"{option.get('option_id', 'unknown')} {field} must be 1..5")


def _validate_decision_matrix(payload: dict[str, Any], errors: list[str]) -> None:
    options = payload.get("options")
    if not isinstance(options, list):
        return

    options_by_id = {
        option["option_id"]: option
        for option in options
        if isinstance(option, dict) and isinstance(option.get("option_id"), str)
    }
    rows = payload.get("decision_matrix")
    if not isinstance(rows, list):
        errors.append("decision_matrix must be a list")
        return

    row_ids = {row.get("option_id") for row in rows if isinstance(row, dict)}
    missing_rows = sorted(REQUIRED_OPTIONS - row_ids)
    if missing_rows:
        errors.append(f"decision_matrix missing rows: {', '.join(missing_rows)}")

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"decision_matrix[{index}] must be an object")
            continue
        extra_keys = sorted(set(row) - DECISION_MATRIX_FIELDS)
        row_label = row.get("option_id", index)
        if extra_keys:
            errors.append(
                f"decision_matrix row {row_label} has unexpected keys: "
                f"{', '.join(extra_keys)}"
            )

        option = options_by_id.get(row.get("option_id"))
        if option is None:
            errors.append(f"decision_matrix row has unknown option_id: {row_label}")
            continue
        if not all(isinstance(option.get(field), int) for field in SCORE_FIELDS):
            continue

        expected_total = sum(option[field] for field in SCORE_FIELDS)
        if row.get("total_context_score") != expected_total:
            errors.append(f"{row['option_id']} total_context_score mismatch")
        if row.get("decision") != option.get("decision"):
            errors.append(f"{row['option_id']} decision mismatch")


def _validate_option_policy(option: dict[str, Any], errors: list[str]) -> None:
    option_id = option.get("option_id")
    rendered = json.dumps(option, ensure_ascii=False, sort_keys=True).lower()
    if option_id == "durable_queue_first":
        if "accepted" not in rendered or "completed" not in rendered:
            errors.append(
                "durable_queue_first must split ACCEPTED and COMPLETED semantics"
            )
    if option_id in {"postgres_primary_standby_ha", "managed_db_ha"}:
        if (
            "consistency gate" not in rendered
            or "write resume approval" not in rendered
        ):
            errors.append(
                f"{option_id} must mention consistency gate and write resume approval"
            )
    if option_id == "direct_postgres_fail_closed":
        if "fail-closed" not in rendered and "503" not in rendered:
            errors.append(
                "direct_postgres_fail_closed must reference fail-closed or 503"
            )
        if "write suspend" not in rendered:
            errors.append("direct_postgres_fail_closed must reference write suspend")


def _validate_sensitive_content(value: Any, errors: list[str], path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if SENSITIVE_KEY_PATTERNS.search(str(key)):
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


if __name__ == "__main__":
    raise SystemExit(main())
