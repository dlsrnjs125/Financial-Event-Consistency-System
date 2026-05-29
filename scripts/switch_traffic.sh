#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment-lib.sh
source "${SCRIPT_DIR}/deployment-lib.sh"

TARGET_COLOR="${1:-}"

usage() {
  cat >&2 <<EOF
Usage: $0 blue|green

Switch the active Nginx upstream snippet after validating nginx config.
EOF
}

case "${TARGET_COLOR}" in
  blue|green)
    ;;
  *)
    usage
    exit 2
    ;;
esac

log "Current active upstream: $(current_active_color)"
log "Requested active upstream: ${TARGET_COLOR}"

nginx_test
set_active_upstream "${TARGET_COLOR}"

log "Traffic switch completed"
log "Active upstream: $(current_active_color)"
