#!/usr/bin/env bash
set -euo pipefail

GRAFANA_DIR="${GRAFANA_DIR:-infra/monitoring/grafana}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
REPORT_FILE="${REPORT_FILE:-reports/monitoring/ops1-grafana-provisioning.md}"
REQUIRED_DASHBOARDS=(
  "api-dashboard.json"
  "infra-dashboard.json"
  "postgres-dashboard.json"
  "redis-dashboard.json"
  "nginx-dashboard.json"
)

mkdir -p "$(dirname "${REPORT_FILE}")"

python3 - "${GRAFANA_DIR}" "${REPORT_FILE}" "${GRAFANA_URL}" "${GRAFANA_USER}" "${GRAFANA_PASSWORD}" "${REQUIRED_DASHBOARDS[@]}" <<'PY'
import base64
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

grafana_dir = Path(sys.argv[1])
report_path = Path(sys.argv[2])
grafana_url = sys.argv[3].rstrip("/")
grafana_user = sys.argv[4]
grafana_password = sys.argv[5]
dashboards = sys.argv[6:]
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

def get_json(path: str) -> tuple[bool, str]:
    request = urllib.request.Request(f"{grafana_url}{path}")
    credentials = f"{grafana_user}:{grafana_password}".encode("utf-8")
    request.add_header(
        "Authorization", "Basic " + base64.b64encode(credentials).decode("ascii")
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            json.loads(response.read().decode("utf-8"))
        return True, "loaded"
    except Exception as exc:
        return False, type(exc).__name__

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

for path, expected in [
    ("/api/health", "Grafana API health"),
    ("/api/datasources", "Grafana datasource loaded"),
    ("/api/search", "Grafana dashboards searchable"),
]:
    ok, note = get_json(path)
    if not ok:
        failed = True
    rows.append((f"{grafana_url}{path}", expected, "PASS" if ok else "FAIL", note))

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
