"""Health and readiness endpoints."""

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.db.session import check_database_connection
from app.observability.metrics import record_readiness_dependency_status
from app.redis.client import check_redis_connection

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/ready")
def readiness_check(response: Response) -> dict[str, object]:
    postgres_ok = check_database_connection()
    redis_ok = check_redis_connection()
    record_readiness_dependency_status("postgres", postgres_ok)
    record_readiness_dependency_status("redis", redis_ok)
    checks = {
        "postgres": "ok" if postgres_ok else "failed",
        "redis": "ok" if redis_ok else "degraded",
    }
    ready = postgres_ok

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    mode = "normal" if redis_ok else "degraded"
    return {
        "status": "ready" if ready else "not_ready",
        "mode": mode if ready else "unavailable",
        "checks": checks,
    }
