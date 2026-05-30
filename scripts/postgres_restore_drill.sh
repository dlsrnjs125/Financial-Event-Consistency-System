#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESTORE_SERVICE="${POSTGRES_RESTORE_SERVICE:-postgres-restore}"
RESTORE_DB="${POSTGRES_RESTORE_DB:-financial_events_restore}"
RESTORE_USER="${POSTGRES_RESTORE_USER:-appuser}"
REQUIRE_CHECKSUM="${REQUIRE_CHECKSUM:-false}"
BACKUP_CREATED_IN_THIS_RUN="${BACKUP_CREATED_IN_THIS_RUN:-false}"
REPORT_FILE="${DR_REPORT_FILE:-${ROOT_DIR}/reports/dr/ops4-postgres-restore-drill.md}"
CONSISTENCY_SQL="${CONSISTENCY_SQL:-${ROOT_DIR}/scripts/sql/dr_consistency_check.sql}"
COMPOSE_CMD="${DOCKER_COMPOSE:-docker compose}"

run_compose() {
    ${COMPOSE_CMD} "$@"
}

usage() {
    echo "Usage: $0 backups/postgres/financial_events_YYYYMMDDTHHMMSS.dump" >&2
}

validate_identifier() {
    local name="$1"
    local value="$2"

    case "$value" in
        ''|*[!a-zA-Z0-9_]*)
            echo "Invalid ${name}: ${value}" >&2
            exit 1
            ;;
    esac
}

verify_checksum() {
    local dump_file="$1"
    local checksum_file="${dump_file}.sha256"
    local checksum_path
    checksum_path="${checksum_file#${ROOT_DIR}/}"

    if [ ! -f "$checksum_file" ]; then
        if [ "$REQUIRE_CHECKSUM" = "true" ]; then
            echo "Checksum file is required but missing: ${checksum_file}" >&2
            exit 1
        fi
        echo "checksum_status=SKIPPED"
        return 0
    fi

    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$ROOT_DIR" && sha256sum -c "$checksum_path" >/dev/null)
    else
        (cd "$ROOT_DIR" && shasum -a 256 -c "$checksum_path" >/dev/null)
    fi
    echo "checksum_status=PASS"
}

wait_for_restore_db() {
    local attempt
    for attempt in $(seq 1 30); do
        if run_compose exec -T "$RESTORE_SERVICE" pg_isready -U "$RESTORE_USER" -d "$RESTORE_DB" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    echo "Restore PostgreSQL did not become ready." >&2
    return 1
}

if [ "$#" -ne 1 ]; then
    usage
    exit 2
fi

validate_identifier "RESTORE_DB" "$RESTORE_DB"
validate_identifier "RESTORE_USER" "$RESTORE_USER"

dump_file="$1"
if [ ! -f "$dump_file" ]; then
    echo "Dump file not found: ${dump_file}" >&2
    exit 1
fi

if [ ! -s "$dump_file" ]; then
    echo "Dump file is empty: ${dump_file}" >&2
    exit 1
fi

checksum_output="$(verify_checksum "$dump_file")"
checksum_status="${checksum_output#checksum_status=}"
if [ "$checksum_status" != "PASS" ] && [ "$checksum_status" != "SKIPPED" ]; then
    echo "Checksum verification failed." >&2
    exit 1
fi

mkdir -p "$(dirname "$REPORT_FILE")"

restore_started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
restore_start_epoch="$(date +%s)"
dr_drill_started_at="${DR_DRILL_STARTED_AT:-${restore_started_at}}"
dr_drill_start_epoch="${DR_DRILL_START_EPOCH:-${restore_start_epoch}}"

echo "Starting restore drill into ${RESTORE_SERVICE}/${RESTORE_DB}."
run_compose up -d "$RESTORE_SERVICE" >/dev/null
wait_for_restore_db

run_compose exec -T "$RESTORE_SERVICE" psql -U "$RESTORE_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${RESTORE_DB}' AND pid <> pg_backend_pid();" >/dev/null
run_compose exec -T "$RESTORE_SERVICE" psql -U "$RESTORE_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS ${RESTORE_DB} WITH (FORCE);" >/dev/null
run_compose exec -T "$RESTORE_SERVICE" psql -U "$RESTORE_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE ${RESTORE_DB} OWNER ${RESTORE_USER};" >/dev/null

if ! run_compose exec -T "$RESTORE_SERVICE" pg_restore --clean --if-exists --no-owner --no-privileges \
    -U "$RESTORE_USER" -d "$RESTORE_DB" < "$dump_file"; then
    echo "pg_restore failed." >&2
    exit 1
fi

required_table_count="$(
    run_compose exec -T "$RESTORE_SERVICE" psql -U "$RESTORE_USER" -d "$RESTORE_DB" -At -v ON_ERROR_STOP=1 \
        -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('accounts', 'transaction_events', 'ledger_entries', 'idempotency_records', 'event_state_histories');" | tr -d '[:space:]'
)"

if [ "$required_table_count" != "5" ]; then
    echo "Schema verification failed. Required table count=${required_table_count}" >&2
    exit 1
fi

check_output="$(
    run_compose exec -T "$RESTORE_SERVICE" psql -U "$RESTORE_USER" -d "$RESTORE_DB" -At -F '=' -v ON_ERROR_STOP=1 -f - < "$CONSISTENCY_SQL"
)"

restore_end_epoch="$(date +%s)"
restore_duration_seconds="$((restore_end_epoch - restore_start_epoch))"
dr_drill_duration_seconds="$((restore_end_epoch - dr_drill_start_epoch))"

dr_status="PASS"
while IFS='=' read -r check_name check_value; do
    [ -n "${check_name:-}" ] || continue
    if [ "$check_value" != "0" ]; then
        dr_status="FAIL"
    fi
done <<< "$check_output"

backup_size="$(du -h "$dump_file" | awk '{print $1}')"
checksum_file="${dump_file}.sha256"
checksum_file_result="N/A"
if [ -f "$checksum_file" ]; then
    checksum_file_result="PASS"
fi

backup_result="EXISTING_DUMP"
if [ "$BACKUP_CREATED_IN_THIS_RUN" = "true" ]; then
    backup_result="PASS"
fi

duplicated_external_event_count="$(printf '%s\n' "$check_output" | awk -F= '$1=="duplicated_external_event_count"{print $2}')"
duplicated_ledger_event_count="$(printf '%s\n' "$check_output" | awk -F= '$1=="duplicated_ledger_event_count"{print $2}')"
orphan_ledger_count="$(printf '%s\n' "$check_output" | awk -F= '$1=="orphan_ledger_count"{print $2}')"
completed_event_without_ledger_count="$(printf '%s\n' "$check_output" | awk -F= '$1=="completed_event_without_ledger_count"{print $2}')"
account_balance_mismatch_count="$(printf '%s\n' "$check_output" | awk -F= '$1=="account_balance_mismatch_count"{print $2}')"
ledger_account_mismatch_count="$(printf '%s\n' "$check_output" | awk -F= '$1=="ledger_account_mismatch_count"{print $2}')"
duplicated_idempotency_key_count="$(printf '%s\n' "$check_output" | awk -F= '$1=="duplicated_idempotency_key_count"{print $2}')"

account_balance_result="PASS"
if [ "${account_balance_mismatch_count:-1}" != "0" ]; then
    account_balance_result="FAIL"
fi

cat > "$REPORT_FILE" <<EOF
# Ops Phase 4 - PostgreSQL Backup / Restore DR Drill

## 목적

백업 파일 생성이 아니라 복구 가능성과 복구 후 정합성을 검증한다.

## 실행 명령

\`\`\`bash
make ops4-demo
\`\`\`

## 실행 증거 기준

이 report는 \`make ops4-demo\` 또는 \`make ops4-drill\`을 로컬 Docker Compose 환경에서
실행한 curated evidence report이다.
실제 dump 파일과 checksum 파일은 민감 정보 포함 가능성이 있어 git에 커밋하지 않는다.
checksum 파일은 실행 시 로컬에서 생성되며, 이 report에는 checksum 검증 상태와
count-only 정합성 결과만 남긴다.
\`Backup 생성\` 항목은 전체 DR Drill에서는 \`PASS\`, 기존 dump를 복원한
restore-only 실행에서는 \`EXISTING_DUMP\`로 기록된다.

## 결과 요약

| 항목 | 결과 |
|---|---:|
| Backup 생성 | ${backup_result} |
| SHA256 checksum 생성 | ${checksum_file_result} |
| Checksum 검증 | ${checksum_status} |
| Restore DB 복원 | PASS |
| Schema 확인 | PASS |
| Duplicated external event | ${duplicated_external_event_count:-N/A} |
| Duplicated ledger event | ${duplicated_ledger_event_count:-N/A} |
| Orphan ledger | ${orphan_ledger_count:-N/A} |
| Completed event without ledger | ${completed_event_without_ledger_count:-N/A} |
| Ledger account mismatch | ${ledger_account_mismatch_count:-N/A} |
| Duplicated idempotency key | ${duplicated_idempotency_key_count:-N/A} |
| Account balance consistency | ${account_balance_result} |
| Restore duration seconds | ${restore_duration_seconds} |
| DR drill duration seconds | ${dr_drill_duration_seconds} |
| DR Drill | ${dr_status} |

## 복구 대상

- Source DB: postgres / financial_events
- Restore DB: ${RESTORE_SERVICE} / ${RESTORE_DB}
- Backup file: \`$(basename "$dump_file")\`
- Backup size: \`${backup_size}\`
- DR drill started at: \`${dr_drill_started_at}\`
- Restore started at: \`${restore_started_at}\`

## 운영 원칙

- 운영 DB에 직접 restore하지 않는다.
- restore 검증은 별도 DB에서 수행한다.
- dump 파일과 checksum은 git에 커밋하지 않는다.
- report에는 실제 row data를 기록하지 않는다.

## 검증 SQL 결과

\`\`\`text
${check_output}
\`\`\`

## 한계

- PITR/WAL archiving은 이번 Phase 범위에서 제외한다.
- 대용량 restore time 측정은 후속 단계에서 수행한다.
- 클라우드 object storage 업로드는 구현하지 않는다.
EOF

if [ "$dr_status" != "PASS" ]; then
    echo "PostgreSQL DR drill failed."
    echo "$check_output"
    echo "report_file=${REPORT_FILE}"
    exit 1
fi

echo "PostgreSQL DR drill passed."
echo "backup_file=${dump_file}"
echo "checksum_file=${checksum_file}"
echo "restore_target=${RESTORE_SERVICE}/${RESTORE_DB}"
echo "duplicated_external_event_count=${duplicated_external_event_count:-N/A}"
echo "duplicated_ledger_event_count=${duplicated_ledger_event_count:-N/A}"
echo "orphan_ledger_count=${orphan_ledger_count:-N/A}"
echo "completed_event_without_ledger_count=${completed_event_without_ledger_count:-N/A}"
echo "account_balance_mismatch_count=${account_balance_mismatch_count:-N/A}"
echo "restore_duration_seconds=${restore_duration_seconds}"
echo "dr_drill_duration_seconds=${dr_drill_duration_seconds}"
echo "report_file=${REPORT_FILE}"
