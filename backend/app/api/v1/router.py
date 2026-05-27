"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.transaction_events import router as transaction_events_router

router = APIRouter()
router.include_router(transaction_events_router)
