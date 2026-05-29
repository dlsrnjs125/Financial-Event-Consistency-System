#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment-lib.sh
source "${SCRIPT_DIR}/deployment-lib.sh"

COMMAND="${1:-deploy}"

ensure_base_stack() {
  log "Ensuring Blue, Nginx, PostgreSQL, and Redis are running"
  compose up -d --build postgres redis "${BLUE_SERVICE}" "${NGINX_SERVICE}"
  wait_for_endpoint "${BLUE_URL}/health" "Blue /health"
  wait_for_endpoint "${BASE_URL}/health" "Nginx /health"
  verify_ready_body "${BLUE_URL}/ready" "Blue"
}

start_green() {
  require_deploy_tools
  log "Starting Green service with Docker Compose profile green-deployment"
  compose_green_profile up -d --build "${GREEN_SERVICE}"
  compose ps "${GREEN_SERVICE}"
  wait_for_endpoint "${GREEN_URL}/health" "Green /health"
  verify_ready_body "${GREEN_URL}/ready" "Green"
  verify_nginx_can_reach_green
}

verify_green_before_switch() {
  log "Verifying Green before traffic switch"
  run_security_log_check
  run_migration_smoke
  run_deployment_smoke "${GREEN_URL}"
  nginx_test
}

switch_to_green() {
  local active_color
  require_deploy_tools
  active_color="$(current_active_color)"
  log "Current active upstream: ${active_color}; target: green"

  if [[ "${active_color}" == "green" ]]; then
    log "Nginx is already routing to Green"
    compose ps "${NGINX_SERVICE}" "${BLUE_SERVICE}" "${GREEN_SERVICE}" || true
    return 0
  fi

  wait_for_endpoint "${GREEN_URL}/health" "Green /health before switch"
  verify_ready_body "${GREEN_URL}/ready" "Green before switch"
  set_active_upstream green

  if ! wait_for_endpoint "${BASE_URL}/health" "Nginx routed /health"; then
    handle_post_switch_failure
    return 1
  fi

  if ! verify_ready_body "${BASE_URL}/ready" "Nginx routed"; then
    handle_post_switch_failure
    return 1
  fi

  if ! run_deployment_smoke "${BASE_URL}"; then
    handle_post_switch_failure
    return 1
  fi

  run_deploy_verify_if_enabled
  print_observability_hints
  log "Blue-Green traffic switch completed"
}

handle_post_switch_failure() {
  log "Post-switch verification failed"
  if [[ "${AUTO_ROLLBACK}" == "true" ]]; then
    log "AUTO_ROLLBACK=true; rolling back to Blue"
    ROLLBACK_REASON="${ROLLBACK_REASON:-post-switch verification failed}" "${SCRIPT_DIR}/rollback.sh"
  else
    log "AUTO_ROLLBACK=false; manual rollback command: make deploy-rollback"
  fi
}

print_observability_hints() {
  cat <<EOF

Deployment observability checklist:
  Prometheus: ${PROMETHEUS_URL:-http://localhost:9090}
  Grafana:    ${GRAFANA_URL:-http://localhost:3000}
  Metrics:
    financial_http_errors_total
    financial_http_request_duration_seconds
    financial_invalid_state_transition_total
    financial_reconciliation_failures_total
    financial_redis_fallback_total
    financial_readiness_dependency_status
  Logs:
    docker compose logs -f ${NGINX_SERVICE} ${BLUE_SERVICE} ${GREEN_SERVICE}
  Consistency:
    make deploy-verify
EOF
}

deploy() {
  log "Starting Phase 12 Blue-Green deployment simulation"
  log "Deployment id: ${DEPLOYMENT_ID}"
  log "Base URL: ${BASE_URL}; Green URL: ${GREEN_URL}"
  ensure_base_stack
  start_green
  verify_green_before_switch
  switch_to_green
}

case "${COMMAND}" in
  deploy)
    deploy
    ;;
  start-green)
    start_green
    ;;
  verify-green)
    verify_green_before_switch
    ;;
  switch-green)
    switch_to_green
    ;;
  *)
    cat >&2 <<EOF
Usage: $0 [deploy|start-green|verify-green|switch-green]
EOF
    exit 2
    ;;
esac
