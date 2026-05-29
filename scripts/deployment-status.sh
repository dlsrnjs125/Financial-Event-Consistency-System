#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment-lib.sh
source "${SCRIPT_DIR}/deployment-lib.sh"

active_color="$(current_active_color)"

cat <<EOF
=== Phase 12 Deployment Status ===
Deployment id: ${DEPLOYMENT_ID}
Active upstream: ${active_color}
Active color file: ${ACTIVE_COLOR_FILE}
Active upstream file: ${ACTIVE_UPSTREAM_FILE}

EOF

if [[ -f "${ACTIVE_UPSTREAM_FILE}" ]]; then
  sed 's/^/  /' "${ACTIVE_UPSTREAM_FILE}"
fi

cat <<EOF

Docker Compose services:
EOF
compose ps "${NGINX_SERVICE}" "${BLUE_SERVICE}" "${GREEN_SERVICE}" postgres redis || true

cat <<EOF

Endpoint checks:
  Nginx health: curl -i ${BASE_URL}/health
  Nginx ready:  curl -i ${BASE_URL}/ready
  Blue health:  curl -i ${BLUE_URL}/health
  Blue ready:   curl -i ${BLUE_URL}/ready
  Green health: curl -i ${GREEN_URL}/health
  Green ready:  curl -i ${GREEN_URL}/ready

Observability:
  Prometheus: ${PROMETHEUS_URL:-http://localhost:9090}
  Grafana:    ${GRAFANA_URL:-http://localhost:3000}
  Logs:       docker compose logs -f ${NGINX_SERVICE} ${BLUE_SERVICE} ${GREEN_SERVICE}
EOF

curl -fsS "${BASE_URL}/health" >/dev/null 2>&1 && echo "Nginx /health: ok" || echo "Nginx /health: unavailable"
if curl -fsS "${BASE_URL}/ready" >/dev/null 2>&1; then
  echo "Nginx /ready: ok"
else
  echo "Nginx /ready: unavailable"
fi
