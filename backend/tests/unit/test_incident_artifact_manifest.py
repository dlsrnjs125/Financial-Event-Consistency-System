from __future__ import annotations

import json
from importlib import util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts/ph2_incident_artifact.py"
SPEC = util.spec_from_file_location("ph2_incident_artifact_manifest", SCRIPT_PATH)
ph2_incident_artifact = util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(ph2_incident_artifact)


def test_create_writes_manifest_report_and_validates(tmp_path: Path) -> None:
    state_file = tmp_path / "write-suspend-state.json"
    state_file.write_text(
        json.dumps(
            {
                "active": True,
                "reason": "postgres_unavailable",
                "retry_after_seconds": 30,
                "source": "postgres_probe",
                "run_id": "ph1-db-down-test",
                "account_no": "synthetic-account-number-1234",
            }
        ),
        encoding="utf-8",
    )

    incident_dir = ph2_incident_artifact.create_artifact(
        scenario="POSTGRES_DOWN",
        run_id="ph1-db-down-test",
        source="unit_test",
        output_root=tmp_path / "incidents",
        write_suspend_state=state_file,
        ph1_report_dir=None,
    )

    manifest = json.loads((incident_dir / "manifest.json").read_text(encoding="utf-8"))
    report = (incident_dir / "sanitized-report.md").read_text(encoding="utf-8")
    copied_state = json.loads(
        (incident_dir / "write-suspend-state.json").read_text(encoding="utf-8")
    )

    assert manifest["incident_id"] == incident_dir.name
    assert manifest["scenario"] == "POSTGRES_DOWN"
    assert manifest["severity_candidate"] == "SEV1"
    assert manifest["sensitive_data_included"] is False
    assert "- Sensitive Data Included: false" in report
    assert "account_no" not in copied_state
    assert ph2_incident_artifact.validate_artifact(incident_dir) == []


def test_validate_fails_when_sensitive_key_is_present(tmp_path: Path) -> None:
    incident_dir = ph2_incident_artifact.create_artifact(
        scenario="POSTGRES_DOWN",
        run_id="ph1-db-down-test",
        source="unit_test",
        output_root=tmp_path / "incidents",
        write_suspend_state=tmp_path / "missing-state.json",
        ph1_report_dir=None,
    )
    command_results = incident_dir / "command-results.json"
    payload = json.loads(command_results.read_text(encoding="utf-8"))
    payload["Authorization"] = "synthetic-authorization-token"
    command_results.write_text(json.dumps(payload), encoding="utf-8")

    errors = ph2_incident_artifact.validate_artifact(incident_dir)

    assert any("sensitive key found" in error for error in errors)
    assert any("sensitive value pattern found" in error for error in errors)


def test_create_handles_corrupt_write_suspend_state(tmp_path: Path) -> None:
    state_file = tmp_path / "write-suspend-state.json"
    state_file.write_text("{broken", encoding="utf-8")

    incident_dir = ph2_incident_artifact.create_artifact(
        scenario="POSTGRES_DOWN",
        run_id="ph1-db-down-test",
        source="unit_test",
        output_root=tmp_path / "incidents",
        write_suspend_state=state_file,
        ph1_report_dir=None,
    )

    state = json.loads(
        (incident_dir / "write-suspend-state.json").read_text(encoding="utf-8")
    )

    assert state["result"] == "invalid_state_json"
    assert state["reason"] == "state_file_invalid"
    assert state["sensitive_data_included"] is False
    assert ph2_incident_artifact.validate_artifact(incident_dir) == []


def test_latest_incident_dir_selects_most_recent(tmp_path: Path) -> None:
    output_root = tmp_path / "incidents"
    first = output_root / "inc-20260706-153000-postgres-down"
    second = output_root / "inc-20260706-153100-postgres-down"
    first.mkdir(parents=True)
    second.mkdir()

    assert ph2_incident_artifact.latest_incident_dir(output_root) == second


def test_create_adds_suffix_when_incident_id_collides(tmp_path: Path) -> None:
    output_root = tmp_path / "incidents"
    existing = output_root / "inc-20260706-153000-postgres-down"
    existing.mkdir(parents=True)

    incident_dir = ph2_incident_artifact._create_unique_incident_dir(
        output_root, "inc-20260706-153000-postgres-down"
    )

    assert incident_dir.name == "inc-20260706-153000-postgres-down-001"
