#!/usr/bin/env bash

set -euo pipefail

PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:8080}"
INTERNAL_BASE_URL="${INTERNAL_BASE_URL:-http://localhost:8081}"
CURL_TIMEOUT_SECONDS="${CURL_TIMEOUT_SECONDS:-5}"
CURL_RETRIES="${CURL_RETRIES:-5}"
CURL_RETRY_DELAY_SECONDS="${CURL_RETRY_DELAY_SECONDS:-2}"

failures=0

curl_status() {
  local method="$1"
  local url="$2"
  local data="${3:-}"

  if [[ -n "${data}" ]]; then
    curl -sS -o /tmp/nginx-access-body.$$ \
      -w "%{http_code}" \
      --connect-timeout "${CURL_TIMEOUT_SECONDS}" \
      --max-time "${CURL_TIMEOUT_SECONDS}" \
      --retry "${CURL_RETRIES}" \
      --retry-delay "${CURL_RETRY_DELAY_SECONDS}" \
      -X "${method}" \
      -H "Content-Type: application/json" \
      --data "${data}" \
      "${url}"
  else
    curl -sS -o /tmp/nginx-access-body.$$ \
      -w "%{http_code}" \
      --connect-timeout "${CURL_TIMEOUT_SECONDS}" \
      --max-time "${CURL_TIMEOUT_SECONDS}" \
      --retry "${CURL_RETRIES}" \
      --retry-delay "${CURL_RETRY_DELAY_SECONDS}" \
      -X "${method}" \
      "${url}"
  fi
}

assert_status_in() {
  local label="$1"
  local actual="$2"
  shift 2
  local allowed=("$@")

  for expected in "${allowed[@]}"; do
    if [[ "${actual}" == "${expected}" ]]; then
      printf "PASS %-48s status=%s\n" "${label}" "${actual}"
      return 0
    fi
  done

  printf "FAIL %-48s status=%s expected=%s\n" "${label}" "${actual}" "${allowed[*]}"
  failures=$((failures + 1))
}

check_endpoint() {
  local label="$1"
  local method="$2"
  local url="$3"
  shift 3
  local status

  status="$(curl_status "${method}" "${url}" || true)"
  status="${status:-000}"
  assert_status_in "${label}" "${status}" "$@"
}

trap 'rm -f /tmp/nginx-access-body.$$' EXIT

echo "== Ops Phase 3 Nginx Access Control Check =="
echo "Public base:   ${PUBLIC_BASE_URL}"
echo "Internal base: ${INTERNAL_BASE_URL}"
echo ""

check_endpoint "public GET /health" "GET" "${PUBLIC_BASE_URL}/health" 200
check_endpoint "public GET /ready must be blocked" "GET" "${PUBLIC_BASE_URL}/ready" 403 404
check_endpoint "public GET /metrics must be blocked" "GET" "${PUBLIC_BASE_URL}/metrics" 403 404
check_endpoint "public GET /docs must be blocked" "GET" "${PUBLIC_BASE_URL}/docs" 403 404
check_endpoint "public GET /redoc must be blocked" "GET" "${PUBLIC_BASE_URL}/redoc" 403 404
check_endpoint "public GET /openapi.json must be blocked" "GET" "${PUBLIC_BASE_URL}/openapi.json" 403 404
check_endpoint "public GET /nginx_status must be blocked" "GET" "${PUBLIC_BASE_URL}/nginx_status" 403 404
check_endpoint "public GET /50x.html must be blocked" "GET" "${PUBLIC_BASE_URL}/50x.html" 403 404
check_endpoint "public GET /admin/debug must be blocked" "GET" "${PUBLIC_BASE_URL}/admin/debug" 403 404
check_endpoint "public GET /debug/vars must be blocked" "GET" "${PUBLIC_BASE_URL}/debug/vars" 403 404
check_endpoint "public GET non-allowlisted API must be blocked" "GET" "${PUBLIC_BASE_URL}/api/v1/accounts/ACC-001/balance" 403 404
check_endpoint "public GET /unknown must be blocked" "GET" "${PUBLIC_BASE_URL}/unknown" 404
check_endpoint "public GET transaction endpoint must be method-blocked" "GET" "${PUBLIC_BASE_URL}/api/v1/transaction-events" 403 404 405

unsigned_body='{"external_event_id":"OPS3-UNSIGNED-CHECK","account_no":"ACC-001","event_type":"DEPOSIT","amount":1000,"currency":"KRW","occurred_at":"2026-05-30T00:00:00Z"}'
unsigned_status="$(curl_status "POST" "${PUBLIC_BASE_URL}/api/v1/transaction-events" "${unsigned_body}" || true)"
unsigned_status="${unsigned_status:-000}"
assert_status_in "public POST transaction without HMAC must fail" "${unsigned_status}" 400 401 403 422

check_endpoint "internal GET /health" "GET" "${INTERNAL_BASE_URL}/health" 200
check_endpoint "internal GET /ready" "GET" "${INTERNAL_BASE_URL}/ready" 200
check_endpoint "internal GET /metrics" "GET" "${INTERNAL_BASE_URL}/metrics" 200

metrics_body="$(cat /tmp/nginx-access-body.$$ 2>/dev/null || true)"
if grep -q "financial_http_requests_total" <<<"${metrics_body}"; then
  printf "PASS %-48s metric=financial_http_requests_total\n" "internal metrics contains custom metric"
else
  printf "FAIL %-48s metric missing\n" "internal metrics contains custom metric"
  failures=$((failures + 1))
fi

if [[ "${failures}" -ne 0 ]]; then
  echo ""
  echo "Nginx access control check failed: ${failures} failure(s)"
  exit 1
fi

echo ""
echo "Nginx access control check passed."
