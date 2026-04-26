"""Shared error model for strategy_kits productization."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Stable error codes for cross-module diagnostics."""

    CONTRACT_MISSING_COLUMN = "SK_CONTRACT_001"
    CONTRACT_INVALID_VALUE = "SK_CONTRACT_002"
    CALENDAR_NOT_INITIALIZED = "SK_CAL_001"
    CALENDAR_OUT_OF_RANGE = "SK_CAL_002"
    FILTER_DATA_UNAVAILABLE = "SK_FILTER_001"
    PREPROCESS_NOT_FITTED = "SK_PRE_001"
    ARTIFACT_WRITE_FAILED = "SK_ARTIFACT_001"
    ARTIFACT_CONTRACT_INVALID = "SK_ARTIFACT_002"


class StrategyKitsError(RuntimeError):
    """Base typed exception with machine-readable code."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value if isinstance(self.code, ErrorCode) else str(self.code),
            "message": self.message,
            "details": self.details,
        }
