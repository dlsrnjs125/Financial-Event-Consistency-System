"""Integration tests for observability metrics exposure."""

from fastapi.testclient import TestClient

from app.main import app
from app.observability.metrics import (
    record_hmac_auth_failure,
    record_idempotency_decision,
    record_redis_lock_result,
    record_transaction_processed,
)


def test_metrics_endpoint_exposes_custom_financial_metrics():
    record_idempotency_decision("STARTED", "db")
    record_redis_lock_result("success")
    record_hmac_auth_failure("invalid_signature")
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "financial_http_requests_total" in response.text
    assert "financial_idempotency_decisions_total" in response.text
    assert "financial_redis_lock_acquired_total" in response.text
    assert "financial_hmac_auth_failures_total" in response.text


def test_transaction_metric_is_exposed_after_helper_call():
    record_transaction_processed("DEPOSIT", "COMPLETED", "processed")
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "financial_transaction_events_total" in response.text
