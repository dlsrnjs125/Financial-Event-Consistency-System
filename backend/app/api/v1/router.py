"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.transaction_events import router as transaction_events_router
from app.core.config import settings

router = APIRouter()
if settings.recovery_admin_api_enabled:
    from app.api.v1.recovery import router as recovery_router

    router.include_router(recovery_router, prefix="/internal")
router.include_router(transaction_events_router)
