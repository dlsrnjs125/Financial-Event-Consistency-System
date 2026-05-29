#!/usr/bin/env bash
set -euo pipefail

REPORT_FILE="${REPORT_FILE:-reports/monitoring/ops1-compose-status.md}"
DOCKER_COMPOSE_MONITORING="${DOCKER_COMPOSE_MONITORING:-docker compose -f docker-compose.yml -f docker-compose.monitoring.yml}"

mkdir -p "$(dirname "${REPORT_FILE}")"

{
  echo "# Ops Phase 1 Docker Compose Status"
  echo
  echo "- Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Tested Commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "- Branch: $(git branch --show-current 2>/dev/null || echo unknown)"
  echo
  echo "> Note: The tested commit can differ from the final PR commit because evidence reports are generated before being committed."
  echo
  echo '```text'
  ${DOCKER_COMPOSE_MONITORING} ps
  echo '```'
} >"${REPORT_FILE}"

echo "Compose status report written: ${REPORT_FILE}"
