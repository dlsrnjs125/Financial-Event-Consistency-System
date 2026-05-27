#!/bin/bash
# Run k6 tests

set -e

BASE_URL=${1:-http://localhost}

echo "=== K6 Test Suite ==="
echo "Base URL: $BASE_URL"

# Smoke test
echo ""
echo "1. Running Smoke Test..."
k6 run tests/k6/smoke-test.js \
  --vus 5 \
  --duration 10s \
  --env BASE_URL=$BASE_URL \
  --out console

# Peak load test
echo ""
echo "2. Running Peak Load Test..."
k6 run tests/k6/peak-load.js \
  --env BASE_URL=$BASE_URL \
  --out console

# Duplicate storm test
echo ""
echo "3. Running Duplicate Storm Test..."
k6 run tests/k6/duplicate-storm.js \
  --vus 100 \
  --duration 30s \
  --env BASE_URL=$BASE_URL \
  --out console

echo ""
echo "✅ All k6 tests completed"
