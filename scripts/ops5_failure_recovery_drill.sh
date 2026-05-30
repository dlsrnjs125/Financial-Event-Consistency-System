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
REPORT_FILE="${OPS5_REPORT_FILE:-${ROOT_DIR}/reports/ops/ops5-failure-recovery-drill.md}"
SCENARIO="${SCENARIO:-all}"
VERIFY_TIMEOUT_SECONDS="${VERIFY_TIMEOUT_SECONDS:-60}"

DRILL_STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
DRILL_START_EPOCH="$(date +%s)"

redis_result="SKIPPED"
redis_duration="0"
redis_down_detected="SKIPPED"
redis_api_fallback="SKIPPED"
redis_restarted="SKIPPED"
redis_ready_after_recovery="SKIPPED"
redis_consistency_check="SKIPPED"
redis_ready_state_while_down="SKIPPED"
redis_event_count="SKIPPED"
redis_ledger_count="SKIPPED"
redis_idempotency_record_count="SKIPPED"
redis_duplicate_ledger_count="SKIPPED"
redis_idempotency_violation_count="SKIPPED"

api_result="SKIPPED"
api_duration="0"
api_down_detected="SKIPPED"
api_health_failure="SKIPPED"
api_restarted="SKIPPED"
api_health_after_recovery="SKIPPED"
api_ready_after_recovery="SKIPPED"
api_smoke_after_recovery="SKIPPED"

db_result="SKIPPED"
db_duration="0"
db_down_detected="SKIPPED"
db_restarted="SKIPPED"
db_ready_after_recovery="SKIPPED"
db_consistency_after_recovery="SKIPPED"

redis_stopped_by_drill=false
api_stopped_by_drill=false
db_stopped_by_drill=false

log() {
    printf '[ops5] %s\n' "$*"
}

compose() {
    (cd "${ROOT_DIR}" && ${DOCKER_COMPOSE} "$@")
}

cleanup() {
    set +e
    if [ "${db_stopped_by_drill}" = "true" ] ||
       [ "${redis_stopped_by_drill}" = "true" ] ||
       [ "${api_stopped_by_drill}" = "true" ]; then
        log "Cleanup: ensuring services stopped by this drill are running."
    fi
    if [ "${db_stopped_by_drill}" = "true" ]; then
        compose start "${POSTGRES_SERVICE}" >/dev/null 2>&1 || true
    fi
    if [ "${redis_stopped_by_drill}" = "true" ]; then
        compose start "${REDIS_SERVICE}" >/dev/null 2>&1 || true
    fi
    if [ "${api_stopped_by_drill}" = "true" ]; then
        compose start "${API_SERVICE}" >/dev/null 2>&1 || true
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

wait_for_ready_postgres_ok() {
    local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))
    local status
    local postgres_state

    while (( SECONDS < deadline )); do
        status="$(http_status "${READY_BASE_URL}/ready")"
        postgres_state="$(ready_json_field "checks.postgres")"
        if [ "${status}" = "200" ] && [ "${postgres_state}" = "ok" ]; then
            log "readiness postgres=ok"
            return 0
        fi
        sleep 2
    done

    echo "Readiness did not recover postgres=ok." >&2
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
    wait_for_ready_postgres_ok
    wait_for_postgres
    compose exec -T "${REDIS_SERVICE}" redis-cli ping >/dev/null
    log "Precheck passed."
}

run_redis_drill() {
    local started
    local external_event_id
    local idempotency_key
    local event_count
    local ledger_count
    local idem_count
    local redis_state
    local smoke_output

    log "Running Redis failure recovery drill."
    started="$(date +%s)"

    compose stop "${REDIS_SERVICE}" >/dev/null
    redis_stopped_by_drill=true
    if ! compose exec -T "${REDIS_SERVICE}" redis-cli ping >/dev/null 2>&1; then
        redis_down_detected="PASS"
    else
        redis_down_detected="FAIL"
    fi

    redis_state="$(ready_json_field "checks.redis")"
    redis_ready_state_while_down="${redis_state:-unknown}"
    if [ "${redis_state}" = "degraded" ]; then
        redis_down_detected="PASS"
    fi

    smoke_output="$(run_duplicate_smoke "OPS5-REDIS")"
    printf '%s\n' "${smoke_output}"
    external_event_id="$(printf '%s\n' "${smoke_output}" | awk -F= '$1=="external_event_id"{print $2}')"
    idempotency_key="$(printf '%s\n' "${smoke_output}" | awk -F= '$1=="idempotency_key"{print $2}')"

    event_count="$(psql_scalar "SELECT COUNT(*) FROM transaction_events WHERE external_event_id = '${external_event_id}';")"
    ledger_count="$(psql_scalar "SELECT COUNT(*) FROM ledger_entries le JOIN transaction_events te ON te.id = le.transaction_event_id WHERE te.external_event_id = '${external_event_id}';")"
    idem_count="$(psql_scalar "SELECT COUNT(*) FROM idempotency_records WHERE idempotency_key = '${idempotency_key}';")"
    redis_event_count="${event_count}"
    redis_ledger_count="${ledger_count}"
    redis_idempotency_record_count="${idem_count}"
    redis_duplicate_ledger_count="$(( ledger_count > 1 ? ledger_count - 1 : 0 ))"
    redis_idempotency_violation_count="$(( idem_count > 1 ? idem_count - 1 : 0 ))"

    if [ "${event_count}" = "1" ] && [ "${ledger_count}" = "1" ] && [ "${idem_count}" = "1" ]; then
        redis_api_fallback="PASS"
    else
        redis_api_fallback="FAIL"
    fi

    compose start "${REDIS_SERVICE}" >/dev/null
    redis_stopped_by_drill=false
    redis_restarted="PASS"
    wait_for_status "${BASE_URL}/health" "200" "health after redis restart"
    wait_for_ready_postgres_ok
    redis_state="$(ready_json_field "checks.redis")"
    if [ "${redis_state}" = "ok" ]; then
        redis_ready_after_recovery="PASS"
    else
        redis_ready_after_recovery="FAIL"
    fi

    if run_consistency_counts; then
        redis_consistency_check="PASS"
    else
        redis_consistency_check="FAIL"
    fi

    redis_duration="$(( $(date +%s) - started ))"
    if [ "${redis_down_detected}" = "PASS" ] &&
       [ "${redis_api_fallback}" = "PASS" ] &&
       [ "${redis_restarted}" = "PASS" ] &&
       [ "${redis_ready_after_recovery}" = "PASS" ] &&
       [ "${redis_consistency_check}" = "PASS" ] &&
       [ "${redis_duplicate_ledger_count}" = "0" ] &&
       [ "${redis_idempotency_violation_count}" = "0" ]; then
        redis_result="PASS"
    else
        redis_result="FAIL"
    fi
}

run_api_drill() {
    local started
    local status

    log "Running API failure recovery drill."
    started="$(date +%s)"

    compose stop "${API_SERVICE}" >/dev/null
    api_stopped_by_drill=true
    status="$(http_status "${BASE_URL}/health")"
    if [ "${status}" != "200" ]; then
        api_down_detected="PASS"
        api_health_failure="PASS"
    else
        api_down_detected="FAIL"
        api_health_failure="FAIL"
    fi

    compose start "${API_SERVICE}" >/dev/null
    api_stopped_by_drill=false
    api_restarted="PASS"
    if wait_for_status "${BASE_URL}/health" "200" "health after api restart"; then
        api_health_after_recovery="PASS"
    else
        api_health_after_recovery="FAIL"
    fi

    if wait_for_ready_postgres_ok; then
        api_ready_after_recovery="PASS"
    else
        api_ready_after_recovery="FAIL"
    fi

    if run_duplicate_smoke "OPS5-API" >/dev/null; then
        api_smoke_after_recovery="PASS"
    else
        api_smoke_after_recovery="FAIL"
    fi

    api_duration="$(( $(date +%s) - started ))"
    if [ "${api_down_detected}" = "PASS" ] &&
       [ "${api_health_failure}" = "PASS" ] &&
       [ "${api_restarted}" = "PASS" ] &&
       [ "${api_health_after_recovery}" = "PASS" ] &&
       [ "${api_ready_after_recovery}" = "PASS" ] &&
       [ "${api_smoke_after_recovery}" = "PASS" ]; then
        api_result="PASS"
    else
        api_result="FAIL"
    fi
}

run_db_drill() {
    local started
    local status

    log "Running PostgreSQL failure detection/recovery drill."
    started="$(date +%s)"

    compose stop "${POSTGRES_SERVICE}" >/dev/null
    db_stopped_by_drill=true
    sleep 2
    status="$(http_status "${READY_BASE_URL}/ready")"
    if [ "${status}" = "503" ] || [ "${status}" = "000" ]; then
        db_down_detected="PASS"
    else
        db_down_detected="FAIL"
    fi

    compose start "${POSTGRES_SERVICE}" >/dev/null
    db_stopped_by_drill=false
    db_restarted="PASS"

    if wait_for_postgres && wait_for_ready_postgres_ok; then
        db_ready_after_recovery="PASS"
    else
        db_ready_after_recovery="FAIL"
    fi

    if run_consistency_counts; then
        db_consistency_after_recovery="PASS"
    else
        db_consistency_after_recovery="FAIL"
    fi

    db_duration="$(( $(date +%s) - started ))"
    if [ "${db_down_detected}" = "PASS" ] &&
       [ "${db_restarted}" = "PASS" ] &&
       [ "${db_ready_after_recovery}" = "PASS" ] &&
       [ "${db_consistency_after_recovery}" = "PASS" ]; then
        db_result="PASS"
    else
        db_result="FAIL"
    fi
}

write_report() {
    local finished_at
    local total_duration
    finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    total_duration="$(( $(date +%s) - DRILL_START_EPOCH ))"

    mkdir -p "$(dirname "${REPORT_FILE}")"
    cat > "${REPORT_FILE}" <<EOF
# Ops Phase 5 - Failure Recovery Runbook Drill

## 실행 목적

Redis, API, PostgreSQL 장애를 Docker Compose 로컬 운영 환경에서 재현하고, 복구 후 서비스 정상성 및 PostgreSQL 기준 정합성을 count-only evidence로 남긴다.

## 실행 환경

| 항목 | 값 |
|---|---|
| 실행 명령 | \`SCENARIO=${SCENARIO} ./scripts/ops5_failure_recovery_drill.sh\` |
| 시작 시각 UTC | \`${DRILL_STARTED_AT}\` |
| 종료 시각 UTC | \`${finished_at}\` |
| Public base URL | \`${BASE_URL}\` |
| Readiness base URL | \`${READY_BASE_URL}\` |
| API service | \`${API_SERVICE}\` |
| PostgreSQL service | \`${POSTGRES_SERVICE}\` |
| Redis service | \`${REDIS_SERVICE}\` |

## 결과 요약

| 시나리오 | 결과 | 복구 시간 seconds | 주요 검증 |
|---|---:|---:|---|
| Redis failure recovery | ${redis_result} | ${redis_duration} | fallback + consistency |
| API failure recovery | ${api_result} | ${api_duration} | health/ready + smoke |
| PostgreSQL failure detection/recovery | ${db_result} | ${db_duration} | readiness fail/pass + consistency |

## Redis Failure Recovery Evidence

| 항목 | 결과 |
|---|---|
| Redis down detected | ${redis_down_detected} |
| Redis ready state while down | ${redis_ready_state_while_down} |
| API fallback behavior | ${redis_api_fallback} |
| Event count for duplicate smoke | ${redis_event_count} |
| Ledger count for duplicate smoke | ${redis_ledger_count} |
| Idempotency record count for duplicate smoke | ${redis_idempotency_record_count} |
| Redis restarted | ${redis_restarted} |
| Ready after recovery | ${redis_ready_after_recovery} |
| Consistency check | ${redis_consistency_check} |
| Duplicate ledger count | ${redis_duplicate_ledger_count} |
| Idempotency violation count | ${redis_idempotency_violation_count} |

## API Failure Recovery Evidence

| 항목 | 결과 |
|---|---|
| API down detected | ${api_down_detected} |
| Health check failure detected | ${api_health_failure} |
| API restarted | ${api_restarted} |
| Health after recovery | ${api_health_after_recovery} |
| Ready after recovery | ${api_ready_after_recovery} |
| Smoke request after recovery | ${api_smoke_after_recovery} |

## PostgreSQL Failure Recovery Evidence

| 항목 | 결과 |
|---|---|
| DB down detected by readiness | ${db_down_detected} |
| DB restarted | ${db_restarted} |
| Ready after recovery | ${db_ready_after_recovery} |
| Consistency check after recovery | ${db_consistency_after_recovery} |

## 복구 시간 Evidence

| 항목 | 값 |
|---|---:|
| Redis recovery duration seconds | ${redis_duration} |
| API recovery duration seconds | ${api_duration} |
| DB recovery duration seconds | ${db_duration} |
| Total drill duration seconds | ${total_duration} |

## 운영상 한계와 보완 전략

- 이 drill은 운영 DB volume을 삭제하지 않고 Docker Compose \`stop/start\`만 사용한다.
- PostgreSQL 장애는 destructive restore가 아니라 readiness failure detection과 재기동 후 정합성 확인으로 제한한다.
- Redis 장애는 최종 정합성 실패가 아니라 degraded dependency로 취급하며, PostgreSQL unique constraint와 transaction을 최종 기준으로 검증한다.
- 컨테이너 stop/start는 CI 환경에서 flakiness가 생길 수 있으므로 실제 장애 주입 evidence는 로컬 runbook drill report로 관리하고, CI에서는 스크립트 문법과 report format을 검증한다.
- Report에는 실제 거래 row data, account_no 원문 목록, secret, token, dump 내용이 아니라 PASS/FAIL, duration, count-only 결과만 기록한다.

## README에 기록할 문장

Ops Phase 5에서는 Redis/API/PostgreSQL 장애를 Docker Compose 환경에서 stop/start 방식으로 재현하고, 복구 후 health/ready/smoke/consistency check와 recovery duration을 \`reports/ops/ops5-failure-recovery-drill.md\`에 count-only evidence로 남긴다.
EOF

    log "Report written: ${REPORT_FILE}"
}

print_usage() {
    cat <<EOF
Usage:
  SCENARIO=check ./scripts/ops5_failure_recovery_drill.sh
  SCENARIO=redis ./scripts/ops5_failure_recovery_drill.sh
  SCENARIO=api ./scripts/ops5_failure_recovery_drill.sh
  SCENARIO=db ./scripts/ops5_failure_recovery_drill.sh
  SCENARIO=all ./scripts/ops5_failure_recovery_drill.sh
EOF
}

case "${SCENARIO}" in
    check)
        ensure_preconditions
        ;;
    redis)
        ensure_preconditions
        run_redis_drill
        write_report
        ;;
    api)
        ensure_preconditions
        run_api_drill
        write_report
        ;;
    db)
        ensure_preconditions
        run_db_drill
        write_report
        ;;
    all)
        ensure_preconditions
        run_redis_drill
        run_api_drill
        run_db_drill
        write_report
        ;;
    -h|--help|help)
        print_usage
        ;;
    *)
        echo "Unknown SCENARIO: ${SCENARIO}" >&2
        print_usage >&2
        exit 2
        ;;
esac

if [ "${redis_result}" = "FAIL" ] || [ "${api_result}" = "FAIL" ] || [ "${db_result}" = "FAIL" ]; then
    exit 1
fi
