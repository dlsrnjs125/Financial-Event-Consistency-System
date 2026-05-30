#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DR_DRILL_STARTED_AT
export DR_DRILL_START_EPOCH

DR_DRILL_STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
DR_DRILL_START_EPOCH="$(date +%s)"

backup_output="$("${ROOT_DIR}/scripts/postgres_backup.sh")"
printf '%s\n' "$backup_output"

backup_file="$(printf '%s\n' "$backup_output" | awk -F= '$1=="backup_file"{print $2}')"
if [ -z "$backup_file" ]; then
    echo "Could not determine backup file from backup output." >&2
    exit 1
fi

BACKUP_CREATED_IN_THIS_RUN=true REQUIRE_CHECKSUM=true \
    "${ROOT_DIR}/scripts/postgres_restore_drill.sh" "$backup_file"
