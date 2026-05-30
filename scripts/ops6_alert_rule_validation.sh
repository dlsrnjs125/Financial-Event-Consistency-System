#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULE_FILE="${ALERT_RULE_FILE:-${ROOT_DIR}/infra/prometheus/rules/financial_event_alerts.yml}"
REPORT_FILE="${OPS6_REPORT_FILE:-${ROOT_DIR}/reports/ops/ops6-alerting-incident-runbook.md}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
PROMETHEUS_API_CHECK="${PROMETHEUS_API_CHECK:-true}"
PROMTOOL_IMAGE="${PROMTOOL_IMAGE:-prom/prometheus:v2.54.1}"

required_alerts=(
    FinancialApiDown
    FinancialApiHighErrorRate
    FinancialApiHighLatencyP95
    FinancialRedisDown
    FinancialPostgresDown
    FinancialInvalidStateTransitionDetected
    FinancialReconciliationFailureDetected
)

log() {
    printf '[ops6] %s\n' "$*"
}

status_file_exists="FAIL"
status_yaml_parse="FAIL"
status_promtool="FAIL"
status_rule_load="SKIPPED"
required_alert_count="0"
prometheus_rule_load_note="Prometheus API check not attempted."

mkdir -p "$(dirname "${REPORT_FILE}")"

if [ -f "${RULE_FILE}" ]; then
    status_file_exists="PASS"
fi

yaml_output="$(
    python3 - "${RULE_FILE}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("missing")
    raise SystemExit(1)

text = path.read_text()
try:
    import yaml  # type: ignore

    payload = yaml.safe_load(text)
    groups = payload.get("groups", []) if isinstance(payload, dict) else []
    alerts = [
        rule.get("alert")
        for group in groups
        for rule in group.get("rules", [])
        if isinstance(rule, dict) and rule.get("alert")
    ]
except Exception:
    groups = re.findall(r"^\s*-\s+name:\s*(\S+)", text, re.MULTILINE)
    alerts = re.findall(r"^\s*-\s+alert:\s*([A-Za-z0-9_]+)", text, re.MULTILINE)

if not groups or not alerts:
    print("groups_or_alerts_missing")
    raise SystemExit(1)

print("alerts=" + ",".join(alerts))
PY
)"
if [ -n "${yaml_output}" ]; then
    status_yaml_parse="PASS"
fi

alert_names="$(printf '%s\n' "${yaml_output}" | awk -F= '$1=="alerts"{print $2}')"
if [ -n "${alert_names}" ]; then
    required_alert_count="$(printf '%s\n' "${alert_names}" | tr ',' '\n' | sed '/^$/d' | wc -l | tr -d '[:space:]')"
else
    required_alert_count="0"
fi

missing_alerts=()
for alert_name in "${required_alerts[@]}"; do
    if ! printf '%s' "${alert_names}" | tr ',' '\n' | grep -qx "${alert_name}"; then
        missing_alerts+=("${alert_name}")
    fi
done

run_promtool() {
    if command -v promtool >/dev/null 2>&1; then
        promtool check rules "${RULE_FILE}"
        return
    fi

    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        docker run --rm \
            -v "${ROOT_DIR}:/work:ro" \
            --entrypoint promtool \
            "${PROMTOOL_IMAGE}" \
            check rules "/work/${RULE_FILE#"${ROOT_DIR}/"}"
        return
    fi

    echo "promtool is unavailable and Docker is not running." >&2
    return 1
}

if run_promtool >/tmp/ops6-promtool.out 2>/tmp/ops6-promtool.err; then
    status_promtool="PASS"
else
    status_promtool="FAIL"
fi

if [ "${PROMETHEUS_API_CHECK}" = "false" ]; then
    status_rule_load="SKIPPED"
    prometheus_rule_load_note="Skipped by PROMETHEUS_API_CHECK=false."
else
    tmp_rules="$(mktemp)"
    trap 'rm -f "${tmp_rules}"' EXIT
    if curl -fsS "${PROMETHEUS_URL}/api/v1/rules" -o "${tmp_rules}" >/dev/null 2>&1; then
        if python3 - "${tmp_rules}" "${required_alerts[@]}" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())
required = set(sys.argv[2:])
loaded: set[str] = set()

for group in payload.get("data", {}).get("groups", []):
    for rule in group.get("rules", []):
        name = rule.get("name")
        if rule.get("type") == "alerting" and name:
            loaded.add(name)

missing = sorted(required - loaded)
if missing:
    print("missing=" + ",".join(missing))
    raise SystemExit(1)
print("loaded=" + ",".join(sorted(required)))
PY
        then
            status_rule_load="PASS"
            prometheus_rule_load_note="Required alert rules are loaded in Prometheus."
        else
            status_rule_load="FAIL"
            prometheus_rule_load_note="Prometheus API responded, but required alert rules were missing."
        fi
    else
        status_rule_load="FAIL"
        prometheus_rule_load_note="Prometheus API was unavailable at ${PROMETHEUS_URL} while PROMETHEUS_API_CHECK=true."
    fi
fi

overall_result="PASS"
if [ "${status_file_exists}" != "PASS" ] ||
   [ "${status_yaml_parse}" != "PASS" ] ||
   [ "${status_promtool}" != "PASS" ] ||
   [ "${#missing_alerts[@]}" -ne 0 ] ||
   [ "${status_rule_load}" = "FAIL" ]; then
    overall_result="FAIL"
fi

inventory_rows="$(
    python3 - "${RULE_FILE}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
blocks = re.split(r"\n\s*-\s+alert:\s*", text)
rows: list[str] = []
for block in blocks[1:]:
    lines = block.splitlines()
    alert = lines[0].strip()
    severity = "unknown"
    component = "unknown"
    runbook = "unknown"
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("severity:"):
            severity = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("component:"):
            component = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("runbook:"):
            runbook = stripped.split(":", 1)[1].strip().strip('"')
    rows.append(f"| {alert} | {severity} | {component} | `{runbook}` |")
print("\n".join(rows))
PY
)"

started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
cat >"${REPORT_FILE}" <<EOF
# Ops Phase 6 - Alerting & Incident Response Runbook

## 실행 목적

Prometheus Alert Rule과 Incident Response Runbook을 구성하고, API/Redis/PostgreSQL/정합성 장애의 탐지 기준과 운영자 1차 대응 기준을 evidence로 남긴다.

## 검증 환경

| 항목 | 값 |
|---|---|
| 검증 시각 UTC | \`${started_at}\` |
| Alert rule file | \`${RULE_FILE#"${ROOT_DIR}/"}\` |
| Prometheus URL | \`${PROMETHEUS_URL}\` |
| Prometheus API check | \`${PROMETHEUS_API_CHECK}\` |
| Promtool image | \`${PROMTOOL_IMAGE}\` |

## Alert Rule 검증 결과

| 항목 | 결과 |
|---|---|
| Alert rule file exists | ${status_file_exists} |
| YAML parse | ${status_yaml_parse} |
| promtool check rules | ${status_promtool} |
| Prometheus rule load check | ${status_rule_load} |
| Required alert count | ${required_alert_count} |
| Overall result | ${overall_result} |

Prometheus rule load note: ${prometheus_rule_load_note}

## Required Alert Inventory

| Alert | Severity | Component | Runbook |
|---|---|---|---|
${inventory_rows}

## CI 검증 범위

CI는 alert rule 파일 존재, 스크립트 문법, YAML 구조, \`promtool check rules\`, report 주요 문구를 검증한다.
Prometheus API rule load check는 runner timing과 monitoring stack 기동 비용 때문에 CI에서는 \`PROMETHEUS_API_CHECK=false\`로 SKIPPED를 허용한다.
커밋된 local evidence report는 \`make ops6-demo\`로 생성하며, 이 경우 Prometheus rule load check가 PASS여야 한다.

## Local 검증 범위

로컬에서는 \`make ops6-demo\`로 monitoring stack을 기동한 뒤 Prometheus API에서 required alert rule load 여부까지 확인한다.
\`PROMETHEUS_API_CHECK=true\` 상태에서 Prometheus API 호출이 실패하면 drill은 FAIL로 종료한다.

## 운영상 한계와 보완 전략

- Slack/PagerDuty/Alertmanager 실연동은 이번 Phase에서 제외한다.
- Redis down은 PostgreSQL 기준 최종 정합성 실패가 아니므로 warning으로 분류한다.
- PostgreSQL down은 Source of Truth 장애이므로 critical로 분류한다.
- consistency violation은 availability 장애보다 더 높은 금융 도메인 위험으로 취급한다.
- reconciliation failure는 counter의 전체 누적값이 아니라 최근 5분 증가량으로 감지한다. 현재 진행 중인 장애 상태를 표현하려면 후속 Phase에서 active gauge를 추가한다.
- Ops6 alert rule의 canonical source는 \`infra/prometheus/rules/financial_event_alerts.yml\`이다. Compose 환경에 따라 Prometheus 컨테이너 내부 경로만 다르게 mount한다.

## Troubleshooting

- Prometheus API rule load check가 FAIL이면 monitoring stack이 실행 중인지, \`make ops6-up\`을 먼저 실행했는지 확인한다.
- Prometheus API rule load check가 SKIPPED이면 CI처럼 \`PROMETHEUS_API_CHECK=false\`로 실행된 것이다.
- \`promtool check rules\`가 실패하면 alert expression metric 이름과 label 이름이 현재 \`backend/app/observability/metrics.py\`와 일치하는지 확인한다.
- 현재 duplicate ledger count와 idempotency violation count는 report/SQL evidence로 검증하며, 직접 gauge metric은 후속 Phase에서 추가한다.

## README에 기록할 문장

Ops Phase 6에서는 Prometheus Alert Rule과 Incident Response Runbook을 구성하고, API/Redis/PostgreSQL/정합성 장애의 탐지 기준과 1차 대응 절차를 evidence report로 남긴다.
EOF

log "Ops6 alerting report written: ${REPORT_FILE}"

if [ "${overall_result}" != "PASS" ]; then
    if [ -s /tmp/ops6-promtool.err ]; then
        cat /tmp/ops6-promtool.err >&2
    fi
    exit 1
fi
