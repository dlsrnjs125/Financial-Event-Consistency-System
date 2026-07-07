"""Unit tests for PH8 HA / queue decision matrix evidence."""

import copy
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import ph8_ha_queue_decision_matrix  # noqa: E402


def test_decision_matrix_is_deterministic():
    first = ph8_ha_queue_decision_matrix.build_report()
    second = ph8_ha_queue_decision_matrix.build_report()

    assert first == second


def test_required_options_are_included():
    report = ph8_ha_queue_decision_matrix.build_report()
    option_ids = {option["option_id"] for option in report["options"]}

    assert ph8_ha_queue_decision_matrix.REQUIRED_OPTIONS <= option_ids


def test_score_out_of_range_fails_validation():
    report = ph8_ha_queue_decision_matrix.build_report()
    tampered = copy.deepcopy(report)
    tampered["options"][0]["availability_score"] = 6

    errors = ph8_ha_queue_decision_matrix.validate_report_payload(tampered)

    assert any("availability_score must be 1..5" in error for error in errors)


def test_queue_first_must_split_accepted_and_completed():
    report = ph8_ha_queue_decision_matrix.build_report()
    tampered = copy.deepcopy(report)
    queue = _option(tampered, "durable_queue_first")
    queue["api_response_semantics"] = "API returns success after enqueue."
    queue["required_new_controls"] = ["consumer idempotency"]

    errors = ph8_ha_queue_decision_matrix.validate_report_payload(tampered)

    assert "durable_queue_first must split ACCEPTED and COMPLETED semantics" in errors


def test_ha_options_must_require_consistency_gate_and_resume_approval():
    report = ph8_ha_queue_decision_matrix.build_report()
    tampered = copy.deepcopy(report)
    ha = _option(tampered, "postgres_primary_standby_ha")
    ha["api_response_semantics"] = "COMPLETED remains primary commit based."
    ha["required_new_controls"] = ["primary identity verification"]

    errors = ph8_ha_queue_decision_matrix.validate_report_payload(tampered)

    assert any(
        "consistency gate and write resume approval" in error for error in errors
    )


def test_direct_option_links_to_fail_closed_and_write_suspend():
    report = ph8_ha_queue_decision_matrix.build_report()
    direct = _option(report, "direct_postgres_fail_closed")
    rendered = repr(direct).lower()

    assert "503" in rendered
    assert "write suspend" in rendered
    assert direct["decision"] == "recommended_now"


def test_sensitive_report_content_fails_validation():
    report = ph8_ha_queue_decision_matrix.build_report()
    tampered = copy.deepcopy(report)
    tampered["options"][0]["risk_summary"] = "raw_request_body should never appear"

    errors = ph8_ha_queue_decision_matrix.validate_report_payload(tampered)

    assert any("sensitive text pattern" in error for error in errors)


def test_missing_top_level_field_fails_validation():
    report = ph8_ha_queue_decision_matrix.build_report()
    tampered = copy.deepcopy(report)
    tampered.pop("current_decision")

    errors = ph8_ha_queue_decision_matrix.validate_report_payload(tampered)

    assert any("missing top-level fields" in error for error in errors)


def test_decision_matrix_total_must_match_option_scores():
    report = ph8_ha_queue_decision_matrix.build_report()
    tampered = copy.deepcopy(report)
    tampered["decision_matrix"][0]["total_context_score"] = 999

    errors = ph8_ha_queue_decision_matrix.validate_report_payload(tampered)

    assert any("total_context_score mismatch" in error for error in errors)


def test_markdown_report_contains_decision_and_follow_up_candidates():
    report = ph8_ha_queue_decision_matrix.build_report()
    markdown = ph8_ha_queue_decision_matrix.render_markdown_report(report)

    assert "Current decision" in markdown
    assert "Follow-up candidates" in markdown
    assert "Direct PostgreSQL transaction" in markdown


def test_markdown_report_contains_contract_boundary():
    report = ph8_ha_queue_decision_matrix.build_report()
    markdown = ph8_ha_queue_decision_matrix.render_markdown_report(report)
    table_header = (
        "| Option | Availability | Explainability | Complexity | "
        "Cost | Local Fit | Decision |"
    )

    assert table_header in markdown
    assert "ACCEPTED" in markdown
    assert "COMPLETED" in markdown
    assert "not production benchmarks" in markdown
    assert "recommended_now" in markdown
    assert "Follow-up candidates" in markdown


def test_forbidden_queue_completion_claim_fails_validation():
    report = ph8_ha_queue_decision_matrix.build_report()
    tampered = copy.deepcopy(report)
    tampered["recommendation"]["recommended_later"].append(
        "queue 도입 시 바로 원장 반영 완료를 보장한다"
    )

    errors = ph8_ha_queue_decision_matrix.validate_report_payload(tampered)

    assert any("forbidden claim" in error for error in errors)


def _option(report, option_id):
    return next(
        option for option in report["options"] if option["option_id"] == option_id
    )
