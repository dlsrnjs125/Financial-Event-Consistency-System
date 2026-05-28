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
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.observability.metrics import record_http_request

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
async def metrics() -> Response:
    payload = await run_in_threadpool(generate_latest)
    return Response(payload, media_type=CONTENT_TYPE_LATEST)


async def metrics_middleware(request: Request, call_next, start: float | None = None):
    start = start or perf_counter()
    status_code = 500
    response = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = perf_counter() - start
        endpoint = (
            request.scope.get("route").path
            if request.scope.get("route")
            else request.url.path
        )
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=str(status_code),
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)
        record_http_request(
            method=request.method,
            route=endpoint,
            status_code=status_code,
            duration_seconds=duration,
        )

        if response is not None:
            response.headers["X-Process-Time"] = f"{duration:.6f}"
