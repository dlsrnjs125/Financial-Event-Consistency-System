#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
BLUE_SERVICE="${BLUE_SERVICE:-api-blue}"
GREEN_SERVICE="${GREEN_SERVICE:-api-green}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
INTERNAL_BASE_URL="${INTERNAL_BASE_URL:-http://localhost:8081}"
BLUE_URL="${BLUE_URL:-http://localhost:8000}"
GREEN_URL="${GREEN_URL:-http://localhost:8001}"
GREEN_UPSTREAM_URL="${GREEN_UPSTREAM_URL:-http://api-green:8000}"
VERIFY_TIMEOUT_SECONDS="${VERIFY_TIMEOUT_SECONDS:-60}"
AUTO_ROLLBACK="${AUTO_ROLLBACK:-true}"
RUN_SECURITY_LOG_CHECK="${RUN_SECURITY_LOG_CHECK:-true}"
RUN_MIGRATION_SMOKE="${RUN_MIGRATION_SMOKE:-true}"
RUN_DEPLOY_VERIFY="${RUN_DEPLOY_VERIFY:-false}"
CLIENT_ID="${CLIENT_ID:-bank-a}"
CLIENT_SECRET="${CLIENT_SECRET:-change-me-secret}"
ACCOUNT_NO="${ACCOUNT_NO:-ACC-001}"

NGINX_DIR="${ROOT_DIR}/infra/nginx"
ACTIVE_COLOR_FILE="${ACTIVE_COLOR_FILE:-${NGINX_DIR}/.active-color}"
ACTIVE_UPSTREAM_FILE="${ACTIVE_UPSTREAM_FILE:-${NGINX_DIR}/conf.d/upstream-active.conf}"
BLUE_UPSTREAM_TEMPLATE="${BLUE_UPSTREAM_TEMPLATE:-${NGINX_DIR}/conf.d/upstream-active.conf.blue}"
GREEN_UPSTREAM_TEMPLATE="${GREEN_UPSTREAM_TEMPLATE:-${NGINX_DIR}/conf.d/upstream-active.conf.green}"

DEPLOYMENT_ID="${DEPLOYMENT_ID:-deploy-$(date -u +%Y%m%dT%H%M%SZ)-$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)}"

log() {
  printf '[%s] %s\n' "${DEPLOYMENT_ID}" "$*"
}

require_command() {
  local name="$1"
  local hint="$2"

  if ! command -v "${name}" >/dev/null 2>&1; then
    log "${name} is required. ${hint}"
    return 1
  fi
}

require_deploy_tools() {
  require_command curl "Install curl and retry."
  require_command python3 "Install Python 3 and retry."
  if [[ "${RUN_SECURITY_LOG_CHECK}" == "true" ]]; then
    require_command rg "Install ripgrep or set RUN_SECURITY_LOG_CHECK=false."
  fi
}

compose() {
  (cd "${ROOT_DIR}" && ${DOCKER_COMPOSE} -f "${COMPOSE_FILE}" "$@")
}

compose_green_profile() {
  (cd "${ROOT_DIR}" && ${DOCKER_COMPOSE} -f "${COMPOSE_FILE}" --profile green-deployment "$@")
}

current_active_color() {
  if [[ -f "${ACTIVE_COLOR_FILE}" ]]; then
    tr -d '[:space:]' < "${ACTIVE_COLOR_FILE}"
    return
  fi

  if grep -q "api-green" "${ACTIVE_UPSTREAM_FILE}" 2>/dev/null; then
    printf 'green'
  else
    printf 'blue'
  fi
}

nginx_test() {
  compose exec -T "${NGINX_SERVICE}" nginx -t
}

nginx_reload() {
  compose exec -T "${NGINX_SERVICE}" nginx -s reload
}

wait_for_endpoint() {
  local url="$1"
  local label="$2"
  local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))

  log "Waiting for ${label}: ${url}"
  while (( SECONDS < deadline )); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      log "${label} is healthy"
      return 0
    fi
    sleep 2
  done

  log "${label} did not become healthy within ${VERIFY_TIMEOUT_SECONDS}s"
  return 1
}

verify_ready_body() {
  local url="$1"
  local label="$2"

  python3 - "$url" "$label" <<'PY'
import json
import sys
import urllib.error
import urllib.request

url = sys.argv[1]
label = sys.argv[2]

try:
    with urllib.request.urlopen(url, timeout=5) as response:
        status = response.status
        payload = json.loads(response.read().decode())
except urllib.error.HTTPError as exc:
    print(f"{label} readiness failed with status {exc.code}", file=sys.stderr)
    raise SystemExit(1)

if status != 200:
    print(f"{label} readiness status was {status}", file=sys.stderr)
    raise SystemExit(1)

if payload.get("status") != "ready":
    print(f"{label} readiness payload was not ready: {payload}", file=sys.stderr)
    raise SystemExit(1)

checks = payload.get("checks", {})
if checks.get("postgres") != "ok":
    print(f"{label} postgres dependency is not ok: {payload}", file=sys.stderr)
    raise SystemExit(1)

if checks.get("redis") not in {"ok", "degraded"}:
    print(f"{label} redis dependency has unexpected state: {payload}", file=sys.stderr)
    raise SystemExit(1)

print(f"{label} readiness accepted: mode={payload.get('mode')}, redis={checks.get('redis')}")
PY
}

set_active_upstream() {
  local target_color="$1"
  local template
  local previous_color
  local backup
  local candidate

  case "${target_color}" in
    blue) template="${BLUE_UPSTREAM_TEMPLATE}" ;;
    green) template="${GREEN_UPSTREAM_TEMPLATE}" ;;
    *)
      log "Unknown upstream color: ${target_color}"
      return 1
      ;;
  esac

  if [[ ! -f "${template}" ]]; then
    log "Missing upstream template: ${template}"
    return 1
  fi

  previous_color="$(current_active_color)"
  backup="$(mktemp "${NGINX_DIR}/conf.d/upstream-active.conf.backup.XXXXXX")"
  candidate="$(mktemp "${NGINX_DIR}/conf.d/upstream-active.conf.tmp.XXXXXX")"
  cp "${ACTIVE_UPSTREAM_FILE}" "${backup}"
  cp "${template}" "${candidate}"

  log "Testing current Nginx config before switching ${previous_color} -> ${target_color}"
  nginx_test

  mv "${candidate}" "${ACTIVE_UPSTREAM_FILE}"

  if ! nginx_test; then
    log "Nginx config test failed after switching to ${target_color}; restoring ${previous_color}"
    mv "${backup}" "${ACTIVE_UPSTREAM_FILE}"
    printf '%s\n' "${previous_color}" > "${ACTIVE_COLOR_FILE}"
    nginx_test || true
    return 1
  fi

  if ! nginx_reload; then
    log "Nginx reload failed after switching to ${target_color}; restoring ${previous_color}"
    mv "${backup}" "${ACTIVE_UPSTREAM_FILE}"
    printf '%s\n' "${previous_color}" > "${ACTIVE_COLOR_FILE}"
    if nginx_test; then
      nginx_reload || true
    fi
    return 1
  fi

  printf '%s\n' "${target_color}" > "${ACTIVE_COLOR_FILE}"
  rm -f "${backup}"
  log "Nginx upstream switched to ${target_color}"
}

run_security_log_check() {
  if [[ "${RUN_SECURITY_LOG_CHECK}" == "true" ]]; then
    log "Running security-log-check"
    (cd "${ROOT_DIR}" && make security-log-check)
  else
    log "Skipping security-log-check because RUN_SECURITY_LOG_CHECK=false"
  fi
}

run_migration_smoke() {
  if [[ "${RUN_MIGRATION_SMOKE}" == "true" ]]; then
    log "Running migration-smoke"
    (cd "${ROOT_DIR}" && make migration-smoke)
  else
    log "Skipping migration-smoke because RUN_MIGRATION_SMOKE=false"
  fi
}

run_deployment_smoke() {
  local url="$1"
  local ready_url="${2:-${url}}"
  log "Running deployment smoke against ${url}"
  BASE_URL="${url}" READY_BASE_URL="${ready_url}" CLIENT_ID="${CLIENT_ID}" CLIENT_SECRET="${CLIENT_SECRET}" ACCOUNT_NO="${ACCOUNT_NO}" \
    "${ROOT_DIR}/scripts/deployment-smoke.sh"
}

verify_nginx_can_reach_green() {
  log "Verifying Nginx container can reach Green upstream: ${GREEN_UPSTREAM_URL}/health"
  compose exec -T "${NGINX_SERVICE}" sh -c \
    "wget -qO- '${GREEN_UPSTREAM_URL}/health' >/dev/null"
}

run_deploy_verify_if_enabled() {
  if [[ "${RUN_DEPLOY_VERIFY}" == "true" ]]; then
    log "Running deploy consistency verification"
    (cd "${ROOT_DIR}" && make deploy-verify)
  else
    log "Skipping deploy-verify by default; run make deploy-verify or RUN_DEPLOY_VERIFY=true for DB consistency verification"
  fi
}
