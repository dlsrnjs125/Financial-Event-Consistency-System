#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment-lib.sh
source "${SCRIPT_DIR}/deployment-lib.sh"

ROLLBACK_REASON="${1:-${ROLLBACK_REASON:-manual rollback}}"

log "Starting API traffic rollback to Blue"
log "Rollback reason: ${ROLLBACK_REASON}"
log "Rollback scope: API traffic only. DB schema downgrade is not automated."

require_deploy_tools

active_color="$(current_active_color)"
if [[ "${active_color}" == "blue" ]]; then
  log "Nginx is already routing to Blue"
else
  set_active_upstream blue
fi

wait_for_endpoint "${BASE_URL}/health" "Nginx routed Blue /health"
verify_ready_body "${INTERNAL_BASE_URL}/ready" "Nginx routed Blue internal"
run_deployment_smoke "${BASE_URL}" "${INTERNAL_BASE_URL}"
run_deploy_verify_if_enabled

cat <<EOF

Rollback completed.
  Active upstream: $(current_active_color)
  Deployment id: ${DEPLOYMENT_ID}
  Consistency verification: make deploy-verify
  Logs: docker compose logs -f ${NGINX_SERVICE} ${BLUE_SERVICE} ${GREEN_SERVICE}

DB migration note:
  This rollback switches API traffic only. Database rollback is intentionally
  not automated; schema changes must follow backward-compatible migration policy.
EOF
