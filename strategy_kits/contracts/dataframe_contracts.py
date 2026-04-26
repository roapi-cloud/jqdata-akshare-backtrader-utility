"""DataFrame contracts used across strategy_kits pipelines."""
from __future__ import annotations

from typing import Iterable, Sequence

import pandas as pd

from ..core.errors import ErrorCode, StrategyKitsError


def ensure_columns(
    df: pd.DataFrame,
    required: Sequence[str],
    context: str,
) -> None:
    missing = [c for c in required if c not in df.columns]
    if not missing:
        return
    raise StrategyKitsError(
        ErrorCode.CONTRACT_MISSING_COLUMN,
        f"{context} missing required columns: {missing}",
        details={"required": list(required), "columns": list(df.columns)},
    )


def normalize_code_column(df: pd.DataFrame, col: str = "code") -> pd.DataFrame:
    out = df.copy()
    if col in out.columns:
        out[col] = out[col].astype(str).str.zfill(6)
    return out


def normalize_date_column(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    out = df.copy()
    if col in out.columns:
        out[col] = pd.to_datetime(out[col]).dt.normalize()
    return out


def validate_prediction_frame(df: pd.DataFrame) -> pd.DataFrame:
    ensure_columns(df, required=["date", "code"], context="prediction_frame")
    out = normalize_date_column(df, "date")
    out = normalize_code_column(out, "code")
    if "weight" not in out.columns:
        out["weight"] = 1.0
    return out


def validate_target_weights_frame(df: pd.DataFrame) -> pd.DataFrame:
    ensure_columns(df, required=["code", "target_weight"], context="target_weights")
    out = normalize_code_column(df, "code")
    if out["target_weight"].isna().any():
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "target_weights contains NaN in target_weight",
        )
    return out


def validate_current_weights_frame(df: pd.DataFrame) -> pd.DataFrame:
    ensure_columns(df, required=["code", "weight"], context="current_weights")
    out = normalize_code_column(df, "code")
    if out["weight"].isna().any():
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "current_weights contains NaN in weight",
        )
    return out


def validate_pool_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Freeze FactorHub pool panel contract."""
    ensure_columns(df, required=["date", "code", "score", "rank"], context="pool_panel")
    out = normalize_date_column(df, "date")
    out = normalize_code_column(out, "code")
    return out

