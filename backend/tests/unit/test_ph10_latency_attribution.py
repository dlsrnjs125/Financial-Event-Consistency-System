"""Unit tests for PH10 latency attribution diagnosis evidence."""

import copy
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import ph10_latency_attribution  # noqa: E402


def test_sample_evidence_analysis_is_deterministic():
    evidence = ph10_latency_attribution.sample_evidence()

    first = ph10_latency_attribution.analyze_evidence(evidence)
    second = ph10_latency_attribution.analyze_evidence(copy.deepcopy(evidence))

    assert first == second
    assert first["classification"] == "internal_postgres_latency"
    assert ph10_latency_attribution.validate_report_payload(first) == []


def test_baseline_normal_latency_classification():
    evidence = _evidence_with(
        observed={
            "k6_p95_ms": 190,
            "k6_p99_ms": 430,
            "nginx_request_p95_ms": 180,
            "nginx_upstream_p95_ms": 160,
            "fastapi_handler_p95_ms": 130,
            "postgres_phase_p95_ms": 70,
            "redis_phase_p95_ms": 20,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0,
        }
    )

    report = ph10_latency_attribution.analyze_evidence(evidence)

    assert report["classification"] == "baseline_normal_latency"


def test_postgres_dominant_classification():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())

    assert report["classification"] == "internal_postgres_latency"


def test_redis_dominant_classification():
    evidence = _evidence_with(
        observed={
            "k6_p95_ms": 650,
            "k6_p99_ms": 1400,
            "nginx_request_p95_ms": 630,
            "nginx_upstream_p95_ms": 600,
            "fastapi_handler_p95_ms": 560,
            "postgres_phase_p95_ms": 120,
            "redis_phase_p95_ms": 260,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0.01,
        }
    )

    report = ph10_latency_attribution.analyze_evidence(evidence)

    assert report["classification"] == "redis_degraded_latency"


def test_outbound_dependency_classification():
    evidence = _evidence_with(
        observed={
            "k6_p95_ms": 800,
            "k6_p99_ms": 1700,
            "nginx_request_p95_ms": 760,
            "nginx_upstream_p95_ms": 720,
            "fastapi_handler_p95_ms": 700,
            "postgres_phase_p95_ms": 90,
            "redis_phase_p95_ms": 30,
            "outbound_http_p95_ms": 520,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0.01,
        }
    )

    report = ph10_latency_attribution.analyze_evidence(evidence)

    assert report["classification"] == "external_dependency_latency"


def test_edge_or_client_network_classification():
    evidence = _evidence_with(
        observed={
            "k6_p95_ms": 900,
            "k6_p99_ms": 1600,
            "nginx_request_p95_ms": 850,
            "nginx_upstream_p95_ms": 180,
            "fastapi_handler_p95_ms": 140,
            "postgres_phase_p95_ms": 70,
            "redis_phase_p95_ms": 20,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0,
        }
    )

    report = ph10_latency_attribution.analyze_evidence(evidence)

    assert report["classification"] == "edge_or_client_network_latency"


def test_external_endpoint_slow_classification():
    evidence = _evidence_with(
        observed={
            "k6_p95_ms": 900,
            "k6_p99_ms": 1900,
            "nginx_request_p95_ms": 860,
            "nginx_upstream_p95_ms": 830,
            "fastapi_handler_p95_ms": 800,
            "postgres_phase_p95_ms": 100,
            "redis_phase_p95_ms": 30,
            "outbound_http_p95_ms": 520,
            "blackbox_probe_p95_ms": 900,
            "error_rate": 0.02,
        }
    )

    report = ph10_latency_attribution.analyze_evidence(evidence)

    assert report["classification"] == "external_endpoint_slow"


def test_app_http_client_path_issue_classification():
    evidence = _evidence_with(
        observed={
            "k6_p95_ms": 780,
            "k6_p99_ms": 1600,
            "nginx_request_p95_ms": 730,
            "nginx_upstream_p95_ms": 700,
            "fastapi_handler_p95_ms": 680,
            "postgres_phase_p95_ms": 90,
            "redis_phase_p95_ms": 30,
            "outbound_http_p95_ms": 500,
            "blackbox_probe_p95_ms": 180,
            "error_rate": 0.01,
        }
    )

    report = ph10_latency_attribution.analyze_evidence(evidence)

    assert report["classification"] == "app_http_client_path_issue"


def test_missing_evidence_becomes_insufficient():
    report = ph10_latency_attribution.analyze_evidence({"run_id": "missing"})

    assert report["classification"] == "insufficient_evidence"
    assert ph10_latency_attribution.validate_report_payload(report) == []


def test_consistency_violation_is_preserved():
    evidence = _evidence_with(
        consistency={
            "duplicate_ledger_count": 1,
            "duplicate_external_event_count": 0,
            "reconciliation_failure_count": 0,
            "invalid_state_transition_count": 0,
        }
    )

    report = ph10_latency_attribution.analyze_evidence(evidence)

    assert report["consistency_status"] == "VIOLATION_DETECTED"


def test_consistency_violation_cannot_be_reported_clean():
    report = ph10_latency_attribution.analyze_evidence(
        _evidence_with(
            consistency={
                "duplicate_ledger_count": 1,
                "duplicate_external_event_count": 0,
                "reconciliation_failure_count": 0,
                "invalid_state_transition_count": 0,
            }
        )
    )
    report["consistency_status"] = "CLEAN"

    errors = ph10_latency_attribution.validate_report_payload(report)

    assert any(
        "consistency violation cannot be reported as CLEAN" in error for error in errors
    )


def test_k6_only_root_cause_claim_fails_validation():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())
    report["evidence"] = ["k6 p95 increased and therefore database is root cause"]

    errors = ph10_latency_attribution.validate_report_payload(report)

    assert any("k6-only evidence" in error for error in errors)


def test_ph11_completed_claim_fails_validation():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())
    report["evidence"].append("PH11 latency drill completed")

    errors = ph10_latency_attribution.validate_report_payload(report)

    assert any("forbidden claim" in error for error in errors)


def test_sensitive_raw_content_fails_validation():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())
    report["evidence"].append("Authorization: Bearer raw-token")

    errors = ph10_latency_attribution.validate_report_payload(report)

    assert any("sensitive text pattern" in error for error in errors)


def test_forbidden_metric_label_fails_validation():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())
    report["input_summary"]["metric_labels"] = ["route_group", "account_no"]

    errors = ph10_latency_attribution.validate_report_payload(report)

    assert any("forbidden metric label" in error for error in errors)


def test_unexpected_sensitive_top_level_key_fails_validation():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())
    report["signature"] = "abc123"

    errors = ph10_latency_attribution.validate_report_payload(report)

    assert any("unexpected top-level fields" in error for error in errors)
    assert any("sensitive key" in error for error in errors)


def test_nested_sensitive_key_name_fails_validation():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())
    report["input_summary"]["raw_request_body_hash_source"] = "payload"

    errors = ph10_latency_attribution.validate_report_payload(report)

    assert any("sensitive key" in error for error in errors)


def test_sensitive_policy_can_describe_prohibited_categories():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())
    report["sensitive_data_policy"]["raw_request_body"] = "prohibited"

    errors = ph10_latency_attribution.validate_report_payload(report)

    assert errors == []


def test_route_specific_candidate_uses_scope_only_language():
    evidence = _evidence_with(
        observed={
            "k6_p95_ms": 620,
            "k6_p99_ms": 1400,
            "nginx_request_p95_ms": 480,
            "nginx_upstream_p95_ms": 220,
            "fastapi_handler_p95_ms": 220,
            "postgres_phase_p95_ms": 80,
            "redis_phase_p95_ms": 20,
            "outbound_http_p95_ms": 0,
            "blackbox_probe_p95_ms": 0,
            "error_rate": 0.01,
        }
    )

    report = ph10_latency_attribution.analyze_evidence(evidence)

    assert report["classification"] == "route_specific_latency_candidate"
    assert "candidate scope only" in " ".join(report["evidence"])


def test_markdown_report_contains_boundaries_and_next_checks():
    report = ph10_latency_attribution.analyze_evidence(_evidence_with())
    markdown = ph10_latency_attribution.render_markdown_report(report)

    assert "Classification" in markdown
    assert "Evidence" in markdown
    assert "Recommended Next Checks" in markdown
    assert "Manual Confirmation Required" in markdown
    assert "PH11 latency drill execution" in markdown


def test_list_rules_output_contains_only_safe_summary_fields():
    rules = ph10_latency_attribution.list_rules()
    rendered = repr(rules)

    assert rules
    assert {"classification", "meaning"} == set(rules[0])
    assert "Authorization:" not in rendered
    assert "account_no" not in rendered
    assert "Idempotency-Key" not in rendered
    assert "internal_resource_saturation" not in rendered


def _evidence_with(observed=None, consistency=None):
    evidence = ph10_latency_attribution.sample_evidence()
    if observed is not None:
        evidence["observed"] = observed
    if consistency is not None:
        evidence["consistency"] = consistency
    return evidence
