"""Phase 1 application skeleton tests."""

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import health
from app.main import app


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_response_contains_service_and_environment():
    client = TestClient(app)

    response = client.get("/health")
    body = response.json()

    assert "status" in body
    assert "service" in body
    assert "environment" in body
    assert "deployment_color" in body
    assert "instance_id" in body


def test_ready_returns_200_when_dependencies_are_available(monkeypatch):
    monkeypatch.setattr(health, "check_database_connection", lambda: True)
    monkeypatch.setattr(health, "check_redis_connection", lambda: True)
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "mode": "normal",
        "checks": {"postgres": "ok", "redis": "ok"},
    }


def test_ready_returns_200_degraded_when_only_redis_fails(monkeypatch):
    monkeypatch.setattr(health, "check_database_connection", lambda: True)
    monkeypatch.setattr(health, "check_redis_connection", lambda: False)
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "mode": "degraded",
        "checks": {"postgres": "ok", "redis": "degraded"},
    }


def test_ready_returns_503_when_postgres_fails(monkeypatch):
    monkeypatch.setattr(health, "check_database_connection", lambda: False)
    monkeypatch.setattr(health, "check_redis_connection", lambda: True)
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "mode": "unavailable",
        "checks": {"postgres": "failed", "redis": "ok"},
    }


def test_metrics_returns_prometheus_format():
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "http_requests_total" in response.text
    assert "app_info" in response.text


def test_recovery_admin_api_is_disabled_by_default():
    client = TestClient(app)

    response = client.get("/api/v1/recovery-cases")

    assert response.status_code == 404


def test_common_http_error_response_contains_error_shape():
    @app.get("/__test_http_error")
    def raise_http_error():
        raise HTTPException(status_code=404, detail="missing")

    client = TestClient(app)

    response = client.get("/__test_http_error")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["message"] == "missing"
    assert response.json()["error"]["request_id"].startswith("req-")


def test_common_unhandled_error_response_contains_error_shape():
    @app.get("/__test_unhandled_error")
    def raise_unhandled_error():
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/__test_unhandled_error")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert response.json()["error"]["message"] == "Unexpected server error"
    assert response.json()["error"]["request_id"].startswith("req-")
