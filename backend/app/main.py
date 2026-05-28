from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.v1.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.metrics.prometheus import router as metrics_router
from app.observability.middleware import request_context_middleware

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    description="금융 거래 이벤트 중복 처리 검증 시스템",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.middleware("http")(request_context_middleware)


api_router.include_router(v1_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(api_router, prefix=settings.api_prefix)
register_exception_handlers(app)


@app.get("/", tags=["Root"])
def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "description": "금융 거래 이벤트 중복 처리 검증 시스템",
        "documentation": "/docs",
    }
