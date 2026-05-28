"""Application configuration."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "financial-event-api"
    app_env: str = "local"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql://postgres:password@localhost:5432/financial_events"
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True
    redis_lock_ttl_ms: int = 3000
    redis_idempotency_cache_ttl_seconds: int = 86400
    redis_socket_timeout_ms: int = 200
    redis_max_connections: int = 50
    log_level: str = "INFO"
    metrics_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("debug", "metrics_enabled", "redis_enabled", mode="before")
    @classmethod
    def parse_boolish(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {
                "1",
                "true",
                "yes",
                "on",
                "local",
                "development",
                "debug",
            }:
                return True
            if normalized in {
                "0",
                "false",
                "no",
                "off",
                "release",
                "production",
                "prod",
            }:
                return False
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
