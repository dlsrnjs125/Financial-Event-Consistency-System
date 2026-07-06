#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
READY_BASE_URL="${READY_BASE_URL:-http://localhost:8081}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-financial_events}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
CLIENT_ID="${CLIENT_ID:-bank-a}"
CLIENT_SECRET="${CLIENT_SECRET:-change-me-secret}"
ACCOUNT_NO="${ACCOUNT_NO:-ACC-001}"
RUN_ID="${RUN_ID:-ph1-write-suspend-$(date -u +%Y%m%dT%H%M%SZ)}"
REPORT_DIR="${REPORT_DIR:-${ROOT_DIR}/reports/production-hardening/ph1-write-suspend/${RUN_ID}}"
STATE_FILE="${WRITE_SUSPEND_STATE_FILE:-${ROOT_DIR}/reports/runtime/write-suspend-state.json}"
VERIFY_TIMEOUT_SECONDS="${VERIFY_TIMEOUT_SECONDS:-60}"

postgres_stopped_by_drill=false

log() {
    printf '[ph1-db-down] %s\n' "$*"
}

compose() {
    (cd "${ROOT_DIR}" && ${DOCKER_COMPOSE} "$@")
}

cleanup() {
    set +e
    if [ "${postgres_stopped_by_drill}" = "true" ]; then
        log "Cleanup: ensuring PostgreSQL is running."
        compose start "${POSTGRES_SERVICE}" >/dev/null 2>&1 || true
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

http_status() {
    local method="$1"
    local url="$2"
    shift 2
    curl -sS -o /dev/null -w '%{http_code}' --max-time 10 -X "${method}" "$@" "${url}" 2>/dev/null || true
}

wait_for_status() {
    local url="$1"
    local expected="$2"
    local label="$3"
    local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))
    local status

    while (( SECONDS < deadline )); do
        status="$(http_status GET "${url}")"
        if [ "${status}" = "${expected}" ]; then
            log "${label}: ${status}"
            return 0
        fi
        sleep 2
    done

    status="$(http_status GET "${url}")"
    echo "${label} did not reach ${expected}; last status=${status}" >&2
    return 1
}

write_request() {
    local external_event_id="$1"
    local idempotency_key="$2"
    local output_file="$3"
    local status_file="$4"
    local header_file="$5"
    local occurred_at="$6"

    python3 - "${CLIENT_SECRET}" "${CLIENT_ID}" "${ACCOUNT_NO}" "${external_event_id}" "${idempotency_key}" "${BASE_URL}" "${output_file}" "${status_file}" "${header_file}" "${occurred_at}" <<'PY'
import datetime as dt
import hashlib
import hmac
import json
import sys
import urllib.error
import urllib.request

secret, client_id, account_no, external_event_id, idempotency_key, base_url, output_file, status_file, header_file, occurred_at = sys.argv[1:11]
path = "/api/v1/transaction-events"
timestamp = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
payload = {
    "external_event_id": external_event_id,
    "account_no": account_no,
    "event_type": "DEPOSIT",
    "amount": 100,
    "currency": "KRW",
    "occurred_at": occurred_at,
}
body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
body_hash = hashlib.sha256(body).hexdigest()
base_string = "\n".join(("POST", path, timestamp, body_hash))
signature = hmac.new(secret.encode(), base_string.encode(), hashlib.sha256).hexdigest()
request = urllib.request.Request(
    base_url.rstrip("/") + path,
    data=body,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "X-Client-Id": client_id,
        "X-Timestamp": timestamp,
        "X-Signature": signature,
        "Idempotency-Key": idempotency_key,
    },
)
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        response_body = response.read().decode()
        status = response.status
        headers = response.headers
except urllib.error.HTTPError as exc:
    response_body = exc.read().decode()
    status = exc.code
    headers = exc.headers

open(output_file, "w", encoding="utf-8").write(response_body)
open(status_file, "w", encoding="utf-8").write(str(status))
open(header_file, "w", encoding="utf-8").write(str(headers))
PY
}

psql_scalar() {
    local sql="$1"
    compose exec -T "${POSTGRES_SERVICE}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
        -tA -v ON_ERROR_STOP=1 -c "${sql}" | tr -d '[:space:]'
}

require_command docker
require_command curl
require_command python3

mkdir -p "${REPORT_DIR}"

log "Starting PH1 DB-down drill: ${RUN_ID}"
compose up -d --build postgres redis api-blue nginx
wait_for_status "${BASE_URL}/health" "200" "health before drill"
wait_for_status "${READY_BASE_URL}/ready" "200" "ready before drill"

WRITE_SUSPEND_STATE_FILE="${STATE_FILE}" python3 "${ROOT_DIR}/scripts/write_suspend_state.py" disable --reason drill_start >/dev/null || true

baseline_event="ph1-baseline-${RUN_ID}"
baseline_occurred_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
baseline_status_file="${REPORT_DIR}/baseline.status"
write_request "${baseline_event}" "ph1-baseline-${RUN_ID}" "${REPORT_DIR}/baseline.json" "${baseline_status_file}" "${REPORT_DIR}/baseline.headers" "${baseline_occurred_at}"
baseline_status="$(cat "${baseline_status_file}")"
test "${baseline_status}" = "200"

compose stop "${POSTGRES_SERVICE}"
postgres_stopped_by_drill=true
wait_for_status "${READY_BASE_URL}/ready" "503" "ready while postgres down"

blocked_event="ph1-blocked-${RUN_ID}"
blocked_occurred_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
blocked_status_file="${REPORT_DIR}/blocked.status"
write_request "${blocked_event}" "ph1-blocked-${RUN_ID}" "${REPORT_DIR}/blocked.json" "${blocked_status_file}" "${REPORT_DIR}/blocked.headers" "${blocked_occurred_at}"
blocked_status="$(cat "${blocked_status_file}")"
test "${blocked_status}" = "503"
grep -qi '^Retry-After:' "${REPORT_DIR}/blocked.headers"
test -f "${STATE_FILE}"

compose start "${POSTGRES_SERVICE}"
postgres_stopped_by_drill=false
wait_for_status "${READY_BASE_URL}/ready" "200" "ready after postgres recovery"

blocked_event_count="$(psql_scalar "SELECT COUNT(*) FROM transaction_events WHERE external_event_id = '${blocked_event}';")"
test "${blocked_event_count}" = "0"

WRITE_SUSPEND_STATE_FILE="${STATE_FILE}" python3 "${ROOT_DIR}/scripts/write_suspend_state.py" disable --reason operator_resume > "${REPORT_DIR}/resume-state.json"

blocked_retry_status_file="${REPORT_DIR}/blocked-retry.status"
write_request "${blocked_event}" "ph1-blocked-${RUN_ID}" "${REPORT_DIR}/blocked-retry.json" "${blocked_retry_status_file}" "${REPORT_DIR}/blocked-retry.headers" "${blocked_occurred_at}"
blocked_retry_status="$(cat "${blocked_retry_status_file}")"
test "${blocked_retry_status}" = "200"

blocked_event_count_after_retry="$(psql_scalar "SELECT COUNT(*) FROM transaction_events WHERE external_event_id = '${blocked_event}';")"
duplicate_ledger_count="$(psql_scalar "SELECT COUNT(*) FROM (SELECT transaction_event_id FROM ledger_entries GROUP BY transaction_event_id HAVING COUNT(*) > 1) duplicated;")"
duplicate_event_count="$(psql_scalar "SELECT COUNT(*) FROM (SELECT external_event_id FROM transaction_events GROUP BY external_event_id HAVING COUNT(*) > 1) duplicated;")"

cat > "${REPORT_DIR}/report.md" <<EOF
# PH1 Write Suspend DB-Down Drill

- run_id: ${RUN_ID}
- baseline_write_status: ${baseline_status}
- blocked_write_status: ${blocked_status}
- retry_after_header_present: yes
- same_idempotency_retry_status: ${blocked_retry_status}
- blocked_event_record_count_before_retry: ${blocked_event_count}
- blocked_event_record_count_after_retry: ${blocked_event_count_after_retry}
- duplicate_event_count: ${duplicate_event_count}
- duplicate_ledger_count: ${duplicate_ledger_count}
- state_file: ${STATE_FILE}

## Result

PostgreSQL down caused readiness failure and financial write suspension.
The blocked request returned 503 with Retry-After and was not recorded as a successful transaction.
After operator resume, the same external_event_id, Idempotency-Key, and body were retried successfully once.
EOF

test "${blocked_event_count_after_retry}" = "1"
test "${duplicate_ledger_count}" = "0"
test "${duplicate_event_count}" = "0"

log "Drill report written: ${REPORT_DIR}/report.md"
