from __future__ import annotations

import json
from importlib import util
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts/ph3_incident_analyzer.py"
SPEC = util.spec_from_file_location("ph3_incident_analyzer", SCRIPT_PATH)
ph3_incident_analyzer = util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(ph3_incident_analyzer)


def test_postgres_down_write_suspended_classification(tmp_path: Path) -> None:
    incident_dir = _artifact(
        tmp_path,
        manifest={"scenario": "POSTGRES_DOWN"},
        write_state={
            "active": True,
            "reason": "postgres_unavailable",
            "source": "postgres_probe",
        },
    )

    result = ph3_incident_analyzer.analyze_incident(incident_dir)

    assert result["classification"] == "POSTGRES_DOWN_WRITE_SUSPENDED"
    assert result["severity_candidate"] == "SEV1"
    assert result["sensitive_data_included"] is False


def test_write_suspended_unknown_dependency_classification(tmp_path: Path) -> None:
    incident_dir = _artifact(
        tmp_path,
        manifest={"scenario": "unknown"},
        write_state={"active": True, "reason": "manual", "source": "runtime"},
    )

    result = ph3_incident_analyzer.analyze_incident(incident_dir)

    assert result["classification"] == "WRITE_SUSPENDED_UNKNOWN_DEPENDENCY"


def test_sanitization_risk_has_priority(tmp_path: Path) -> None:
    incident_dir = _artifact(
        tmp_path,
        manifest={"scenario": "POSTGRES_DOWN", "sensitive_data_included": True},
        consistency={"duplicate_ledger_count": 1},
    )

    result = ph3_incident_analyzer.analyze_incident(incident_dir)

    assert result["classification"] == "ARTIFACT_SANITIZATION_RISK"
    assert result["severity_candidate"] == "SEV2"


def test_consistency_issue_candidate_classification(tmp_path: Path) -> None:
    incident_dir = _artifact(
        tmp_path,
        manifest={"scenario": "MANUAL_CHECK"},
        consistency={"duplicate_ledger_count": 1},
    )

    result = ph3_incident_analyzer.analyze_incident(incident_dir)

    assert result["classification"] == "CONSISTENCY_ISSUE_CANDIDATE"
    assert result["severity_candidate"] == "SEV1"


def test_insufficient_evidence_without_manifest(tmp_path: Path) -> None:
    incident_dir = tmp_path / "inc-20260706-153000-postgres-down"
    incident_dir.mkdir()

    result = ph3_incident_analyzer.analyze_incident(incident_dir)

    assert result["classification"] == "INSUFFICIENT_EVIDENCE"
    assert result["confidence_candidate"] == 0.4


def test_analyze_writes_and_validates_outputs(tmp_path: Path) -> None:
    incident_dir = _artifact(
        tmp_path,
        manifest={"scenario": "POSTGRES_DOWN"},
        write_state={"active": True, "reason": "postgres_unavailable"},
    )

    ph3_incident_analyzer.analyze_incident(incident_dir)

    assert (incident_dir / "analyzer-result.json").exists()
    assert (incident_dir / "incident-analysis.md").exists()
    assert ph3_incident_analyzer.validate_analysis(incident_dir) == []


def test_validate_fails_when_analyzer_output_marks_sensitive_data(
    tmp_path: Path,
) -> None:
    incident_dir = _artifact(tmp_path, manifest={"scenario": "POSTGRES_DOWN"})
    ph3_incident_analyzer.analyze_incident(incident_dir)
    result_path = incident_dir / "analyzer-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["sensitive_data_included"] = True
    result_path.write_text(json.dumps(result), encoding="utf-8")

    errors = ph3_incident_analyzer.validate_analysis(incident_dir)

    assert any("sensitive_data_included must be false" in error for error in errors)


def test_latest_incident_dir_uses_latest_ph2_artifact(tmp_path: Path) -> None:
    first = tmp_path / "inc-20260706-153000-postgres-down"
    second = tmp_path / "inc-20260706-153100-postgres-down"
    first.mkdir()
    second.mkdir()

    assert ph3_incident_analyzer.latest_incident_dir(tmp_path) == second


def _artifact(
    tmp_path: Path,
    *,
    manifest: dict[str, Any] | None = None,
    write_state: dict[str, Any] | None = None,
    consistency: dict[str, Any] | None = None,
) -> Path:
    incident_dir = tmp_path / "inc-20260706-153000-postgres-down"
    incident_dir.mkdir()
    manifest_payload = {
        "incident_id": incident_dir.name,
        "scenario": "POSTGRES_DOWN",
        "severity_candidate": "SEV1",
        "confidence_candidate": 0.8,
        "created_at": "2026-07-06T15:30:00+09:00",
        "created_by": "test",
        "source": "unit_test",
        "run_id": "ph3-test",
        "sanitized": True,
        "sensitive_data_included": False,
        "manual_review_required": True,
        "evidence_files": [],
        "manual_required": [],
    }
    if manifest:
        manifest_payload.update(manifest)
    _write_json(incident_dir / "manifest.json", manifest_payload)
    _write_json(
        incident_dir / "write-suspend-state.json",
        write_state or {"active": False, "reason": "not_collected"},
    )
    _write_json(
        incident_dir / "health-ready-summary.json",
        {"ready_status": "not_collected", "health_status": "not_collected"},
    )
    _write_json(
        incident_dir / "consistency-summary.json",
        consistency or {"result": "not_collected"},
    )
    _write_json(
        incident_dir / "command-results.json",
        {"command_name": "test", "exit_code": 0, "result": "created"},
    )
    (incident_dir / "docker-compose-status.txt").write_text(
        "docker_compose_status: not_collected\n",
        encoding="utf-8",
    )
    (incident_dir / "sanitized-report.md").write_text(
        "# Incident Report Draft\n\n- Sensitive Data Included: false\n",
        encoding="utf-8",
    )
    (incident_dir / "raw").mkdir()
    (incident_dir / "raw" / "README.md").write_text("empty\n", encoding="utf-8")
    return incident_dir


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
