#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
READY_BASE_URL="${READY_BASE_URL:-${BASE_URL}}"
CLIENT_ID="${CLIENT_ID:-bank-a}"
CLIENT_SECRET="${CLIENT_SECRET:-change-me-secret}"
ACCOUNT_NO="${ACCOUNT_NO:-ACC-001}"
SMOKE_ACCOUNT_NO="${SMOKE_ACCOUNT_NO:-${ACCOUNT_NO}}"
API_PATH="${API_PATH:-/api/v1/transaction-events}"

python3 - "$BASE_URL" "$CLIENT_ID" "$CLIENT_SECRET" "$SMOKE_ACCOUNT_NO" "$API_PATH" "$READY_BASE_URL" <<'PY'
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

base_url, client_id, client_secret, account_no, api_path, ready_base_url = sys.argv[1:7]


def request(method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None):
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers or {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = response.read().decode()
            return response.status, payload
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def sign(method: str, path: str, timestamp: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    base_string = f"{method}\n{path}\n{timestamp}\n{body_hash}"
    return hmac.new(client_secret.encode(), base_string.encode(), hashlib.sha256).hexdigest()


def hmac_headers(method: str, path: str, body: bytes, idempotency_key: str) -> dict[str, str]:
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return {
        "Content-Type": "application/json",
        "X-Client-Id": client_id,
        "X-Timestamp": timestamp,
        "X-Signature": sign(method, path, timestamp, body),
        "Idempotency-Key": idempotency_key,
    }


def assert_status(name: str, actual: int, allowed: set[int]) -> None:
    if actual not in allowed:
        raise SystemExit(f"{name} returned {actual}, expected one of {sorted(allowed)}")
    print(f"{name}: {actual}")


health_status, _ = request("GET", "/health")
assert_status("/health", health_status, {200})

def request_to(base: str, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None):
    req = urllib.request.Request(
        f"{base}{path}",
        data=body,
        headers=headers or {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = response.read().decode()
            return response.status, payload
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


ready_status, ready_body = request_to(ready_base_url, "GET", "/ready")
assert_status("/ready", ready_status, {200})
ready_payload = json.loads(ready_body)
if ready_payload.get("status") != "ready":
    raise SystemExit(f"/ready payload was not ready: {ready_payload}")
if ready_payload.get("checks", {}).get("postgres") != "ok":
    raise SystemExit(f"postgres dependency was not ok: {ready_payload}")
if ready_payload.get("checks", {}).get("redis") not in {"ok", "degraded"}:
    raise SystemExit(f"redis dependency had unexpected state: {ready_payload}")
print(f"/ready mode: {ready_payload.get('mode')}, redis={ready_payload.get('checks', {}).get('redis')}")

suffix = f"{int(time.time() * 1000)}"
payload = {
    "external_event_id": f"BG-SMOKE-{suffix}",
    "account_no": account_no,
    "event_type": "DEPOSIT",
    "amount": 1000,
    "currency": "KRW",
    "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
}
body = canonical_json(payload)
idempotency_key = f"bg-smoke-{suffix}"
headers = hmac_headers("POST", api_path, body, idempotency_key)

first_status, first_body = request("POST", api_path, body, headers)
assert_status("transaction create", first_status, {200, 201, 202})

second_status, second_body = request("POST", api_path, body, headers)
assert_status("idempotency replay", second_status, {200, 201, 202})

try:
    first_json = json.loads(first_body or "{}")
    second_json = json.loads(second_body or "{}")
except json.JSONDecodeError as exc:
    raise SystemExit(f"transaction response was not JSON: {exc}") from exc

first_event_id = first_json.get("event_id")
second_event_id = second_json.get("event_id")
if first_event_id and second_event_id:
    if first_event_id != second_event_id:
        raise SystemExit(
            f"idempotency replay returned different event_id values: "
            f"{first_event_id} != {second_event_id}"
        )
    print(f"idempotency replay event_id: {first_event_id}")
elif first_status in {200, 201} and second_status in {200, 201}:
    raise SystemExit(
        "idempotency replay did not expose event_id for successful responses"
    )
else:
    print("idempotency replay accepted non-terminal processing response")

invalid_payload = dict(payload)
invalid_payload["amount"] = 0
invalid_body = canonical_json(invalid_payload)
invalid_headers = hmac_headers("POST", api_path, invalid_body, f"bg-invalid-{suffix}")
invalid_status, _ = request("POST", api_path, invalid_body, invalid_headers)
assert_status("validation failure", invalid_status, {400, 422})

print("Deployment smoke passed.")
PY
