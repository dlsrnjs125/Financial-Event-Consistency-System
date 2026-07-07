"""Unit tests for PH7 HMAC rotation drill validation."""

import copy
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import ph7_hmac_rotation_drill  # noqa: E402


def test_validate_report_payload_rejects_unexpected_case_keys():
    payload = ph7_hmac_rotation_drill.build_report()
    tampered = copy.deepcopy(payload)
    tampered["cases"][0]["signature"] = "0" * 64

    errors = ph7_hmac_rotation_drill.validate_report_payload(tampered)

    assert any("unexpected keys" in error for error in errors)
    assert any("signature" in error for error in errors)


def test_validate_report_payload_accepts_generated_sample_shape():
    payload = ph7_hmac_rotation_drill.build_report()

    assert ph7_hmac_rotation_drill.validate_report_payload(payload) == []
