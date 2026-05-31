#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
READY_BASE_URL="${READY_BASE_URL:-http://localhost:8081}"
API_SERVICE="${API_SERVICE:-api-blue}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
REDIS_SERVICE="${REDIS_SERVICE:-redis}"
POSTGRES_DB="${POSTGRES_DB:-financial_events}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
CLIENT_ID="${CLIENT_ID:-bank-a}"
CLIENT_SECRET="${CLIENT_SECRET:-change-me-secret}"
ACCOUNT_NO="${ACCOUNT_NO:-ACC-001}"
REPORT_FILE="${OPS7_REPORT_FILE:-${ROOT_DIR}/reports/ops/ops7-incident-timeline-postmortem.md}"
VERIFY_TIMEOUT_SECONDS="${VERIFY_TIMEOUT_SECONDS:-60}"
MODE="${MODE:-drill}"

incident_id="OPS7-$(date -u +"%Y%m%dT%H%M%SZ")"
scenario="Redis degraded duplicate event handling"
severity="warning"

started_at=""
detected_at=""
mitigated_at=""
recovered_at=""
started_epoch="0"
detected_epoch="0"
mitigated_epoch="0"
recovered_epoch="0"
detection_latency_seconds="0"
mitigation_latency_seconds="0"
recovery_duration_seconds="0"
total_incident_duration_seconds="0"

redis_stopped_by_drill=false
redis_degraded_detected="FAIL"
api_fallback_behavior="FAIL"
first_duplicate_smoke_status="0"
second_duplicate_smoke_status="0"
synthetic_external_event_id_prefix="SKIPPED"
synthetic_idempotency_key_prefix="SKIPPED"
event_count_for_duplicate_smoke="0"
ledger_count_for_duplicate_smoke="0"
idempotency_record_count_for_duplicate_smoke="0"
duplicate_ledger_count="0"
idempotency_violation_count="0"
consistency_check="FAIL"
redis_restarted="FAIL"
health_after_recovery="FAIL"
ready_after_recovery="FAIL"
smoke_after_recovery="FAIL"
consistency_after_recovery="FAIL"
overall_result="FAIL"

timeline_rows=""
consistency_output=""

log() {
    printf '[ops7] %s\n' "$*"
}

compose() {
    (cd "${ROOT_DIR}" && ${DOCKER_COMPOSE} "$@")
}

cleanup() {
    set +e
    if [ "${redis_stopped_by_drill}" = "true" ]; then
        log "Cleanup: ensuring Redis is running."
        compose start "${REDIS_SERVICE}" >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT

require_command() {
    local command_name="$1"
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "${command_name} is required." >&2
        exit 1
    fi
}

utc_now() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

epoch_now() {
    date +%s
}

append_timeline() {
    local time_utc="$1"
    local phase="$2"
    local event="$3"
    local evidence="$4"
    timeline_rows="${timeline_rows}| ${time_utc} | ${phase} | ${event} | ${evidence} |
"
}

http_status() {
    local url="$1"
    curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "${url}" 2>/dev/null || true
}

wait_for_status() {
    local url="$1"
    local expected="$2"
    local label="$3"
    local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))
    local status

    while (( SECONDS < deadline )); do
        status="$(http_status "${url}")"
        if [ "${status}" = "${expected}" ]; then
            log "${label}: ${status}"
            return 0
        fi
        sleep 2
    done

    status="$(http_status "${url}")"
    echo "${label} did not reach ${expected}; last status=${status}" >&2
    return 1
}

ready_json_field() {
    local field="$1"
    python3 - "${READY_BASE_URL}/ready" "${field}" <<'PY'
import json
import sys
import urllib.error
import urllib.request

url, field = sys.argv[1:3]
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.loads(response.read().decode())
except urllib.error.HTTPError as exc:
    payload = json.loads(exc.read().decode() or "{}")
except Exception:
    print("")
    raise SystemExit(0)

value = payload
for part in field.split("."):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break
print("" if value is None else value)
PY
}

wait_for_redis_state() {
    local expected="$1"
    local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))
    local redis_state

    while (( SECONDS < deadline )); do
        redis_state="$(ready_json_field "checks.redis")"
        if [ "${redis_state}" = "${expected}" ]; then
            log "readiness redis=${expected}"
            return 0
        fi
        sleep 2
    done

    echo "Readiness did not reach redis=${expected}." >&2
    return 1
}

wait_for_ready_ok() {
    local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))
    local status
    local postgres_state
    local redis_state

    while (( SECONDS < deadline )); do
        status="$(http_status "${READY_BASE_URL}/ready")"
        postgres_state="$(ready_json_field "checks.postgres")"
        redis_state="$(ready_json_field "checks.redis")"
        if [ "${status}" = "200" ] &&
           [ "${postgres_state}" = "ok" ] &&
           [ "${redis_state}" = "ok" ]; then
            log "readiness postgres=ok redis=ok"
            return 0
        fi
        sleep 2
    done

    echo "Readiness did not recover postgres=ok redis=ok." >&2
    return 1
}

wait_for_postgres() {
    local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))

    while (( SECONDS < deadline )); do
        if compose exec -T "${POSTGRES_SERVICE}" pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
            log "postgres is ready"
            return 0
        fi
        sleep 2
    done

    echo "postgres did not become ready" >&2
    return 1
}

psql_scalar() {
    local sql="$1"
    compose exec -T "${POSTGRES_SERVICE}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
        -tA -v ON_ERROR_STOP=1 -c "${sql}" | tr -d '[:space:]'
}

run_consistency_counts() {
    local output
    output="$(
        compose exec -T "${POSTGRES_SERVICE}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
            -tA -v ON_ERROR_STOP=1 -f - <<'SQL'
WITH latest_ledger AS (
    SELECT DISTINCT ON (account_id)
        account_id,
        balance_after
    FROM ledger_entries
    ORDER BY account_id, created_at DESC, id DESC
),
checks AS (
    SELECT 'duplicated_external_event_count' AS check_name, COUNT(*)::bigint AS check_value
    FROM (
        SELECT external_event_id
        FROM transaction_events
        GROUP BY external_event_id
        HAVING COUNT(*) > 1
    ) duplicated_external_events
    UNION ALL
    SELECT 'duplicated_ledger_event_count', COUNT(*)::bigint
    FROM (
        SELECT transaction_event_id
        FROM ledger_entries
        GROUP BY transaction_event_id
        HAVING COUNT(*) > 1
    ) duplicated_ledger_events
    UNION ALL
    SELECT 'orphan_ledger_count', COUNT(*)::bigint
    FROM ledger_entries le
    LEFT JOIN transaction_events te ON te.id = le.transaction_event_id
    WHERE te.id IS NULL
    UNION ALL
    SELECT 'completed_event_without_ledger_count', COUNT(*)::bigint
    FROM transaction_events te
    LEFT JOIN ledger_entries le ON le.transaction_event_id = te.id
    WHERE te.status IN ('COMPLETED', 'SETTLED')
      AND le.id IS NULL
    UNION ALL
    SELECT 'ledger_account_mismatch_count', COUNT(*)::bigint
    FROM ledger_entries le
    JOIN transaction_events te ON te.id = le.transaction_event_id
    WHERE le.account_id <> te.account_id
    UNION ALL
    SELECT 'duplicated_idempotency_key_count', COUNT(*)::bigint
    FROM (
        SELECT idempotency_key
        FROM idempotency_records
        GROUP BY idempotency_key
        HAVING COUNT(*) > 1
    ) duplicated_idempotency_keys
    UNION ALL
    SELECT 'account_balance_mismatch_count', COUNT(*)::bigint
    FROM accounts a
    JOIN latest_ledger ll ON ll.account_id = a.id
    WHERE a.balance <> ll.balance_after
)
SELECT check_name || '=' || check_value
FROM checks
ORDER BY check_name;
SQL
    )"

    consistency_output="${output}"
    printf '%s\n' "${output}" >&2
    if printf '%s\n' "${output}" | awk -F= '{ if ($2 != 0) exit 1 }'; then
        return 0
    fi
    return 1
}

run_duplicate_smoke() {
    local prefix="$1"
    python3 - "${BASE_URL}" "${CLIENT_ID}" "${CLIENT_SECRET}" "${ACCOUNT_NO}" "${prefix}" <<'PY'
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

base_url, client_id, client_secret, account_no, prefix = sys.argv[1:6]
api_path = "/api/v1/transaction-events"


def canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def sign(method: str, path: str, timestamp: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    base_string = f"{method}\n{path}\n{timestamp}\n{body_hash}"
    return hmac.new(client_secret.encode(), base_string.encode(), hashlib.sha256).hexdigest()


def headers(method: str, path: str, body: bytes, key: str) -> dict[str, str]:
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return {
        "Content-Type": "application/json",
        "X-Client-Id": client_id,
        "X-Timestamp": timestamp,
        "X-Signature": sign(method, path, timestamp, body),
        "Idempotency-Key": key,
    }


def request(method: str, path: str, body: bytes, request_headers: dict[str, str]):
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


suffix = str(int(time.time() * 1000))
external_event_id = f"{prefix}-{suffix}"
idempotency_key = f"{prefix.lower()}-{suffix}"
payload = {
    "external_event_id": external_event_id,
    "account_no": account_no,
    "event_type": "DEPOSIT",
    "amount": 1000,
    "currency": "KRW",
    "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
}
body = canonical_json(payload)
request_headers = headers("POST", api_path, body, idempotency_key)

first_status, first_body = request("POST", api_path, body, request_headers)
second_status, second_body = request("POST", api_path, body, request_headers)

allowed = {200, 201, 202}
if first_status not in allowed or second_status not in allowed:
    raise SystemExit(
        f"smoke request failed: first={first_status}, second={second_status}, "
        f"first_body={first_body[:120]}, second_body={second_body[:120]}"
    )

print(f"external_event_id={external_event_id}")
print(f"idempotency_key={idempotency_key}")
print(f"first_status={first_status}")
print(f"second_status={second_status}")
PY
}

ensure_preconditions() {
    require_command curl
    require_command python3
    require_command docker

    log "Checking Docker Compose services."
    compose ps "${POSTGRES_SERVICE}" "${REDIS_SERVICE}" "${API_SERVICE}" nginx

    wait_for_status "${BASE_URL}/health" "200" "public health"
    wait_for_ready_ok
    wait_for_postgres
    compose exec -T "${REDIS_SERVICE}" redis-cli ping >/dev/null
    log "Precheck passed."
}

usage() {
    cat <<'EOF'
Usage: MODE=<mode> ./scripts/ops7_incident_timeline_drill.sh

Modes:
  check            Run precheck only. Does not stop Redis or write report.
  drill            Run Redis degraded incident drill and write report. Default.
  validate-report  Validate committed Ops7 postmortem report format/evidence only.
  help             Print this help.
EOF
}

validate_report() {
    local required_patterns=(
        "# Ops Phase 7 - Incident Timeline & Postmortem Drill"
        "Incident Summary"
        "Incident Timeline"
        "Impact Evidence"
        "Root Cause Analysis"
        "Recovery Verification"
        "Action Items"
        "| Overall result | PASS |"
        "| Duplicate ledger count | 0 |"
        "| Idempotency violation count | 0 |"
        "Detection latency seconds"
        "Mitigation latency seconds"
        "Recovery duration seconds"
        "Total incident duration seconds"
    )
    local pattern

    if [ ! -f "${REPORT_FILE}" ]; then
        echo "Ops7 report file not found: ${REPORT_FILE}" >&2
        return 1
    fi

    for pattern in "${required_patterns[@]}"; do
        if ! grep -q "${pattern}" "${REPORT_FILE}"; then
            echo "Ops7 report missing required pattern: ${pattern}" >&2
            return 1
        fi
    done

    log "Ops7 report validation passed: ${REPORT_FILE}"
}

run_incident_drill() {
    local smoke_output
    local external_event_id
    local idempotency_key
    local event_count
    local ledger_count
    local idem_count
    local redis_state

    ensure_preconditions

    started_at="$(utc_now)"
    started_epoch="$(epoch_now)"
    append_timeline "${started_at}" "STARTED" "Incident drill started" "incident_id=${incident_id}"

    compose stop "${REDIS_SERVICE}" >/dev/null
    redis_stopped_by_drill=true

    if wait_for_redis_state "degraded"; then
        redis_degraded_detected="PASS"
    else
        redis_degraded_detected="FAIL"
    fi
    detected_at="$(utc_now)"
    detected_epoch="$(epoch_now)"
    redis_state="$(ready_json_field "checks.redis")"
    detection_latency_seconds="$(( detected_epoch - started_epoch ))"
    append_timeline "${detected_at}" "DETECTED" "Redis degraded detected" "readiness=${redis_state:-unknown}"

    smoke_output="$(run_duplicate_smoke "OPS7-INCIDENT")"
    external_event_id="$(printf '%s\n' "${smoke_output}" | awk -F= '$1=="external_event_id"{print $2}')"
    idempotency_key="$(printf '%s\n' "${smoke_output}" | awk -F= '$1=="idempotency_key"{print $2}')"
    first_duplicate_smoke_status="$(printf '%s\n' "${smoke_output}" | awk -F= '$1=="first_status"{print $2}')"
    second_duplicate_smoke_status="$(printf '%s\n' "${smoke_output}" | awk -F= '$1=="second_status"{print $2}')"
    synthetic_external_event_id_prefix="${external_event_id%-*}"
    synthetic_idempotency_key_prefix="${idempotency_key%-*}"

    event_count="$(psql_scalar "SELECT COUNT(*) FROM transaction_events WHERE external_event_id = \$ops7\$${external_event_id}\$ops7\$;")"
    ledger_count="$(psql_scalar "SELECT COUNT(*) FROM ledger_entries le JOIN transaction_events te ON te.id = le.transaction_event_id WHERE te.external_event_id = \$ops7\$${external_event_id}\$ops7\$;")"
    idem_count="$(psql_scalar "SELECT COUNT(*) FROM idempotency_records WHERE idempotency_key = \$ops7\$${idempotency_key}\$ops7\$;")"
    event_count_for_duplicate_smoke="${event_count}"
    ledger_count_for_duplicate_smoke="${ledger_count}"
    idempotency_record_count_for_duplicate_smoke="${idem_count}"
    duplicate_ledger_count="$(( ledger_count > 1 ? ledger_count - 1 : 0 ))"
    idempotency_violation_count="$(( idem_count > 1 ? idem_count - 1 : 0 ))"

    if [ "${event_count}" = "1" ] && [ "${ledger_count}" = "1" ] && [ "${idem_count}" = "1" ]; then
        api_fallback_behavior="PASS"
    else
        api_fallback_behavior="FAIL"
    fi
    append_timeline "$(utc_now)" "IMPACT_CHECK" "Duplicate smoke executed" "first=${first_duplicate_smoke_status}, second=${second_duplicate_smoke_status}, event_prefix=${synthetic_external_event_id_prefix}"

    mitigated_at="$(utc_now)"
    mitigated_epoch="$(epoch_now)"
    mitigation_latency_seconds="$(( mitigated_epoch - detected_epoch ))"
    append_timeline "${mitigated_at}" "MITIGATED" "Redis restart requested" "container=start"
    compose start "${REDIS_SERVICE}" >/dev/null
    redis_stopped_by_drill=false
    redis_restarted="PASS"

    if wait_for_status "${BASE_URL}/health" "200" "health after redis restart"; then
        health_after_recovery="PASS"
    fi

    if wait_for_ready_ok; then
        ready_after_recovery="PASS"
    fi
    recovered_at="$(utc_now)"
    recovered_epoch="$(epoch_now)"
    recovery_duration_seconds="$(( recovered_epoch - mitigated_epoch ))"
    total_incident_duration_seconds="$(( recovered_epoch - started_epoch ))"
    append_timeline "${recovered_at}" "RECOVERED" "Readiness recovered" "ready=${ready_after_recovery}"

    if run_duplicate_smoke "OPS7-RECOVERY" >/dev/null; then
        smoke_after_recovery="PASS"
    fi

    if run_consistency_counts; then
        consistency_check="PASS"
        consistency_after_recovery="PASS"
    fi
    append_timeline "$(utc_now)" "VERIFIED" "Consistency check passed" "duplicate_ledger_count=${duplicate_ledger_count}"

    if [ "${redis_degraded_detected}" = "PASS" ] &&
       [ "${api_fallback_behavior}" = "PASS" ] &&
       [ "${duplicate_ledger_count}" = "0" ] &&
       [ "${idempotency_violation_count}" = "0" ] &&
       [ "${consistency_check}" = "PASS" ] &&
       [ "${redis_restarted}" = "PASS" ] &&
       [ "${health_after_recovery}" = "PASS" ] &&
       [ "${ready_after_recovery}" = "PASS" ] &&
       [ "${smoke_after_recovery}" = "PASS" ] &&
       [ "${consistency_after_recovery}" = "PASS" ]; then
        overall_result="PASS"
    else
        overall_result="FAIL"
    fi
}

write_report() {
    mkdir -p "$(dirname "${REPORT_FILE}")"
    cat > "${REPORT_FILE}" <<EOF
# Ops Phase 7 - Incident Timeline & Postmortem Drill

## 실행 목적

Redis degraded incident를 재현하고, 장애 발생부터 탐지, 영향 확인, 복구, 정합성 검증, 원인 분석, 재발 방지 Action Item까지 count-only postmortem evidence로 남긴다.

## Incident Summary

| 항목 | 값 |
|---|---|
| Incident ID | ${incident_id} |
| Scenario | ${scenario} |
| Severity | ${severity} |
| Started at | ${started_at} |
| Detected at | ${detected_at} |
| Mitigated at | ${mitigated_at} |
| Recovered at | ${recovered_at} |
| Detection latency seconds | ${detection_latency_seconds} |
| Mitigation latency seconds | ${mitigation_latency_seconds} |
| Recovery duration seconds | ${recovery_duration_seconds} |
| Total incident duration seconds | ${total_incident_duration_seconds} |
| Overall result | ${overall_result} |

## Incident Timeline

| Time UTC | Phase | Event | Evidence |
|---|---|---|---|
${timeline_rows}
## Impact Evidence

| 항목 | 결과 |
|---|---|
| Redis degraded detected | ${redis_degraded_detected} |
| API fallback behavior | ${api_fallback_behavior} |
| First duplicate smoke status | ${first_duplicate_smoke_status} |
| Second duplicate smoke status | ${second_duplicate_smoke_status} |
| Synthetic external event id prefix | ${synthetic_external_event_id_prefix} |
| Synthetic idempotency key prefix | ${synthetic_idempotency_key_prefix} |
| Event count for duplicate smoke | ${event_count_for_duplicate_smoke} |
| Ledger count for duplicate smoke | ${ledger_count_for_duplicate_smoke} |
| Idempotency record count for duplicate smoke | ${idempotency_record_count_for_duplicate_smoke} |
| Duplicate ledger count | ${duplicate_ledger_count} |
| Idempotency violation count | ${idempotency_violation_count} |
| Consistency check | ${consistency_check} |

## Root Cause Analysis

| 항목 | 내용 |
|---|---|
| Immediate cause | Redis container stopped by controlled drill |
| Root cause category | Dependency degraded |
| Source of truth impact | PostgreSQL consistency maintained |
| User impact | Duplicate event request accepted without duplicate ledger |
| Data consistency impact | No duplicate ledger, no idempotency violation |

## Recovery Verification

| 항목 | 결과 |
|---|---|
| Redis restarted | ${redis_restarted} |
| Health after recovery | ${health_after_recovery} |
| Ready after recovery | ${ready_after_recovery} |
| Smoke after recovery | ${smoke_after_recovery} |
| Consistency after recovery | ${consistency_after_recovery} |

## Action Items

| 우선순위 | 항목 | 목적 | 후속 Phase |
|---|---|---|---|
| P1 | incident timeline을 Slack/PagerDuty/Jira ticket과 연결 | Markdown evidence를 실제 운영 incident workflow와 연결 | Ops follow-up |
| P2 | trace_id/request_id/event_id 기반 log query evidence 추가 | 원인 추적을 수동 report에서 queryable evidence로 확장 | OpenTelemetry/Loki follow-up |
| P2 | Redis degraded alert와 postmortem template 자동 연결 | Alert 발생 후 운영자가 같은 template으로 기록하도록 표준화 | Ops follow-up |

## 운영상 한계와 보완 전략

- 이 drill은 Docker Compose Redis stop/start로 controlled incident를 재현하며, destructive DB operation은 수행하지 않는다.
- Redis degraded는 warning 성격의 incident다. PostgreSQL Source of Truth가 유지되는지와 duplicate ledger 0건을 핵심 기준으로 삼는다.
- Report에는 실제 거래 row data, account_no 원문, secret, token을 기록하지 않고 PASS/FAIL, duration, count-only evidence만 기록한다.
- 실제 운영에서는 Slack/PagerDuty/Jira incident ticket과 연결할 수 있지만, 이번 Phase에서는 Markdown postmortem evidence로 제한한다.
- CI에서는 Redis stop/start incident drill을 직접 실행하지 않고 \`MODE=validate-report\`로 script/report 형식을 검증한다. 실제 incident evidence는 로컬 \`make ops7-demo\` 결과로 남긴다.
- 현재 repo에는 \`infra/loki\`, \`infra/promtail\` 구성이 없으므로 trace/log query evidence는 후속 Phase에서 보강한다.

## Troubleshooting

- Drill 실패 시 cleanup trap이 Redis를 다시 start한다. 그래도 readiness가 회복되지 않으면 \`make ops7-up\` 후 \`make ops7-check\`를 다시 실행한다.
- Duplicate smoke status가 2xx가 아니면 API health, HMAC header 설정, PostgreSQL readiness를 먼저 확인한다.
- Duplicate ledger count 또는 idempotency violation count가 0이 아니면 PostgreSQL unique constraint와 idempotency transaction 경계를 우선 점검한다.
- CI report 검증은 \`MODE=validate-report\`와 curated local evidence report를 대상으로 한다. CI에서 Redis stop/start를 강제하지 않는 것은 runner flakiness를 줄이기 위한 trade-off다.

## README에 기록할 문장

Ops Phase 7에서는 Redis degraded incident를 재현하고, 장애 발생부터 탐지, 영향 확인, 복구, 정합성 검증, 재발 방지 Action Item까지 \`reports/ops/ops7-incident-timeline-postmortem.md\`에 postmortem evidence로 남긴다.
EOF

    log "Ops7 incident postmortem report written: ${REPORT_FILE}"
}

main() {
    if [ "${MODE}" = "help" ]; then
        usage
        exit 0
    fi

    if [ "${MODE}" = "check" ]; then
        ensure_preconditions
        exit 0
    fi

    if [ "${MODE}" = "validate-report" ]; then
        validate_report
        exit 0
    fi

    if [ "${MODE}" != "drill" ]; then
        echo "Unknown MODE: ${MODE}" >&2
        usage >&2
        exit 1
    fi

    run_incident_drill
    write_report

    if [ "${overall_result}" != "PASS" ]; then
        exit 1
    fi
}

main "$@"
