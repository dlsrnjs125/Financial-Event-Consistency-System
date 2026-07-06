"""Schemas for recovery case and quarantine read APIs."""

from datetime import datetime

from pydantic import BaseModel


class RecoveryCaseResponse(BaseModel):
    case_id: str
    source_key: str
    case_type: str
    severity: str
    current_status: str
    classification: str
    confidence_candidate: float | None
    external_event_id: str | None
    client_id: str | None
    detected_by: str
    detected_at: datetime
    source_incident_id: str | None
    proposed_action: str
    approval_required: bool
    approved_by: str | None
    approved_at: datetime | None
    action_attempt_id: str | None
    evidence_path: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuarantineRecordResponse(BaseModel):
    quarantine_id: str
    target_type: str
    target_id: str
    reason: str
    source_incident_id: str | None
    active: bool
    activated_at: datetime
    activated_by: str
    released_at: datetime | None
    released_by: str | None
    release_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
