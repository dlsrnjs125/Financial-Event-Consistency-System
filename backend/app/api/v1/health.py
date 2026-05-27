"""Health and readiness endpoints."""

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.db.session import check_database_connection
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
    checks = {
        "database": "ok" if check_database_connection() else "failed",
        "redis": "ok" if check_redis_connection() else "failed",
    }
    ready = all(value == "ok" for value in checks.values())

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
    }
