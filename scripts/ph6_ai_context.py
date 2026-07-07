#!/usr/bin/env python3
"""Generate and validate PH6 AI-safe context artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
DEFAULT_OUTPUT_ROOT = ROOT_DIR / "reports/ai-context"
SAMPLE_CONTEXT = DEFAULT_OUTPUT_ROOT / "sample-ai-context.json"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.security.ai_context_sanitizer import (  # noqa: E402
    render_markdown_report,
    sanitize_context,
    validate_sanitized_context,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sanitize_parser = subparsers.add_parser("sanitize")
    sanitize_parser.add_argument("--input", type=Path, required=True)
    sanitize_parser.add_argument("--output", type=Path)
    sanitize_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)

    latest_parser = subparsers.add_parser("sanitize-latest")
    latest_parser.add_argument(
        "--source", choices=["incidents", "reconciliation"], default="incidents"
    )
    latest_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, default=SAMPLE_CONTEXT)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)

    args = parser.parse_args()
    try:
        result = _handle(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"PH6 AI context error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "sanitize":
        payload = _load_input(args.input)
        output_path = args.output or _create_run_dir(args.output_dir) / "context.json"
        return _write_sanitized_context(payload, output_path)

    if args.command == "sanitize-latest":
        source_dir = _latest_source_dir(args.source)
        output_path = _create_run_dir(args.output_dir) / "context.json"
        return _write_sanitized_context(_load_input(source_dir), output_path)

    if args.command == "validate":
        errors = validate_context_file(args.input)
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

    if args.command == "demo":
        run_dir = _create_run_dir(args.output_dir)
        output_path = run_dir / "context.json"
        result = _write_sanitized_context(_demo_payload(), output_path)
        errors = validate_context_file(output_path)
        result["validation_errors"] = errors
        if errors:
            raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    raise SystemExit(f"unknown command: {args.command}")


def validate_context_file(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_sanitized_context(payload)
    if payload.get("sensitive_data_included") is not False:
        errors.append("sensitive_data_included must be false")
    if "sanitized_context" not in payload:
        errors.append("missing sanitized_context")
    if "redaction_summary" not in payload:
        errors.append("missing redaction_summary")
    return sorted(set(errors))


def _write_sanitized_context(payload: Any, output_path: Path) -> dict[str, Any]:
    result = sanitize_context(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_payload = result.to_dict()
    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_path = output_path.with_suffix(".md")
    report_path.write_text(render_markdown_report(result), encoding="utf-8")
    return {
        "output": str(output_path),
        "report": str(report_path),
        "removed_field_count": len(result.removed_fields),
        "validation_errors": validate_context_file(output_path),
    }


def _load_input(path: Path) -> Any:
    if path.is_dir():
        payload: dict[str, Any] = {
            "source": path.name,
            "evidence_paths": _evidence_paths(path),
        }
        for json_file in sorted(path.glob("*.json")):
            content = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(content, dict):
                payload.update(content)
            else:
                payload[json_file.stem.replace("-", "_")] = content
        return payload
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_source_dir(source: str) -> Path:
    if source == "incidents":
        root = ROOT_DIR / "reports/incidents"
        candidates = sorted(path for path in root.glob("inc-*") if path.is_dir())
    else:
        root = ROOT_DIR / "reports/reconciliation"
        candidates = sorted(path for path in root.glob("run-*") if path.is_dir())
    if not candidates:
        raise FileNotFoundError(f"no {source} artifacts found under {root}")
    return candidates[-1]


def _create_run_dir(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    base = f"run-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    run_dir = output_root / base
    suffix = 1
    while run_dir.exists():
        run_dir = output_root / f"{base}-{suffix:03d}"
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir


def _evidence_paths(path: Path) -> list[str]:
    return sorted(
        str(item.relative_to(ROOT_DIR))
        for item in path.iterdir()
        if item.is_file() and item.suffix in {".json", ".md", ".txt"}
    )


def _demo_payload() -> dict[str, Any]:
    return {
        "incident_id": "inc-demo-postgres-down",
        "run_id": "ph6-demo",
        "classification": "STALE_PROCESSING_DETECTED",
        "severity": "SEV2",
        "confidence": 0.82,
        "created_at": "2026-07-07T00:00:00+00:00",
        "status": "WAITING_APPROVAL",
        "case_type": "STALE_PROCESSING",
        "target_type": "ACCOUNT",
        "account_token": "acctok_demo_001",
        "event_token": "evttok_demo_001",
        "idempotency_key_hash": "a" * 64,
        "request_hash": "b" * 64,
        "consistency_counts": {
            "stale_processing_count": 1,
            "duplicate_ledger_count": 0,
            "duplicate_external_event_count": 0,
            "account_balance_mismatch_count": 0,
            "account_no": "ACC-001",
        },
        "manual_action_candidates": [
            {
                "proposed_action": "NOOP_REVIEW_ONLY",
                "approval_required": True,
                "authorization": "Bearer REDACTED",
            }
        ],
        "runbook_reference": "docs/48-ph6-ai-safe-context-sanitizer.md",
        "evidence_paths": ["reports/incidents/sample-analyzer-result.json"],
        "raw_request_body": '{"amount":1000}',
        "hmac_signature": "HMAC REDACTED",
    }


if __name__ == "__main__":
    raise SystemExit(main())
