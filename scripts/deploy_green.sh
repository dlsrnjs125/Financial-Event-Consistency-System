#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment-lib.sh
source "${SCRIPT_DIR}/deployment-lib.sh"

STOP_GREEN_ON_FAILURE="${STOP_GREEN_ON_FAILURE:-false}"

handle_failure() {
  local exit_code="$?"
  log "Green verification failed. Inspect logs with: docker compose --profile green-deployment logs ${GREEN_SERVICE}"
  compose_green_profile ps "${GREEN_SERVICE}" || true
  if [[ "${STOP_GREEN_ON_FAILURE}" == "true" ]]; then
    log "STOP_GREEN_ON_FAILURE=true; stopping ${GREEN_SERVICE}"
    compose_green_profile stop "${GREEN_SERVICE}" || true
  fi
  exit "${exit_code}"
}

trap handle_failure ERR

require_command curl "Install curl and retry."
require_command python3 "Install Python 3 and retry."

log "Starting Green service with Docker Compose profile green-deployment"
compose_green_profile up -d --build "${GREEN_SERVICE}"
compose ps "${GREEN_SERVICE}"

wait_for_endpoint "${GREEN_URL}/health" "Green /health"
verify_ready_body "${GREEN_URL}/ready" "Green"
verify_nginx_can_reach_green

trap - ERR
log "Green is ready for traffic switch"
