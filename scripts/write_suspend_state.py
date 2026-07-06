#!/usr/bin/env python3
"""Manage local runtime write-suspend state."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_FILE = ROOT_DIR / "reports/runtime/write-suspend-state.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    enable_parser = subparsers.add_parser("enable")
    enable_parser.add_argument("--reason", required=True)
    enable_parser.add_argument("--activated-by", default="operator")
    enable_parser.add_argument("--source", default="cli")
    enable_parser.add_argument("--retry-after-seconds", type=int)
    enable_parser.add_argument("--run-id")

    disable_parser = subparsers.add_parser("disable")
    disable_parser.add_argument("--reason", required=True)
    disable_parser.add_argument("--resumed-by", default="operator")

    subparsers.add_parser("status")

    args = parser.parse_args()
    state_file = Path(os.getenv("WRITE_SUSPEND_STATE_FILE", str(DEFAULT_STATE_FILE)))
    retry_after_seconds = int(os.getenv("WRITE_SUSPEND_RETRY_AFTER_SECONDS", "30"))

    if args.command == "enable":
        state = {
            "active": True,
            "reason": args.reason,
            "activated_at": _utc_now(),
            "activated_by": args.activated_by,
            "retry_after_seconds": args.retry_after_seconds or retry_after_seconds,
            "source": args.source,
            "run_id": args.run_id or f"write-suspend-{uuid4().hex[:12]}",
            "resumed_at": None,
            "resumed_by": None,
            "resume_reason": None,
        }
        _write_state(state_file, state)
    elif args.command == "disable":
        previous = _read_state(state_file, retry_after_seconds)
        state = {
            **previous,
            "active": False,
            "resumed_at": _utc_now(),
            "resumed_by": args.resumed_by,
            "resume_reason": args.reason,
        }
        _write_state(state_file, state)
    else:
        state = _read_state(state_file, retry_after_seconds)

    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def _read_state(state_file: Path, retry_after_seconds: int) -> dict[str, object]:
    if not state_file.exists():
        return {
            "active": False,
            "reason": "none",
            "activated_at": None,
            "activated_by": None,
            "retry_after_seconds": retry_after_seconds,
            "source": "cli",
            "run_id": "none",
            "resumed_at": None,
            "resumed_by": None,
            "resume_reason": None,
        }
    return json.loads(state_file.read_text(encoding="utf-8"))


def _write_state(state_file: Path, state: dict[str, object]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
