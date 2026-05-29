"""Masking helpers for sensitive identifiers."""


def mask_account_no(account_no: str | None) -> str:
    if not account_no:
        return ""
    if len(account_no) <= 4:
        return "*" * len(account_no)
    return f"{'*' * (len(account_no) - 4)}{account_no[-4:]}"


def mask_idempotency_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def mask_signature(signature: str | None) -> str:
    if not signature:
        return ""
    if len(signature) <= 8:
        return "<redacted>"
    return f"{signature[:8]}***"


def redact_secret(value: str | None) -> str:
    return "<redacted>"
