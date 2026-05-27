"""Transaction processing result value object."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TransactionProcessingResult:
    status_code: int
    body: dict[str, Any]
    processed: bool
    duplicated: bool
