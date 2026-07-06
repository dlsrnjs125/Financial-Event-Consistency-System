"""Unit tests for runtime write-suspend state management."""

from app.services.write_suspension_service import WriteSuspensionService


def test_missing_artifact_defaults_to_inactive(tmp_path):
    service = WriteSuspensionService(
        state_file=tmp_path / "missing.json",
        retry_after_seconds=30,
    )

    state = service.status()

    assert state.active is False
    assert state.reason == "none"
    assert state.retry_after_seconds == 30


def test_enable_persists_active_artifact(tmp_path):
    state_file = tmp_path / "state.json"
    service = WriteSuspensionService(state_file=state_file, retry_after_seconds=30)

    state = service.enable(
        reason="postgres_unavailable",
        activated_by="test",
        source="postgres_probe",
        retry_after_seconds=60,
        run_id="run-001",
    )

    assert state.active is True
    assert state.reason == "postgres_unavailable"
    assert state.retry_after_seconds == 60
    assert state_file.exists()

    reloaded = WriteSuspensionService(
        state_file=state_file,
        retry_after_seconds=30,
    ).status()
    assert reloaded.active is True
    assert reloaded.run_id == "run-001"


def test_disable_records_resume_metadata(tmp_path):
    service = WriteSuspensionService(
        state_file=tmp_path / "state.json",
        retry_after_seconds=30,
    )
    service.enable(
        reason="postgres_unavailable",
        activated_by="test",
        source="postgres_probe",
        run_id="run-001",
    )

    state = service.disable(reason="operator_resume", resumed_by="operator-a")

    assert state.active is False
    assert state.resumed_by == "operator-a"
    assert state.resume_reason == "operator_resume"


def test_corrupt_artifact_fails_closed(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{broken", encoding="utf-8")
    service = WriteSuspensionService(
        state_file=state_file,
        retry_after_seconds=30,
    )

    state = service.status()

    assert state.active is True
    assert state.reason == "unknown"
    assert state.source == "artifact_corrupt"
