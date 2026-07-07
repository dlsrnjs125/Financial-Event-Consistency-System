#!/usr/bin/env python3
"""Manage PH4 recovery cases and quarantine records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.domain.recovery import QuarantineTargetType  # noqa: E402
from app.repositories.quarantine_repository import QuarantineRepository  # noqa: E402
from app.repositories.recovery_case_repository import (  # noqa: E402
    RecoveryCaseRepository,
)
from app.services.quarantine_service import QuarantineService  # noqa: E402
from app.services.recovery_case_service import RecoveryCaseService  # noqa: E402

DEFAULT_INCIDENTS_DIR = ROOT_DIR / "reports/incidents"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-from-analysis")
    create_parser.add_argument("--incident-dir", type=Path)
    create_parser.add_argument("--latest", action="store_true")

    subparsers.add_parser("list-cases")

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--case-id", required=True)
    approve_parser.add_argument("--approved-by", required=True)
    approve_parser.add_argument("--reason", default=None)

    reject_parser = subparsers.add_parser("reject")
    reject_parser.add_argument("--case-id", required=True)
    reject_parser.add_argument("--reason", default=None)

    quarantine_parser = subparsers.add_parser("quarantine")
    quarantine_parser.add_argument("--target-type", required=True)
    quarantine_parser.add_argument("--target-id", required=True)
    quarantine_parser.add_argument("--reason", required=True)
    quarantine_parser.add_argument("--activated-by", default="operator")

    release_parser = subparsers.add_parser("release-quarantine")
    release_parser.add_argument("--quarantine-id", required=True)
    release_parser.add_argument("--released-by", required=True)
    release_parser.add_argument("--reason", required=True)

    subparsers.add_parser("list-quarantines")

    args = parser.parse_args()
    with SessionLocal() as session:
        recovery_repository = RecoveryCaseRepository(session)
        quarantine_service = QuarantineService(QuarantineRepository(session))
        recovery_service = RecoveryCaseService(
            recovery_repository,
            quarantine_service=quarantine_service,
        )
        result = _handle(args, recovery_service, quarantine_service)
        session.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle(
    args: argparse.Namespace,
    recovery_service: RecoveryCaseService,
    quarantine_service: QuarantineService,
) -> dict[str, Any] | list[dict[str, Any]]:
    if args.command == "create-from-analysis":
        incident_dir = args.incident_dir
        if args.latest:
            incident_dir = _latest_incident_dir(DEFAULT_INCIDENTS_DIR)
        if incident_dir is None:
            raise SystemExit("--incident-dir or --latest is required")
        return _case_to_dict(recovery_service.create_from_analyzer_result(incident_dir))
    if args.command == "list-cases":
        return [_case_to_dict(case) for case in recovery_service.list_cases()]
    if args.command == "approve":
        return _case_to_dict(
            recovery_service.approve(args.case_id, args.approved_by, args.reason)
        )
    if args.command == "reject":
        return _case_to_dict(recovery_service.reject(args.case_id, args.reason))
    if args.command == "quarantine":
        quarantine = quarantine_service.create_quarantine(
            QuarantineTargetType(args.target_type),
            args.target_id,
            args.reason,
            args.activated_by,
        )
        return _quarantine_to_dict(quarantine)
    if args.command == "release-quarantine":
        quarantine = quarantine_service.release_quarantine(
            args.quarantine_id,
            args.released_by,
            args.reason,
        )
        return _quarantine_to_dict(quarantine)
    if args.command == "list-quarantines":
        return [
            _quarantine_to_dict(quarantine)
            for quarantine in quarantine_service.list_quarantines()
        ]
    raise SystemExit(f"unknown command: {args.command}")


def _latest_incident_dir(output_root: Path) -> Path:
    incident_dirs = sorted(path for path in output_root.glob("inc-*") if path.is_dir())
    if not incident_dirs:
        raise SystemExit(f"no incident directories found under {output_root}")
    return incident_dirs[-1]


def _case_to_dict(recovery_case: Any) -> dict[str, Any]:
    return {
        "case_id": recovery_case.case_id,
        "source_key": recovery_case.source_key,
        "case_type": recovery_case.case_type,
        "severity": recovery_case.severity,
        "current_status": recovery_case.current_status,
        "classification": recovery_case.classification,
        "source_incident_id": recovery_case.source_incident_id,
        "proposed_action": recovery_case.proposed_action,
        "approval_required": recovery_case.approval_required,
        "approved_by": recovery_case.approved_by,
        "action_attempt_id": recovery_case.action_attempt_id,
    }


def _quarantine_to_dict(quarantine: Any) -> dict[str, Any]:
    return {
        "quarantine_id": quarantine.quarantine_id,
        "target_type": quarantine.target_type,
        "target_id": quarantine.target_id,
        "active": quarantine.active,
        "source_incident_id": quarantine.source_incident_id,
    }


if __name__ == "__main__":
    raise SystemExit(main())
