"""Unit tests for PH11 latency drill evidence runner."""

import copy
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import ph10_latency_attribution, ph11_latency_drill_runner  # noqa: E402


def test_drill_catalog_is_deterministic():
    first = ph11_latency_drill_runner.build_report()
    second = ph11_latency_drill_runner.build_report()

    assert first == second


def test_required_lat_drills_are_included():
    report = ph11_latency_drill_runner.build_report()
    drill_ids = {drill["drill_id"] for drill in report["drills"]}

    assert ph11_latency_drill_runner.REQUIRED_DRILLS <= drill_ids
    assert report["drill_count"] == 6


def test_ph10_input_generation_is_deterministic():
    first = ph11_latency_drill_runner.generate_ph10_input("db_lock_contention")
    second = ph11_latency_drill_runner.generate_ph10_input("db_lock_contention")

    assert first == second


def test_scenarios_match_expected_ph10_classification():
    expected = {
        "baseline": "baseline_normal_latency",
        "db_pool_pressure": "internal_postgres_pool_pressure",
        "db_lock_contention": "internal_postgres_lock_contention",
        "redis_degraded": "redis_degraded_latency",
        "redis_unavailable": "redis_unavailable_fallback",
        "external_endpoint_slow": "external_endpoint_slow",
        "app_http_client_path_issue": "app_http_client_path_issue",
        "nginx_edge_latency": "edge_or_client_network_latency",
        "insufficient_evidence": "insufficient_evidence",
    }

    for scenario, classification in expected.items():
        evidence = ph11_latency_drill_runner.generate_ph10_input(scenario)
        report = ph10_latency_attribution.analyze_evidence(evidence)
        assert report["classification"] == classification


def test_expected_actual_classification_mismatch_fails_validation():
    report = ph11_latency_drill_runner.build_report()
    tampered = copy.deepcopy(report)
    tampered["drills"][0]["actual_ph10_classification"] = "internal_postgres_latency"

    errors = ph11_latency_drill_runner.validate_report_payload(tampered)

    assert any("PH10 classification mismatch" in error for error in errors)


def test_safe_auto_run_cannot_include_destructive_command():
    report = ph11_latency_drill_runner.build_report()
    tampered = copy.deepcopy(report)
    drill = _drill(tampered, "LAT-001")
    drill["commands"].append("make ph11-latency-db-lock-manual")

    errors = ph11_latency_drill_runner.validate_report_payload(tampered)

    assert any("destructive/manual command" in error for error in errors)


def test_default_command_must_exist_in_makefile():
    report = ph11_latency_drill_runner.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "LAT-001")["commands"].append("make missing-latency-target")

    errors = ph11_latency_drill_runner.validate_report_payload(tampered)

    assert any("command target does not exist" in error for error in errors)


def test_manual_drill_requires_manual_boundary():
    report = ph11_latency_drill_runner.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "LAT-003")["manual_approval_required_for"] = []

    errors = ph11_latency_drill_runner.validate_report_payload(tampered)

    assert any(
        "manual drill must document manual approval boundary" in error
        for error in errors
    )


def test_consistency_violation_cannot_be_reported_as_clean_latency():
    report = ph11_latency_drill_runner.build_report()
    tampered = copy.deepcopy(report)
    tampered["consistency_policy"]["duplicate_ledger_count"] = 1
    tampered["consistency_policy"]["violation_priority"] = "treat as latency warning"

    errors = ph11_latency_drill_runner.validate_report_payload(tampered)

    assert any("consistency violation" in error for error in errors)


def test_k6_only_root_cause_claim_fails_validation():
    report = ph11_latency_drill_runner.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "LAT-002")["failure_signals"].append("k6 alone proves postgres")

    errors = ph11_latency_drill_runner.validate_report_payload(tampered)

    assert any("forbidden claim" in error or "k6-only" in error for error in errors)


def test_forbidden_metric_label_fails_validation():
    report = ph11_latency_drill_runner.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "LAT-006")["label_candidates"] = ["route_group", "request_id"]

    errors = ph11_latency_drill_runner.validate_report_payload(tampered)

    assert any("forbidden metric label" in error for error in errors)


def test_sensitive_report_content_fails_validation():
    report = ph11_latency_drill_runner.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "LAT-005")["failure_signals"].append(
        "Authorization: Bearer raw-token"
    )

    errors = ph11_latency_drill_runner.validate_report_payload(tampered)

    assert any("sensitive text pattern" in error for error in errors)


def test_markdown_report_contains_contract_boundaries():
    report = ph11_latency_drill_runner.build_report()
    markdown = ph11_latency_drill_runner.render_markdown_report(report)

    for drill_id in ph11_latency_drill_runner.REQUIRED_DRILLS:
        assert drill_id in markdown
    assert "PH10 Analyzer Link" in markdown
    assert "Safe Demo / Manual Boundary" in markdown
    assert "Sensitive Data Policy" in markdown
    assert "Consistency Policy" in markdown


def test_list_output_contains_only_safe_summary_fields():
    report = ph11_latency_drill_runner.build_report()
    rows = ph11_latency_drill_runner.list_catalog_rows(report)
    rendered = repr(rows)

    assert rows
    assert {
        "drill_id",
        "name",
        "safe_to_auto_run",
        "manual_run_required",
        "expected_ph10_classification",
    } == set(rows[0])
    assert "Authorization:" not in rendered
    assert "account_no" not in rendered
    assert "Idempotency-Key" not in rendered


def _drill(report, drill_id):
    return next(drill for drill in report["drills"] if drill["drill_id"] == drill_id)
