"""Domain Prometheus metrics and safe recording helpers."""

from collections.abc import Callable
from typing import ParamSpec, TypeVar

from prometheus_client import Counter, Gauge, Histogram

P = ParamSpec("P")
T = TypeVar("T")

STATUS_CLASSES = {"2xx", "3xx", "4xx", "5xx", "unknown"}
EVENT_TYPES = {"DEPOSIT", "WITHDRAW", "CANCEL", "unknown"}
TRANSACTION_STATUSES = {
    "RECEIVED",
    "VALIDATED",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "SETTLED",
    "unknown",
}
TRANSACTION_RESULTS = {"processed", "duplicated", "failed", "unknown"}
IDEMPOTENCY_DECISIONS = {
    "STARTED",
    "ALREADY_PROCESSING",
    "REPLAY_COMPLETED",
    "REPLAY_FAILED",
    "unknown",
}
IDEMPOTENCY_SOURCES = {"db", "cache", "unknown"}
REDIS_RESULTS = {"success", "failure", "unavailable", "rejected", "unknown"}
REDIS_OPERATIONS = {
    "lock_acquire",
    "lock_release",
    "cache_get",
    "cache_set",
    "cache_delete",
    "unknown",
}
DEPENDENCIES = {"redis", "postgres", "unknown"}
DEPENDENCY_RESULTS = {"success", "failure", "fallback", "unknown"}
FAILURE_REASONS = {
    "timeout",
    "connection_error",
    "integrity_conflict",
    "unavailable",
    "unknown",
}
HMAC_FAILURE_REASONS = {
    "missing_header",
    "unknown_client",
    "disabled_client",
    "invalid_timestamp",
    "expired_timestamp",
    "invalid_signature",
    "unknown",
}
ENDPOINTS = {"transaction_events", "unknown"}
STATE_RESULTS = {"allowed", "rejected", "unknown"}

financial_http_requests_total = Counter(
    "financial_http_requests_total",
    "Total HTTP requests by bounded route and status class.",
    ["method", "route", "status_class"],
)
financial_http_request_duration_seconds = Histogram(
    "financial_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "route"],
    buckets=[0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0],
)
financial_http_errors_total = Counter(
    "financial_http_errors_total",
    "Total HTTP error responses by bounded route and status class.",
    ["method", "route", "status_class"],
)
financial_transaction_events_total = Counter(
    "financial_transaction_events_total",
    "Transaction event outcomes.",
    ["event_type", "status", "result"],
)
financial_transaction_event_processed_total = Counter(
    "financial_transaction_event_processed_total",
    "Successfully processed transaction events.",
    ["event_type", "status"],
)
financial_transaction_event_failed_total = Counter(
    "financial_transaction_event_failed_total",
    "Failed transaction events.",
    ["event_type", "status"],
)
financial_transaction_event_conflict_total = Counter(
    "financial_transaction_event_conflict_total",
    "Transaction event conflict or duplicate outcomes.",
    ["event_type", "status"],
)
financial_transaction_processing_duration_seconds = Histogram(
    "financial_transaction_processing_duration_seconds",
    "Transaction event processing duration in seconds.",
    ["event_type"],
    buckets=[0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0],
)
financial_transaction_failures_total = Counter(
    "financial_transaction_failures_total",
    "Transaction processing failures.",
    ["event_type", "status"],
)
financial_duplicate_external_event_total = Counter(
    "financial_duplicate_external_event_total",
    "Duplicate external event detections.",
    ["event_type"],
)
financial_idempotency_decisions_total = Counter(
    "financial_idempotency_decisions_total",
    "Idempotency decisions.",
    ["decision", "source"],
)
financial_idempotency_conflict_total = Counter(
    "financial_idempotency_conflict_total",
    "Idempotency conflicts.",
    ["source"],
)
financial_idempotency_processing_total = Counter(
    "financial_idempotency_processing_total",
    "Idempotency already-processing decisions.",
    ["source"],
)
financial_idempotency_duplicate_total = Counter(
    "financial_idempotency_duplicate_total",
    "Idempotency duplicate/replay decisions.",
    ["source", "decision"],
)
financial_redis_lock_acquired_total = Counter(
    "financial_redis_lock_acquired_total",
    "Redis idempotency lock acquisitions.",
)
financial_redis_lock_rejected_total = Counter(
    "financial_redis_lock_rejected_total",
    "Redis idempotency lock rejected attempts.",
)
financial_redis_unavailable_total = Counter(
    "financial_redis_unavailable_total",
    "Redis unavailable observations.",
    ["operation"],
)
financial_idempotency_cache_hit_total = Counter(
    "financial_idempotency_cache_hit_total",
    "Idempotency response cache hits.",
)
financial_idempotency_cache_miss_total = Counter(
    "financial_idempotency_cache_miss_total",
    "Idempotency response cache misses.",
)
financial_idempotency_cache_set_failure_total = Counter(
    "financial_idempotency_cache_set_failure_total",
    "Idempotency response cache set failures.",
)
financial_redis_operations_total = Counter(
    "financial_redis_operations_total",
    "Redis operation outcomes.",
    ["operation", "result"],
)
financial_redis_operation_total = Counter(
    "financial_redis_operation_total",
    "Redis operation outcomes for Phase 10 fallback tracking.",
    ["operation", "result", "reason"],
)
financial_redis_operation_failed_total = Counter(
    "financial_redis_operation_failed_total",
    "Redis operation failures for Phase 10 fallback tracking.",
    ["operation", "reason"],
)
financial_redis_fallback_total = Counter(
    "financial_redis_fallback_total",
    "Requests continued with PostgreSQL after Redis operation failure.",
    ["operation", "reason"],
)
financial_db_transaction_retry_total = Counter(
    "financial_db_transaction_retry_total",
    "Database transaction retries after concurrency conflicts.",
    ["reason"],
)
financial_readiness_dependency_status = Gauge(
    "financial_readiness_dependency_status",
    "Readiness dependency status. 1 means healthy, 0 means failed.",
    ["dependency"],
)
financial_hmac_auth_failures_total = Counter(
    "financial_hmac_auth_failures_total",
    "HMAC authentication failures.",
    ["reason", "endpoint"],
)
financial_hmac_auth_success_total = Counter(
    "financial_hmac_auth_success_total",
    "HMAC authentication successes.",
    ["endpoint"],
)
financial_invalid_state_transition_total = Counter(
    "financial_invalid_state_transition_total",
    "Rejected transaction state transitions.",
    ["from_status", "to_status"],
)
financial_state_transitions_total = Counter(
    "financial_state_transitions_total",
    "Transaction state transitions.",
    ["from_status", "to_status", "result"],
)
financial_reconciliation_failures_total = Counter(
    "financial_reconciliation_failures_total",
    "Ledger/account reconciliation failures.",
)
financial_reconciliation_last_checked_timestamp = Gauge(
    "financial_reconciliation_last_checked_timestamp",
    "Last reconciliation check timestamp.",
)


def safe_metric(func: Callable[P, T]) -> Callable[P, T | None]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
        try:
            return func(*args, **kwargs)
        except Exception:
            return None

    return wrapper


def status_class(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "unknown"


def normalize_label(value: object, allowed: set[str]) -> str:
    normalized = str(value.value if hasattr(value, "value") else value)
    return normalized if normalized in allowed else "unknown"


@safe_metric
def record_http_request(
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    status = status_class(status_code)
    financial_http_requests_total.labels(
        method=method, route=route, status_class=status
    ).inc()
    financial_http_request_duration_seconds.labels(method=method, route=route).observe(
        duration_seconds
    )
    if status in {"4xx", "5xx"}:
        financial_http_errors_total.labels(
            method=method, route=route, status_class=status
        ).inc()


@safe_metric
def record_transaction_processed(event_type: str, status: str, result: str) -> None:
    normalized_event_type = normalize_label(event_type, EVENT_TYPES)
    normalized_status = normalize_label(status, TRANSACTION_STATUSES)
    normalized_result = normalize_label(result, TRANSACTION_RESULTS)
    financial_transaction_events_total.labels(
        event_type=normalized_event_type,
        status=normalized_status,
        result=normalized_result,
    ).inc()
    if normalized_result == "processed":
        financial_transaction_event_processed_total.labels(
            event_type=normalized_event_type,
            status=normalized_status,
        ).inc()
    elif normalized_result == "duplicated":
        financial_transaction_event_conflict_total.labels(
            event_type=normalized_event_type,
            status=normalized_status,
        ).inc()
        return
    elif normalized_result == "failed":
        financial_transaction_event_failed_total.labels(
            event_type=normalized_event_type,
            status=normalized_status,
        ).inc()
        financial_transaction_failures_total.labels(
            event_type=normalized_event_type,
            status=normalized_status,
        ).inc()


@safe_metric
def record_duplicate_external_event(event_type: str) -> None:
    financial_duplicate_external_event_total.labels(
        event_type=normalize_label(event_type, EVENT_TYPES)
    ).inc()


@safe_metric
def observe_transaction_duration(event_type: str, duration_seconds: float) -> None:
    financial_transaction_processing_duration_seconds.labels(
        event_type=normalize_label(event_type, EVENT_TYPES)
    ).observe(duration_seconds)


@safe_metric
def record_idempotency_decision(decision: str, source: str = "db") -> None:
    normalized_decision = normalize_label(decision, IDEMPOTENCY_DECISIONS)
    normalized_source = normalize_label(source, IDEMPOTENCY_SOURCES)
    financial_idempotency_decisions_total.labels(
        decision=normalized_decision,
        source=normalized_source,
    ).inc()
    if normalized_decision == "ALREADY_PROCESSING":
        financial_idempotency_processing_total.labels(source=normalized_source).inc()
    if normalized_decision in {"ALREADY_PROCESSING", "REPLAY_COMPLETED"}:
        financial_idempotency_duplicate_total.labels(
            source=normalized_source,
            decision=normalized_decision,
        ).inc()


@safe_metric
def record_idempotency_conflict(source: str = "db") -> None:
    financial_idempotency_conflict_total.labels(
        source=normalize_label(source, IDEMPOTENCY_SOURCES)
    ).inc()


@safe_metric
def record_redis_lock_result(result: str) -> None:
    normalized = normalize_label(result, REDIS_RESULTS)
    financial_redis_operations_total.labels(
        operation="lock_acquire", result=normalized
    ).inc()
    if normalized == "success":
        financial_redis_lock_acquired_total.inc()
    elif normalized == "rejected":
        financial_redis_lock_rejected_total.inc()
    elif normalized == "unavailable":
        financial_redis_unavailable_total.labels(operation="lock_acquire").inc()


@safe_metric
def record_redis_operation(operation: str, result: str) -> None:
    normalized_operation = normalize_label(operation, REDIS_OPERATIONS)
    normalized_result = normalize_label(result, REDIS_RESULTS)
    financial_redis_operations_total.labels(
        operation=normalized_operation,
        result=normalized_result,
    ).inc()
    if normalized_result == "unavailable":
        financial_redis_unavailable_total.labels(operation=normalized_operation).inc()


@safe_metric
def record_redis_operation_v2(
    operation: str, result: str, reason: str = "unknown"
) -> None:
    normalized_operation = normalize_label(operation, REDIS_OPERATIONS)
    normalized_result = normalize_label(result, DEPENDENCY_RESULTS)
    normalized_reason = normalize_label(reason, FAILURE_REASONS)
    financial_redis_operation_total.labels(
        operation=normalized_operation,
        result=normalized_result,
        reason=normalized_reason,
    ).inc()
    if normalized_result == "failure":
        financial_redis_operation_failed_total.labels(
            operation=normalized_operation,
            reason=normalized_reason,
        ).inc()


@safe_metric
def record_redis_fallback(operation: str, reason: str = "unknown") -> None:
    normalized_operation = normalize_label(operation, REDIS_OPERATIONS)
    normalized_reason = normalize_label(reason, FAILURE_REASONS)
    financial_redis_fallback_total.labels(
        operation=normalized_operation,
        reason=normalized_reason,
    ).inc()


@safe_metric
def record_db_transaction_retry(reason: str = "unknown") -> None:
    financial_db_transaction_retry_total.labels(
        reason=normalize_label(reason, FAILURE_REASONS)
    ).inc()


@safe_metric
def record_readiness_dependency_status(dependency: str, healthy: bool) -> None:
    financial_readiness_dependency_status.labels(
        dependency=normalize_label(dependency, DEPENDENCIES)
    ).set(1 if healthy else 0)


@safe_metric
def record_idempotency_cache_hit() -> None:
    financial_idempotency_cache_hit_total.inc()
    record_redis_operation("cache_get", "success")
    record_redis_operation_v2("cache_get", "success")


@safe_metric
def record_idempotency_cache_miss() -> None:
    financial_idempotency_cache_miss_total.inc()
    record_redis_operation("cache_get", "failure")
    record_redis_operation_v2("cache_get", "success")


@safe_metric
def record_idempotency_cache_set_failure() -> None:
    financial_idempotency_cache_set_failure_total.inc()
    record_redis_operation("cache_set", "failure")
    record_redis_operation_v2("cache_set", "failure")


@safe_metric
def record_hmac_auth_success(endpoint: str = "transaction_events") -> None:
    financial_hmac_auth_success_total.labels(
        endpoint=normalize_label(endpoint, ENDPOINTS)
    ).inc()


@safe_metric
def record_hmac_auth_failure(
    reason: str,
    endpoint: str = "transaction_events",
) -> None:
    financial_hmac_auth_failures_total.labels(
        reason=normalize_label(reason, HMAC_FAILURE_REASONS),
        endpoint=normalize_label(endpoint, ENDPOINTS),
    ).inc()


@safe_metric
def record_state_transition(from_status: str, to_status: str, result: str) -> None:
    normalized_from = normalize_label(from_status, TRANSACTION_STATUSES)
    normalized_to = normalize_label(to_status, TRANSACTION_STATUSES)
    normalized_result = normalize_label(result, STATE_RESULTS)
    financial_state_transitions_total.labels(
        from_status=normalized_from,
        to_status=normalized_to,
        result=normalized_result,
    ).inc()
    if normalized_result == "rejected":
        financial_invalid_state_transition_total.labels(
            from_status=normalized_from,
            to_status=normalized_to,
        ).inc()


@safe_metric
def record_reconciliation_failure() -> None:
    financial_reconciliation_failures_total.inc()
