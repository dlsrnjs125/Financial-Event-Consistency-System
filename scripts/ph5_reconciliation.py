#!/usr/bin/env python3
"""Run PH5 stale PROCESSING detection and count-only reconciliation."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
DEFAULT_OUTPUT_ROOT = ROOT_DIR / "reports/reconciliation"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.quarantine_repository import QuarantineRepository  # noqa: E402
from app.repositories.recovery_case_repository import (  # noqa: E402
    RecoveryCaseRepository,
)
from app.services.quarantine_service import QuarantineService  # noqa: E402
from app.services.reconciliation_service import ReconciliationService  # noqa: E402
from app.services.recovery_case_service import RecoveryCaseService  # noqa: E402

PH2_SPEC = importlib.util.spec_from_file_location(
    "ph2_incident_artifact", ROOT_DIR / "scripts/ph2_incident_artifact.py"
)
ph2_incident_artifact = importlib.util.module_from_spec(PH2_SPEC)
assert PH2_SPEC and PH2_SPEC.loader
PH2_SPEC.loader.exec_module(ph2_incident_artifact)

REQUIRED_FILES = {
    "reconciliation-summary.json",
    "stale-processing-summary.json",
    "recovery-case-links.json",
    "consistency-counts.json",
    "ph5-report.md",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stale_parser = subparsers.add_parser("detect-stale")
    stale_parser.add_argument("--threshold-minutes", type=int, default=5)
    stale_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)

    reconcile_parser = subparsers.add_parser("reconcile")
    reconcile_parser.add_argument("--threshold-minutes", type=int, default=5)
    reconcile_parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT
    )

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--threshold-minutes", type=int, default=5)
    run_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--latest", action="store_true")
    report_parser.add_argument("--run-dir", type=Path)
    report_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--latest", action="store_true")
    validate_parser.add_argument("--run-dir", type=Path)
    validate_parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT
    )

    args = parser.parse_args()
    try:
        result = _handle(args)
    except SQLAlchemyError as exc:
        print(
            "PH5 requires a recovered PostgreSQL connection. "
            "If the database is unavailable, use PH1 write suspend and PH2/PH3 "
            f"incident artifact/analyzer flow first. error={type(exc).__name__}",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(f"PH5 report filesystem error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.command in {"detect-stale", "reconcile", "run"}:
        run_dir = _create_run_dir(args.output_root)
        with SessionLocal() as session:
            quarantine_service = QuarantineService(QuarantineRepository(session))
            recovery_service = RecoveryCaseService(
                RecoveryCaseRepository(session),
                quarantine_service=quarantine_service,
            )
            reconciliation_service = ReconciliationService(
                session,
                recovery_service,
                quarantine_service=quarantine_service,
            )
            if args.command == "detect-stale":
                candidates = reconciliation_service.detect_stale_processing(
                    threshold_minutes=args.threshold_minutes
                )
                counts = reconciliation_service.reconcile(
                    threshold_minutes=args.threshold_minutes,
                    create_recovery_cases=False,
                )[0]
                links: list[Any] = []
            elif args.command == "reconcile":
                candidates = reconciliation_service.detect_stale_processing(
                    threshold_minutes=args.threshold_minutes,
                    create_recovery_cases=False,
                )
                counts, links = reconciliation_service.reconcile(
                    threshold_minutes=args.threshold_minutes
                )
            else:
                candidates = reconciliation_service.detect_stale_processing(
                    threshold_minutes=args.threshold_minutes
                )
                counts, links = reconciliation_service.reconcile(
                    threshold_minutes=args.threshold_minutes
                )
            session.commit()

        summary = _write_artifact(
            run_dir, args.threshold_minutes, candidates, counts, links
        )
        validation_errors = validate_artifact(run_dir)
        summary["validation_errors"] = validation_errors
        if validation_errors:
            raise SystemExit(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary

    run_dir = args.run_dir
    if args.latest:
        run_dir = latest_run_dir(args.output_root)
    if run_dir is None:
        raise SystemExit("--run-dir or --latest is required")
    if args.command == "report":
        return {
            "run_dir": str(run_dir),
            "report": (run_dir / "ph5-report.md").read_text(),
        }
    if args.command == "validate":
        return {
            "run_dir": str(run_dir),
            "validation_errors": validate_artifact(run_dir),
        }
    raise SystemExit(f"unknown command: {args.command}")


def _create_run_dir(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    base = f"run-{dt.datetime.now(dt.UTC).strftime('%Y%m%d-%H%M%S')}"
    run_dir = output_root / base
    suffix = 1
    while run_dir.exists():
        run_dir = output_root / f"{base}-{suffix:03d}"
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir


def _write_artifact(
    run_dir: Path,
    threshold_minutes: int,
    candidates: list[Any],
    counts: Any,
    links: list[Any],
) -> dict[str, Any]:
    now = dt.datetime.now(dt.UTC).isoformat()
    stale_payload = {
        "threshold_minutes": threshold_minutes,
        "stale_processing_count": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
        "sensitive_data_included": False,
    }
    counts_payload = counts.to_dict()
    link_payload = {
        "links": [link.to_dict() for link in links],
        "sensitive_data_included": False,
    }
    summary = {
        "run_id": run_dir.name,
        "generated_at": now,
        "threshold_minutes": threshold_minutes,
        "stale_processing_count": len(candidates),
        "consistency_counts": counts_payload,
        "recovery_case_link_count": len(links),
        "sensitive_data_included": False,
    }
    _write_json(run_dir / "stale-processing-summary.json", stale_payload)
    _write_json(run_dir / "consistency-counts.json", counts_payload)
    _write_json(run_dir / "recovery-case-links.json", link_payload)
    _write_json(run_dir / "reconciliation-summary.json", summary)
    (run_dir / "ph5-report.md").write_text(
        render_report(summary, stale_payload, counts_payload, link_payload),
        encoding="utf-8",
    )
    return {"run_dir": str(run_dir), **summary}


def render_report(
    summary: dict[str, Any],
    stale_payload: dict[str, Any],
    counts: dict[str, int],
    links: dict[str, Any],
) -> str:
    return f"""# PH5 Reconciliation Report

## Summary

- Run ID: {summary["run_id"]}
- Generated At: {summary["generated_at"]}
- Threshold Minutes: {summary["threshold_minutes"]}
- Stale PROCESSING Count: {summary["stale_processing_count"]}
- Recovery Case Link Count: {summary["recovery_case_link_count"]}
- Sensitive Data Included: false

## Consistency Counts

{_markdown_counts(counts)}

## Stale PROCESSING Candidates

- Candidate Count: {stale_payload["stale_processing_count"]}

## Recovery Case Links

- Link Count: {len(links["links"])}

## PH5 Limits

- PH5 does not mark stale PROCESSING records completed or failed.
- PH5 does not update account balances.
- PH5 does not create compensation ledger entries.
- PH5 does not execute recovery actions.
"""


def validate_artifact(run_dir: Path) -> list[str]:
    errors: list[str] = []
    for filename in sorted(REQUIRED_FILES):
        if not (run_dir / filename).exists():
            errors.append(f"missing {filename}")
    for json_file in [
        "reconciliation-summary.json",
        "stale-processing-summary.json",
        "recovery-case-links.json",
        "consistency-counts.json",
    ]:
        path = run_dir / json_file
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{json_file} invalid JSON: {exc}")
            continue
        if (
            json_file != "consistency-counts.json"
            and payload.get("sensitive_data_included") is not False
        ):
            errors.append(f"{json_file} sensitive_data_included must be false")
    for path in run_dir.iterdir() if run_dir.exists() else []:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if ph2_incident_artifact.SENSITIVE_TEXT_RE.search(text):
            errors.append(f"sensitive value pattern found: {path.name}")
    return errors


def latest_run_dir(output_root: Path) -> Path:
    run_dirs = sorted(path for path in output_root.glob("run-*") if path.is_dir())
    if not run_dirs:
        raise SystemExit(f"no reconciliation run directories found under {output_root}")
    return run_dirs[-1]


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _markdown_counts(counts: dict[str, int]) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
