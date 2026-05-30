#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups/postgres}"
SOURCE_SERVICE="${POSTGRES_SOURCE_SERVICE:-postgres}"
SOURCE_DB="${POSTGRES_SOURCE_DB:-financial_events}"
SOURCE_USER="${POSTGRES_SOURCE_USER:-postgres}"
COMPOSE_CMD="${DOCKER_COMPOSE:-docker compose}"

run_compose() {
    ${COMPOSE_CMD} "$@"
}

wait_for_source_db() {
    local attempt
    for attempt in $(seq 1 30); do
        if run_compose exec -T "$SOURCE_SERVICE" pg_isready -U "$SOURCE_USER" -d "$SOURCE_DB" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    echo "Source PostgreSQL did not become ready: service=${SOURCE_SERVICE} db=${SOURCE_DB}" >&2
    return 1
}

checksum_file() {
    local file_path="$1"
    local relative_path
    relative_path="${file_path#${ROOT_DIR}/}"
    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$ROOT_DIR" && sha256sum "$relative_path" > "${relative_path}.sha256")
    else
        (cd "$ROOT_DIR" && shasum -a 256 "$relative_path" > "${relative_path}.sha256")
    fi
}

mkdir -p "$BACKUP_DIR"

timestamp="$(date +%Y%m%dT%H%M%S)"
backup_file="${BACKUP_DIR}/financial_events_${timestamp}.dump"
checksum_path="${backup_file}.sha256"

echo "Starting PostgreSQL backup from ${SOURCE_SERVICE}/${SOURCE_DB}."
run_compose up -d "$SOURCE_SERVICE" >/dev/null
wait_for_source_db

if ! run_compose exec -T "$SOURCE_SERVICE" pg_dump -U "$SOURCE_USER" -d "$SOURCE_DB" -Fc > "$backup_file"; then
    rm -f "$backup_file" "$checksum_path"
    echo "pg_dump failed. Backup file was not kept." >&2
    exit 1
fi

if [ ! -s "$backup_file" ]; then
    rm -f "$backup_file" "$checksum_path"
    echo "pg_dump produced an empty backup file." >&2
    exit 1
fi

checksum_file "$backup_file"
backup_size="$(du -h "$backup_file" | awk '{print $1}')"

echo "PostgreSQL backup completed."
echo "backup_file=${backup_file}"
echo "checksum_file=${checksum_path}"
echo "backup_size=${backup_size}"
