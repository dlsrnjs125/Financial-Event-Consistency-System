"""Unit tests for PH9 production hardening drill catalog evidence."""

import copy
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import ph9_production_hardening_drill  # noqa: E402


def test_drill_catalog_is_deterministic():
    first = ph9_production_hardening_drill.build_report()
    second = ph9_production_hardening_drill.build_report()

    assert first == second


def test_required_ph1_to_ph8_drills_are_included():
    report = ph9_production_hardening_drill.build_report()
    phases = {drill["phase"] for drill in report["drills"]}

    assert ph9_production_hardening_drill.REQUIRED_PHASES <= phases


def test_latency_candidate_cannot_be_completed_drill():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    tampered["drills"].append(
        {
            **tampered["drills"][0],
            "phase": "PH10",
            "drill_id": "ph10-latency-attribution",
        }
    )
    tampered["drill_count"] = len(tampered["drills"])

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("follow-up candidate" in error for error in errors)


def test_safe_auto_run_cannot_include_manual_approval_action():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    drill = _drill(tampered, "ph6-ai-safe-context-sanitizer")
    drill["safe_to_auto_run"] = True
    drill["manual_approval_required_for"] = ["write resume"]

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("safe_to_auto_run cannot include" in error for error in errors)


def test_destructive_command_fails_validation():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "ph1-postgres-write-suspend-db-down")["commands"].append(
        "make ph1-db-down-drill"
    )

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("destructive/manual command" in error for error in errors)


def test_candidate_command_must_be_allowlisted():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "ph8-postgres-ha-queue-decision-evidence")[
        "candidate_commands"
    ].append("make latency-analyze")

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("candidate command is not allowlisted" in error for error in errors)


def test_linked_docs_must_not_be_empty():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "ph2-incident-artifact-sanitized-report")["linked_docs"] = []

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("linked_docs must not be empty" in error for error in errors)


def test_success_criteria_must_not_be_empty():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "ph3-incident-analyzer-mvp")["success_criteria"] = []

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("success_criteria must not be empty" in error for error in errors)


def test_sensitive_data_policy_must_not_be_empty():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "ph4-recovery-case-quarantine-manual-approval")[
        "sensitive_data_policy"
    ] = ""

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("sensitive_data_policy must not be empty" in error for error in errors)


def test_sensitive_report_content_fails_validation():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "ph5-stale-processing-reconciliation")["failure_signals"].append(
        "raw request body leaked with account_no"
    )

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("sensitive text pattern" in error for error in errors)


def test_queue_completion_claim_fails_validation():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "ph8-postgres-ha-queue-decision-evidence")[
        "failure_signals"
    ].append("queue 도입 시 바로 원장 반영 완료를 보장한다")

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("forbidden claim" in error for error in errors)


def test_ha_replaces_consistency_gate_claim_fails_validation():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    _drill(tampered, "ph8-postgres-ha-queue-decision-evidence")[
        "failure_signals"
    ].append("HA removes the need for consistency gate")

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("forbidden claim" in error for error in errors)


def test_ai_as_recovery_executor_claim_fails_validation():
    report = ph9_production_hardening_drill.build_report()
    tampered = copy.deepcopy(report)
    drill = _drill(tampered, "ph6-ai-safe-context-sanitizer")
    drill["goal"] = "AI automatically executes recovery"

    errors = ph9_production_hardening_drill.validate_report_payload(tampered)

    assert any("forbidden claim" in error for error in errors)


def test_markdown_report_contains_boundaries_and_followups():
    report = ph9_production_hardening_drill.build_report()
    markdown = ph9_production_hardening_drill.render_markdown_report(report)

    for phase in ph9_production_hardening_drill.REQUIRED_PHASES:
        assert phase in markdown
    assert "Automation Boundary" in markdown
    assert "Manual Approval Boundary" in markdown
    assert "Safety Notes" in markdown
    assert "Follow-up Candidates" in markdown
    assert "destructive drills" in markdown
    assert "ACCEPTED" in markdown
    assert "COMPLETED" in markdown
    assert "AI-safe context" in markdown
    assert "candidate_commands are not default auto-run commands" in markdown


def test_list_output_contains_only_safe_summary_fields():
    report = ph9_production_hardening_drill.build_report()
    rows = ph9_production_hardening_drill.list_catalog_rows(report)
    rendered = repr(rows)
    expected_fields = {
        "phase",
        "drill_id",
        "name",
        "safe_to_auto_run",
        "manual_run_required",
    }

    assert rows
    assert expected_fields == set(rows[0])
    assert "Authorization:" not in rendered
    assert "raw request body" not in rendered
    assert "account_no" not in rendered


def _drill(report, drill_id):
    return next(drill for drill in report["drills"] if drill["drill_id"] == drill_id)
