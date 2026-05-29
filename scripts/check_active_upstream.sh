#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment-lib.sh
source "${SCRIPT_DIR}/deployment-lib.sh"

EXPECTED_COLOR="${1:-}"

usage() {
  cat >&2 <<EOF
Usage: $0 blue|green

Verify active color state, upstream snippet, and loaded Nginx config.
EOF
}

case "${EXPECTED_COLOR}" in
  blue)
    EXPECTED_UPSTREAM="api-blue:8000"
    ;;
  green)
    EXPECTED_UPSTREAM="api-green:8000"
    ;;
  *)
    usage
    exit 2
    ;;
esac

actual_color="$(current_active_color)"
if [[ "${actual_color}" != "${EXPECTED_COLOR}" ]]; then
  log "Active color mismatch: expected=${EXPECTED_COLOR}, actual=${actual_color}"
  exit 1
fi

if ! grep -q "${EXPECTED_UPSTREAM}" "${ACTIVE_UPSTREAM_FILE}"; then
  log "Active upstream file does not contain ${EXPECTED_UPSTREAM}: ${ACTIVE_UPSTREAM_FILE}"
  exit 1
fi

nginx_test
if ! compose exec -T "${NGINX_SERVICE}" nginx -T 2>/dev/null | grep -q "${EXPECTED_UPSTREAM}"; then
  log "Loaded Nginx config does not contain ${EXPECTED_UPSTREAM}"
  exit 1
fi

log "Active upstream verified: ${EXPECTED_COLOR} (${EXPECTED_UPSTREAM})"
