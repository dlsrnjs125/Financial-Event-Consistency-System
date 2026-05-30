#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment-lib.sh
source "${SCRIPT_DIR}/deployment-lib.sh"

STOP_GREEN=false

for arg in "$@"; do
  case "${arg}" in
    --stop-green)
      STOP_GREEN=true
      ;;
    -h|--help)
      cat <<EOF
Usage: $0 [--stop-green]

Rollback Nginx API traffic to Blue. This does not run DB schema rollback.
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      exit 2
      ;;
  esac
done

require_command curl "Install curl and retry."
require_command python3 "Install Python 3 and retry."

log "Starting rollback to Blue"
log "Rollback scope: API traffic only. DB schema rollback is not automated."

if [[ "$(current_active_color)" == "blue" ]]; then
  log "Nginx is already routing to Blue"
  nginx_test
else
  set_active_upstream blue
fi

wait_for_endpoint "${BASE_URL}/health" "Nginx Blue /health"
verify_ready_body "${INTERNAL_BASE_URL}/ready" "Nginx Blue internal"

if [[ "${STOP_GREEN}" == "true" ]]; then
  log "Stopping Green service after rollback"
  compose_green_profile stop "${GREEN_SERVICE}" || true
fi

log "Rollback to Blue completed"
