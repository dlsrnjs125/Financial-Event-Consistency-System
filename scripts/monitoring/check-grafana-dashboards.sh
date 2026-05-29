#!/usr/bin/env bash
set -euo pipefail

GRAFANA_DIR="${GRAFANA_DIR:-infra/monitoring/grafana}"
REPORT_FILE="${REPORT_FILE:-reports/monitoring/ops1-grafana-provisioning.md}"
REQUIRED_DASHBOARDS=(
  "api-dashboard.json"
  "infra-dashboard.json"
  "postgres-dashboard.json"
  "redis-dashboard.json"
  "nginx-dashboard.json"
)

mkdir -p "$(dirname "${REPORT_FILE}")"

python3 - "${GRAFANA_DIR}" "${REPORT_FILE}" "${REQUIRED_DASHBOARDS[@]}" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

grafana_dir = Path(sys.argv[1])
report_path = Path(sys.argv[2])
dashboards = sys.argv[3:]
datasource = grafana_dir / "provisioning" / "datasources" / "datasource.yml"
dashboard_provider = grafana_dir / "provisioning" / "dashboards" / "dashboard.yml"
dashboard_dir = grafana_dir / "dashboards"

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

for path, expected in [
    (datasource, "datasource provisioning exists"),
    (dashboard_provider, "dashboard provider exists"),
]:
    if path.exists():
        rows.append((str(path), expected, "PASS", ""))
    else:
        failed = True
        rows.append((str(path), expected, "FAIL", "missing"))

for name in dashboards:
    path = dashboard_dir / name
    if not path.exists():
        failed = True
        rows.append((str(path), "valid dashboard JSON", "FAIL", "missing"))
        continue
    try:
        payload = json.loads(path.read_text())
        title = payload.get("title", "")
        panel_count = len(payload.get("panels", []))
    except Exception as exc:
        failed = True
        rows.append((str(path), "valid dashboard JSON", "FAIL", type(exc).__name__))
        continue
    if not title or panel_count < 1:
        failed = True
        rows.append((str(path), "title and at least one panel", "FAIL", "metadata missing"))
    else:
        rows.append((str(path), "title and at least one panel", "PASS", title))

lines = [
    "# Ops Phase 1 Grafana Provisioning Check",
    "",
    f"- Date: {now}",
    f"- Git Commit: {commit}",
    f"- Branch: {branch}",
    f"- Result: {'FAILED' if failed else 'PASSED'}",
    "",
    "| File | Expected | Status | Note |",
    "|---|---|---|---|",
]
for row in rows:
    lines.append(f"| `{row[0]}` | {row[1]} | {row[2]} | {row[3]} |")

report_path.write_text("\n".join(lines) + "\n")
print(f"Grafana provisioning report written: {report_path}")
if failed:
    raise SystemExit(1)
PY
