"""Application configuration."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "financial-event-api"
    app_env: str = "local"
    deployment_color: str = "local"
    instance_id: str = "local"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql://postgres:password@localhost:5432/financial_events"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout: int = 30
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True
    redis_lock_enabled: bool = True
    idempotency_cache_enabled: bool = False
    redis_lock_ttl_ms: int = 3000
    redis_idempotency_cache_ttl_seconds: int = 86400
    redis_socket_timeout_ms: int = 200
    redis_max_connections: int = 50
    hmac_enabled: bool = True
    hmac_allowed_skew_seconds: int = 300
    external_client_secrets: str = ""
    enable_partner_hmac_auth: bool = False
    partner_hmac_timestamp_skew_seconds: int = 300
    partner_hmac_allow_next_dry_run: bool = False
    partner_hmac_secrets: str = ""
    log_level: str = "INFO"
    metrics_enabled: bool = True
    write_suspend_state_file: str = "reports/runtime/write-suspend-state.json"
    write_suspend_retry_after_seconds: int = 30
    recovery_admin_api_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "debug",
        "metrics_enabled",
        "redis_enabled",
        "redis_lock_enabled",
        "idempotency_cache_enabled",
        "hmac_enabled",
        "enable_partner_hmac_auth",
        "partner_hmac_allow_next_dry_run",
        "recovery_admin_api_enabled",
        mode="before",
    )
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
