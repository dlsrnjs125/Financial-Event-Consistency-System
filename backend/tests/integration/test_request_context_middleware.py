"""Integration tests for request context middleware."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import unhandled_exception_handler
from app.main import app
from app.observability.middleware import request_context_middleware


def test_response_includes_trace_and_request_id_headers():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"].startswith("trace-")
    assert response.headers["X-Request-ID"].startswith("req-")


def test_request_id_header_is_preserved():
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-ID": "req-custom"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-custom"


def test_trace_id_header_is_preserved_on_metrics_endpoint():
    client = TestClient(app)

    response = client.get("/metrics", headers={"X-Trace-ID": "trace-custom"})

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == "trace-custom"


def test_exception_response_keeps_request_id_header():
    test_app = FastAPI()
    test_app.middleware("http")(request_context_middleware)
    test_app.add_exception_handler(Exception, unhandled_exception_handler)

    @test_app.get("/__observability_error")
    def raise_error():
        raise RuntimeError("boom")

    client = TestClient(test_app, raise_server_exceptions=False)

    response = client.get(
        "/__observability_error", headers={"X-Request-ID": "req-error"}
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "req-error"
