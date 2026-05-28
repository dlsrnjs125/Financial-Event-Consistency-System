"""Unit tests for observability metric helpers."""

from prometheus_client import REGISTRY

from app.observability import metrics


def sample_value(name: str, labels: dict[str, str]) -> float:
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name and all(
                sample.labels.get(key) == value for key, value in labels.items()
            ):
                return float(sample.value)
    return 0.0


def test_idempotency_decision_metric_increments():
    before = sample_value(
        "financial_idempotency_decisions_total",
        {"decision": "STARTED", "source": "db"},
    )

    metrics.record_idempotency_decision("STARTED", "db")

    after = sample_value(
        "financial_idempotency_decisions_total",
        {"decision": "STARTED", "source": "db"},
    )
    assert after == before + 1


def test_redis_cache_hit_and_miss_metrics_increment():
    hit_before = sample_value("financial_idempotency_cache_hit_total", {})
    miss_before = sample_value("financial_idempotency_cache_miss_total", {})

    metrics.record_idempotency_cache_hit()
    metrics.record_idempotency_cache_miss()

    assert sample_value("financial_idempotency_cache_hit_total", {}) == hit_before + 1
    assert sample_value("financial_idempotency_cache_miss_total", {}) == miss_before + 1


def test_hmac_auth_failure_metric_increments():
    before = sample_value(
        "financial_hmac_auth_failures_total",
        {"reason": "invalid_signature", "endpoint": "transaction_events"},
    )

    metrics.record_hmac_auth_failure("invalid_signature")

    after = sample_value(
        "financial_hmac_auth_failures_total",
        {"reason": "invalid_signature", "endpoint": "transaction_events"},
    )
    assert after == before + 1


def test_invalid_state_transition_metric_increments():
    before = sample_value(
        "financial_invalid_state_transition_total",
        {"from_status": "COMPLETED", "to_status": "PROCESSING"},
    )

    metrics.record_state_transition("COMPLETED", "PROCESSING", "rejected")

    after = sample_value(
        "financial_invalid_state_transition_total",
        {"from_status": "COMPLETED", "to_status": "PROCESSING"},
    )
    assert after == before + 1


def test_unknown_label_values_are_bounded_to_unknown():
    before = sample_value(
        "financial_idempotency_decisions_total",
        {"decision": "unknown", "source": "unknown"},
    )

    metrics.record_idempotency_decision("external-id-should-not-be-a-label", "bad")

    after = sample_value(
        "financial_idempotency_decisions_total",
        {"decision": "unknown", "source": "unknown"},
    )
    assert after == before + 1


def test_metric_helper_does_not_propagate_exceptions(monkeypatch):
    class BrokenCounter:
        def labels(self, **kwargs):
            raise RuntimeError("metric registry unavailable")

    monkeypatch.setattr(
        metrics, "financial_idempotency_decisions_total", BrokenCounter()
    )

    metrics.record_idempotency_decision("STARTED", "db")
