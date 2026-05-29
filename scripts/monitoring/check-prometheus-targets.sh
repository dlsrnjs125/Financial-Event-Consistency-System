#!/usr/bin/env bash
set -euo pipefail

PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
REPORT_FILE="${REPORT_FILE:-reports/monitoring/ops1-prometheus-targets.md}"
REQUIRED_JOBS=("api" "node-exporter" "cadvisor" "postgres-exporter" "redis-exporter")
OPTIONAL_JOBS=("nginx-exporter")

mkdir -p "$(dirname "${REPORT_FILE}")"

tmp_json="$(mktemp)"
trap 'rm -f "${tmp_json}"' EXIT

if ! curl -fsS "${PROMETHEUS_URL}/api/v1/targets" -o "${tmp_json}"; then
  {
    echo "# Ops Phase 1 Prometheus Target Check"
    echo ""
    echo "- Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "- Prometheus URL: ${PROMETHEUS_URL}"
    echo "- Result: FAILED"
    echo ""
    echo "Prometheus target API is unavailable."
  } >"${REPORT_FILE}"
  echo "Prometheus target API is unavailable: ${PROMETHEUS_URL}"
  exit 1
fi

python3 - "${tmp_json}" "${REPORT_FILE}" "${REQUIRED_JOBS[*]}" "${OPTIONAL_JOBS[*]}" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

json_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
required = sys.argv[3].split()
optional = sys.argv[4].split()

payload = json.loads(json_path.read_text())
targets = payload.get("data", {}).get("activeTargets", [])
by_job: dict[str, list[dict]] = {}
for target in targets:
    job = target.get("labels", {}).get("job", "")
    if job:
        by_job.setdefault(job, []).append(target)

def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True).strip()
    except Exception:
        return "unknown"

commit = git_value(["git", "rev-parse", "--short", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

rows: list[tuple[str, str, str, str]] = []
failed = False
for job in required:
    job_targets = by_job.get(job, [])
    health_values = [t.get("health", "unknown") for t in job_targets]
    status = ",".join(health_values) if health_values else "missing"
    expected = "UP"
    note = ""
    if not job_targets:
        failed = True
        note = "target missing"
    elif any(value != "up" for value in health_values):
        failed = True
        note = "target not healthy"
    rows.append((job, expected, status, note))

for job in optional:
    job_targets = by_job.get(job, [])
    health_values = [t.get("health", "unknown") for t in job_targets]
    status = ",".join(health_values) if health_values else "not configured"
    rows.append((job, "Optional", status, "Ops Phase 2 candidate"))

lines = [
    "# Ops Phase 1 Prometheus Target Check",
    "",
    f"- Date: {now}",
    f"- Git Commit: {commit}",
    f"- Branch: {branch}",
    f"- Result: {'FAILED' if failed else 'PASSED'}",
    "",
    "| Target | Expected | Status | Note |",
    "|---|---|---|---|",
]
for row in rows:
    lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")

report_path.write_text("\n".join(lines) + "\n")
print(f"Prometheus target report written: {report_path}")
if failed:
    raise SystemExit(1)
PY
