#!/usr/bin/env bash
set -euo pipefail

PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8081}"
REPORT_FILE="${REPORT_FILE:-reports/monitoring/ops1-required-metrics.md}"
REQUIRED_QUERIES=(
  "up{job=\"api\"} == 1"
  "up{job=\"node-exporter\"} == 1"
  "up{job=\"cadvisor\"} == 1"
  "up{job=\"postgres-exporter\"} == 1"
  "up{job=\"redis-exporter\"} == 1"
  "pg_up == 1"
  "redis_up == 1"
  "financial_http_requests_total"
  "node_cpu_seconds_total"
  "container_cpu_usage_seconds_total"
)
API_EXPOSITION_METRICS=(
  "financial_readiness_dependency_status"
  "financial_redis_fallback_total"
)

mkdir -p "$(dirname "${REPORT_FILE}")"

# Warm application metrics that are created by request handling/readiness checks.
curl -fsS "${API_BASE_URL}/health" >/dev/null || true
curl -fsS "${API_BASE_URL}/ready" >/dev/null || true
api_metrics="$(curl -fsS "${API_BASE_URL}/metrics" || true)"

# Allow Prometheus one scrape interval to collect warmed application metrics.
sleep "${PROMETHEUS_SCRAPE_WAIT_SECONDS:-6}"

python3 - "${PROMETHEUS_URL}" "${REPORT_FILE}" "${api_metrics}" "${#REQUIRED_QUERIES[@]}" "${REQUIRED_QUERIES[@]}" "${API_EXPOSITION_METRICS[@]}" <<'PY'
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

prometheus_url = sys.argv[1].rstrip("/")
report_path = Path(sys.argv[2])
api_metrics = sys.argv[3]
query_count = int(sys.argv[4])
queries = sys.argv[5 : 5 + query_count]
exposition_metrics = sys.argv[5 + query_count :]

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
for metric in queries:
    ok, note = query(metric)
    failed = failed or not ok
    rows.append((metric, "queryable", "PASS" if ok else "FAIL", note))

for metric in exposition_metrics:
    ok = metric in api_metrics
    failed = failed or not ok
    rows.append(
        (
            metric,
            "exposed by API /metrics",
            "PASS" if ok else "FAIL",
            "metric definition present" if ok else "not found in API /metrics",
        )
    )

lines = [
    "# Ops Phase 1 Required Metrics Check",
    "",
    f"- Date: {now}",
    f"- Tested Commit: {commit}",
    f"- Branch: {branch}",
    f"- Result: {'FAILED' if failed else 'PASSED'}",
    "",
    "> Note: The tested commit can differ from the final PR commit because evidence reports are generated before being committed.",
    "",
    "| Query | Expected | Status | Note |",
    "|---|---|---|---|",
]
for row in rows:
    lines.append(f"| `{row[0]}` | {row[1]} | {row[2]} | {row[3]} |")

report_path.write_text("\n".join(lines) + "\n")
print(f"Required metrics report written: {report_path}")
if failed:
    raise SystemExit(1)
PY
