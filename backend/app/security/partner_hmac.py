"""Partner HMAC verification with secret-version rotation policy."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.security.hmac import generate_body_hash


class SecretStatus(str, Enum):
    NEXT = "next"
    CURRENT = "current"
    PREVIOUS = "previous"
    REVOKED = "revoked"
    DISABLED = "disabled"


class HmacDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


@dataclass(frozen=True)
class PartnerSecret:
    client_id: str
    key_id: str
    secret: str
    status: SecretStatus
    previous_valid_until: datetime | None = None
    client_enabled: bool = True


@dataclass(frozen=True)
class PartnerHmacResult:
    accepted: bool
    decision: HmacDecision
    decision_reason: str
    client_token: str
    client_status: str
    key_id: str
    key_version: str
    secret_status: str
    request_case: str
    expected_result: str
    actual_result: str
    timestamp_skew_seconds: int | None
    nonce_present: bool
    canonical_request_hash: str
    body_hash: str
    signature_present: bool
    signature_algorithm: str
    rotation_window_status: str
    raw_secret_included: bool = False
    raw_signature_included: bool = False
    raw_body_included: bool = False

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "client_token": self.client_token,
            "client_status": self.client_status,
            "key_id": self.key_id,
            "key_version": self.key_version,
            "secret_status": self.secret_status,
            "request_case": self.request_case,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "decision": self.decision.value,
            "decision_reason": self.decision_reason,
            "timestamp_skew_seconds": self.timestamp_skew_seconds,
            "nonce_present": self.nonce_present,
            "canonical_request_hash": self.canonical_request_hash,
            "body_hash": self.body_hash,
            "signature_present": self.signature_present,
            "signature_algorithm": self.signature_algorithm,
            "rotation_window_status": self.rotation_window_status,
            "raw_secret_included": self.raw_secret_included,
            "raw_signature_included": self.raw_signature_included,
            "raw_body_included": self.raw_body_included,
        }


class PartnerSecretRegistry:
    def __init__(self, secrets: list[PartnerSecret]) -> None:
        self._secrets = {
            (secret.client_id, secret.key_id): secret for secret in secrets
        }

    @classmethod
    def from_config(cls, raw_config: str) -> "PartnerSecretRegistry":
        secrets: list[PartnerSecret] = []
        for item in _split_config(raw_config):
            parts = _split_config_item(item)
            if len(parts) < 4:
                continue
            client_id, key_id, status_value, secret_value = parts[:4]
            if not client_id or not key_id or not secret_value:
                continue
            previous_valid_until = None
            if len(parts) >= 5 and parts[4]:
                previous_valid_until = _parse_timestamp(parts[4])
                if previous_valid_until is None:
                    continue
            client_enabled = True
            if len(parts) >= 6:
                client_enabled = parts[5].lower() not in {"0", "false", "disabled"}
            secrets.append(
                PartnerSecret(
                    client_id=client_id,
                    key_id=key_id,
                    secret=secret_value,
                    status=SecretStatus(status_value.lower()),
                    previous_valid_until=previous_valid_until,
                    client_enabled=client_enabled,
                )
            )
        return cls(secrets)

    def get(self, client_id: str, key_id: str) -> PartnerSecret | None:
        return self._secrets.get((client_id, key_id))

    def has_client(self, client_id: str) -> bool:
        return any(secret.client_id == client_id for secret in self._secrets.values())


def build_partner_canonical_request(
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    raw_body: bytes,
) -> str:
    return "\n".join(
        (
            method.upper(),
            path,
            timestamp,
            nonce,
            generate_body_hash(raw_body),
        )
    )


def generate_partner_hmac_signature(secret: str, canonical_request: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        canonical_request.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_partner_hmac_request(
    *,
    registry: PartnerSecretRegistry,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    raw_body: bytes,
    client_id: str,
    key_id: str,
    signature: str,
    now: datetime | None = None,
    allowed_skew_seconds: int = 300,
    allow_next_for_dry_run: bool = False,
    request_case: str = "partner_hmac_request",
    expected_result: str = "ACCEPT",
) -> PartnerHmacResult:
    current_time = now or datetime.now(timezone.utc)
    canonical_request = build_partner_canonical_request(
        method=method,
        path=path,
        timestamp=timestamp,
        nonce=nonce,
        raw_body=raw_body,
    )
    body_hash = generate_body_hash(raw_body)
    canonical_request_hash = hashlib.sha256(
        canonical_request.encode("utf-8")
    ).hexdigest()
    common = _CommonResult(
        client_id=client_id,
        key_id=key_id,
        request_case=request_case,
        expected_result=expected_result,
        body_hash=body_hash,
        canonical_request_hash=canonical_request_hash,
        signature_present=bool(signature and signature.strip()),
        nonce_present=bool(nonce and nonce.strip()),
    )

    if not common.nonce_present:
        return _reject(common, "missing_nonce")
    if not common.signature_present:
        return _reject(common, "missing_signature")
    if not _is_hex_digest(signature.strip()):
        return _reject(common, "invalid_signature_format")

    parsed_timestamp = _parse_timestamp(timestamp)
    if parsed_timestamp is None:
        return _reject(common, "invalid_timestamp")
    timestamp_skew_seconds = abs(int((parsed_timestamp - current_time).total_seconds()))
    if timestamp_skew_seconds > allowed_skew_seconds:
        return _reject(
            common,
            "timestamp_skew_exceeded",
            timestamp_skew_seconds=timestamp_skew_seconds,
        )

    secret = registry.get(client_id, key_id)
    if secret is None:
        if registry.has_client(client_id):
            return _reject(
                common,
                "unknown_key",
                timestamp_skew_seconds=timestamp_skew_seconds,
            )
        return _reject(
            common,
            "unknown_client",
            timestamp_skew_seconds=timestamp_skew_seconds,
        )
    if not secret.client_enabled or secret.status == SecretStatus.DISABLED:
        return _reject_with_secret(
            common,
            secret,
            "disabled_client",
            timestamp_skew_seconds=timestamp_skew_seconds,
        )
    if secret.status == SecretStatus.REVOKED:
        return _reject_with_secret(
            common,
            secret,
            "revoked_key",
            timestamp_skew_seconds=timestamp_skew_seconds,
        )
    if secret.status == SecretStatus.NEXT and not allow_next_for_dry_run:
        return _reject_with_secret(
            common,
            secret,
            "next_not_allowed",
            timestamp_skew_seconds=timestamp_skew_seconds,
        )
    if secret.status == SecretStatus.PREVIOUS and not _previous_window_is_active(
        secret, current_time
    ):
        return _reject_with_secret(
            common,
            secret,
            "previous_expired",
            timestamp_skew_seconds=timestamp_skew_seconds,
            rotation_window_status="expired",
        )

    expected_signature = generate_partner_hmac_signature(
        secret.secret, canonical_request
    )
    if not hmac.compare_digest(expected_signature, signature.strip().lower()):
        return _reject_with_secret(
            common,
            secret,
            "invalid_signature",
            timestamp_skew_seconds=timestamp_skew_seconds,
        )

    reason = _accept_reason(secret.status)
    return _result(
        common,
        accepted=True,
        decision_reason=reason,
        timestamp_skew_seconds=timestamp_skew_seconds,
        secret=secret,
        rotation_window_status=_rotation_window_status(secret, current_time),
    )


@dataclass(frozen=True)
class _CommonResult:
    client_id: str
    key_id: str
    request_case: str
    expected_result: str
    body_hash: str
    canonical_request_hash: str
    signature_present: bool
    nonce_present: bool


def _result(
    common: _CommonResult,
    *,
    accepted: bool,
    decision_reason: str,
    timestamp_skew_seconds: int | None = None,
    secret: PartnerSecret | None = None,
    rotation_window_status: str = "not_applicable",
) -> PartnerHmacResult:
    return PartnerHmacResult(
        accepted=accepted,
        decision=HmacDecision.ACCEPT if accepted else HmacDecision.REJECT,
        decision_reason=decision_reason,
        client_token=_client_token(common.client_id),
        client_status=_client_status(secret),
        key_id=common.key_id,
        key_version=common.key_id,
        secret_status=secret.status.value if secret else "unknown",
        request_case=common.request_case,
        expected_result=common.expected_result,
        actual_result="ACCEPT" if accepted else "REJECT",
        timestamp_skew_seconds=timestamp_skew_seconds,
        nonce_present=common.nonce_present,
        canonical_request_hash=common.canonical_request_hash,
        body_hash=common.body_hash,
        signature_present=common.signature_present,
        signature_algorithm="HMAC-SHA256",
        rotation_window_status=rotation_window_status,
    )


def _reject(
    common: _CommonResult,
    decision_reason: str,
    *,
    timestamp_skew_seconds: int | None = None,
    rotation_window_status: str = "not_applicable",
) -> PartnerHmacResult:
    return _result(
        common,
        accepted=False,
        decision_reason=decision_reason,
        timestamp_skew_seconds=timestamp_skew_seconds,
        rotation_window_status=rotation_window_status,
    )


def _reject_with_secret(
    common: _CommonResult,
    secret: PartnerSecret,
    decision_reason: str,
    *,
    timestamp_skew_seconds: int | None = None,
    rotation_window_status: str | None = None,
) -> PartnerHmacResult:
    return _result(
        common,
        accepted=False,
        decision_reason=decision_reason,
        timestamp_skew_seconds=timestamp_skew_seconds,
        secret=secret,
        rotation_window_status=rotation_window_status
        or _rotation_window_status(secret, datetime.now(timezone.utc)),
    )


def _accept_reason(status: SecretStatus) -> str:
    if status == SecretStatus.CURRENT:
        return "current_secret"
    if status == SecretStatus.PREVIOUS:
        return "previous_grace_window"
    if status == SecretStatus.NEXT:
        return "next_dry_run"
    return "accepted"


def _previous_window_is_active(secret: PartnerSecret, now: datetime) -> bool:
    if secret.previous_valid_until is None:
        return False
    return now <= secret.previous_valid_until


def _rotation_window_status(secret: PartnerSecret | None, now: datetime) -> str:
    if secret is None:
        return "not_applicable"
    if secret.status == SecretStatus.PREVIOUS:
        return "active" if _previous_window_is_active(secret, now) else "expired"
    if secret.status == SecretStatus.NEXT:
        return "dry_run_only"
    return "not_applicable"


def _client_status(secret: PartnerSecret | None) -> str:
    if secret is None:
        return "unknown"
    if not secret.client_enabled or secret.status == SecretStatus.DISABLED:
        return "disabled"
    return "enabled"


def _client_token(client_id: str) -> str:
    digest = hashlib.sha256(client_id.encode("utf-8")).hexdigest()
    return f"client_{digest[:12]}"


def _timestamp_skew_seconds(timestamp: str, now: datetime) -> int | None:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return None
    return abs(int((parsed - now).total_seconds()))


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _is_hex_digest(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _split_config(raw_config: str) -> list[str]:
    return [
        item.strip()
        for item in raw_config.replace("\n", ",").replace(";", ",").split(",")
        if item.strip()
    ]


def _split_config_item(item: str) -> list[str]:
    if "|" in item:
        return [part.strip() for part in item.split("|")]
    return [part.strip() for part in item.split(":", 3)]
