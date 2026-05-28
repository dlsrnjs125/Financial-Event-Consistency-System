"""HMAC-SHA256 signature helpers."""

import hashlib
import hmac


def generate_body_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def build_signature_base_string(
    method: str,
    path: str,
    timestamp: str,
    body_hash: str,
) -> str:
    return "\n".join((method.upper(), path, timestamp, body_hash))


def generate_hmac_signature(secret: str, base_string: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_hmac_signature(
    secret: str,
    base_string: str,
    signature: str,
) -> bool:
    if not secret or not signature:
        return False
    if not _is_hex_digest(signature):
        return False

    expected = generate_hmac_signature(secret, base_string)
    return hmac.compare_digest(expected, signature.lower())


def _is_hex_digest(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True
