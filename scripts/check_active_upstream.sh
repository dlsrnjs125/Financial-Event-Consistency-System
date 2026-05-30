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
    EXPECTED_INSTANCE="api-blue"
    ;;
  green)
    EXPECTED_UPSTREAM="api-green:8000"
    EXPECTED_INSTANCE="api-green"
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

if [[ "${EXPECTED_COLOR}" == "green" ]]; then
  compose_green_profile ps "${GREEN_SERVICE}"
  if ! compose_green_profile ps --status running --services | grep -q "^${GREEN_SERVICE}$"; then
    log "Green service is not running while active upstream expects Green"
    exit 1
  fi
fi

python3 - "${BASE_URL}/health" "${EXPECTED_COLOR}" "${EXPECTED_INSTANCE}" <<'PY'
import json
import sys
import urllib.request

url, expected_color, expected_instance = sys.argv[1:4]

with urllib.request.urlopen(url, timeout=5) as response:
    payload = json.loads(response.read().decode())

actual_color = payload.get("deployment_color")
actual_instance = payload.get("instance_id")

if actual_color != expected_color:
    print(
        f"deployment_color mismatch: expected={expected_color}, actual={actual_color}",
        file=sys.stderr,
    )
    raise SystemExit(1)

if actual_instance != expected_instance:
    print(
        f"instance_id mismatch: expected={expected_instance}, actual={actual_instance}",
        file=sys.stderr,
    )
    raise SystemExit(1)

print(
    f"Routed response identity verified: "
    f"deployment_color={actual_color}, instance_id={actual_instance}"
)
PY

log "Active upstream verified: ${EXPECTED_COLOR} (${EXPECTED_UPSTREAM})"
