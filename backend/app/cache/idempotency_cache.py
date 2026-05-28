"""Redis-backed completed idempotency response cache."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.cache.redis_keys import idempotency_cache_key


@dataclass(frozen=True)
class CachedIdempotencyResponse:
    request_hash: str
    response_code: int
    response_body: Any


class IdempotencyResponseCache:
    def __init__(self, redis_client, ttl_seconds: int = 86400) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    def get(self, idempotency_key: str) -> CachedIdempotencyResponse | None:
        try:
            cached = self.redis_client.get(idempotency_cache_key(idempotency_key))
        except Exception:
            return None
        if cached is None:
            return None

        try:
            data = json.loads(cached)
            return CachedIdempotencyResponse(
                request_hash=data["request_hash"],
                response_code=int(data["response_code"]),
                response_body=data.get("response_body"),
            )
        except (TypeError, ValueError, KeyError):
            return None

    def set_completed(
        self,
        idempotency_key: str,
        request_hash: str,
        response_code: int,
        response_body: Any,
    ) -> None:
        payload = {
            "request_hash": request_hash,
            "response_code": response_code,
            "response_body": response_body,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        try:
            self.redis_client.setex(
                idempotency_cache_key(idempotency_key),
                self.ttl_seconds,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception:
            return

    def delete(self, idempotency_key: str) -> None:
        try:
            self.redis_client.delete(idempotency_cache_key(idempotency_key))
        except Exception:
            return
