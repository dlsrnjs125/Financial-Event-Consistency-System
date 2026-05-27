"""Prometheus metrics and endpoint."""

from time import perf_counter

from fastapi import APIRouter, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.core.config import settings

router = APIRouter(tags=["Monitoring"])

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0],
)

app_info = Gauge(
    "app_info",
    "Application information",
    ["service", "environment"],
)
app_info.labels(service=settings.app_name, environment=settings.app_env).set(1)


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def metrics_middleware(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    duration = perf_counter() - start

    endpoint = (
        request.scope.get("route").path
        if request.scope.get("route")
        else request.url.path
    )
    http_requests_total.labels(
        method=request.method,
        endpoint=endpoint,
        status=str(response.status_code),
    ).inc()
    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=endpoint,
    ).observe(duration)

    response.headers["X-Process-Time"] = f"{duration:.6f}"
    return response
