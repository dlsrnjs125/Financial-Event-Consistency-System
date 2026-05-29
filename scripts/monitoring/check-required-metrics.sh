#!/usr/bin/env bash
set -euo pipefail

PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
REPORT_FILE="${REPORT_FILE:-reports/monitoring/ops1-required-metrics.md}"
REQUIRED_METRICS=(
  "up"
  "process_cpu_seconds_total"
  "node_cpu_seconds_total"
  "container_cpu_usage_seconds_total"
  "pg_up"
  "redis_up"
)

mkdir -p "$(dirname "${REPORT_FILE}")"

python3 - "${PROMETHEUS_URL}" "${REPORT_FILE}" "${REQUIRED_METRICS[@]}" <<'PY'
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

prometheus_url = sys.argv[1].rstrip("/")
report_path = Path(sys.argv[2])
metrics = sys.argv[3:]

def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True).strip()
    except Exception:
        return "unknown"

def query(metric: str) -> tuple[bool, str]:
    encoded = urllib.parse.urlencode({"query": metric})
    url = f"{prometheus_url}/api/v1/query?{encoded}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return False, f"query failed: {type(exc).__name__}"

    if payload.get("status") != "success":
        return False, payload.get("error", "query did not succeed")

    result = payload.get("data", {}).get("result", [])
    if not result:
        return False, "no series returned"

    return True, f"{len(result)} series"

commit = git_value(["git", "rev-parse", "--short", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

rows = []
failed = False
for metric in metrics:
    ok, note = query(metric)
    failed = failed or not ok
    rows.append((metric, "queryable", "PASS" if ok else "FAIL", note))

lines = [
    "# Ops Phase 1 Required Metrics Check",
    "",
    f"- Date: {now}",
    f"- Git Commit: {commit}",
    f"- Branch: {branch}",
    f"- Result: {'FAILED' if failed else 'PASSED'}",
    "",
    "| Metric | Expected | Status | Note |",
    "|---|---|---|---|",
]
for row in rows:
    lines.append(f"| `{row[0]}` | {row[1]} | {row[2]} | {row[3]} |")

report_path.write_text("\n".join(lines) + "\n")
print(f"Required metrics report written: {report_path}")
if failed:
    raise SystemExit(1)
PY
