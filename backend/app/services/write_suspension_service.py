"""Runtime write-suspend state management for financial write traffic."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.observability.metrics import record_write_suspend_state

ACTIVE_REASON_LABELS = {"postgres_unavailable", "manual", "unknown"}


@dataclass(frozen=True)
class WriteSuspendState:
    active: bool
    reason: str
    activated_at: str | None
    activated_by: str | None
    retry_after_seconds: int
    source: str
    run_id: str
    resumed_at: str | None = None
    resumed_by: str | None = None
    resume_reason: str | None = None


class WriteSuspended(Exception):
    def __init__(self, state: WriteSuspendState) -> None:
        self.state = state
        super().__init__(state.reason)


class WriteSuspensionService:
    def __init__(
        self,
        state_file: str | Path,
        retry_after_seconds: int,
    ) -> None:
        self.state_file = Path(state_file)
        self.retry_after_seconds = retry_after_seconds
        self._runtime_state = self._inactive_state()

    def status(self) -> WriteSuspendState:
        artifact_state = self._read_artifact_state()
        if artifact_state is not None:
            self._runtime_state = artifact_state
        self._record_state_metric(self._runtime_state)
        return self._runtime_state

    def enable(
        self,
        *,
        reason: str,
        activated_by: str = "system",
        source: str = "manual",
        retry_after_seconds: int | None = None,
        run_id: str | None = None,
    ) -> WriteSuspendState:
        state = WriteSuspendState(
            active=True,
            reason=reason or "unknown",
            activated_at=_utc_now(),
            activated_by=activated_by,
            retry_after_seconds=retry_after_seconds or self.retry_after_seconds,
            source=source,
            run_id=run_id or f"write-suspend-{uuid4().hex[:12]}",
        )
        self._runtime_state = state
        self._write_artifact(state)
        self._record_state_metric(state)
        return state

    def disable(
        self,
        *,
        reason: str,
        resumed_by: str = "operator",
    ) -> WriteSuspendState:
        previous = self.status()
        state = WriteSuspendState(
            active=False,
            reason=previous.reason,
            activated_at=previous.activated_at,
            activated_by=previous.activated_by,
            retry_after_seconds=previous.retry_after_seconds,
            source=previous.source,
            run_id=previous.run_id,
            resumed_at=_utc_now(),
            resumed_by=resumed_by,
            resume_reason=reason or "operator_resume",
        )
        self._runtime_state = state
        self._write_artifact(state)
        self._record_state_metric(state)
        return state

    def _inactive_state(self) -> WriteSuspendState:
        return WriteSuspendState(
            active=False,
            reason="none",
            activated_at=None,
            activated_by=None,
            retry_after_seconds=self.retry_after_seconds,
            source="runtime",
            run_id="none",
        )

    def _read_artifact_state(self) -> WriteSuspendState | None:
        if not self.state_file.exists():
            return None
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return WriteSuspendState(
                active=True,
                reason="unknown",
                activated_at=_utc_now(),
                activated_by="system",
                retry_after_seconds=self.retry_after_seconds,
                source="artifact_corrupt",
                run_id="artifact-corrupt",
            )
        return WriteSuspendState(
            active=bool(payload.get("active", False)),
            reason=str(payload.get("reason") or "unknown"),
            activated_at=payload.get("activated_at"),
            activated_by=payload.get("activated_by"),
            retry_after_seconds=int(
                payload.get("retry_after_seconds", self.retry_after_seconds)
            ),
            source=str(payload.get("source") or "artifact"),
            run_id=str(payload.get("run_id") or "unknown"),
            resumed_at=payload.get("resumed_at"),
            resumed_by=payload.get("resumed_by"),
            resume_reason=payload.get("resume_reason"),
        )

    def _write_artifact(self, state: WriteSuspendState) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.state_file.with_name(
            f".{self.state_file.name}.{uuid4().hex}.tmp"
        )
        temp_file.write_text(
            json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_file.replace(self.state_file)

    def _record_state_metric(self, state: WriteSuspendState) -> None:
        if state.reason in ACTIVE_REASON_LABELS:
            reason = state.reason
        elif state.active:
            reason = "unknown"
        else:
            reason = "none"
        record_write_suspend_state(reason, state.active)


_service: WriteSuspensionService | None = None


def get_write_suspension_service() -> WriteSuspensionService:
    global _service
    if _service is None:
        _service = WriteSuspensionService(
            state_file=settings.write_suspend_state_file,
            retry_after_seconds=settings.write_suspend_retry_after_seconds,
        )
    return _service


def reset_write_suspension_service_for_testing() -> None:
    global _service
    _service = None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
