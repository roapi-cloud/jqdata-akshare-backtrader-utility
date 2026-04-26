"""FactorHub panel contracts for strategy_kits."""
from __future__ import annotations

import pandas as pd

from ...contracts import ensure_columns, normalize_code_column, normalize_date_column, validate_pool_panel
from ...core.errors import ErrorCode, StrategyKitsError


def _to_numeric_strict(df: pd.DataFrame, col: str, context: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_numeric(out[col], errors="coerce")
    if out[col].isna().any():
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            f"{context} contains invalid numeric values in column '{col}'",
            details={"column": col},
        )
    return out


def guess_factorhub_panel_type(df: pd.DataFrame) -> str:
    """Guess panel type from columns."""
    if {"date", "code", "score", "rank"}.issubset(df.columns):
        return "pool_panel"
    if {"date", "code", "score"}.issubset(df.columns) or {"date", "code", "ts_score"}.issubset(df.columns):
        return "score_panel"
    raise StrategyKitsError(
        ErrorCode.CONTRACT_MISSING_COLUMN,
        "Unable to infer panel type from columns",
        details={"columns": list(df.columns)},
    )


def validate_factorhub_pool_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize FactorHub pool panel contract."""
    out = validate_pool_panel(df)
    out = _to_numeric_strict(out, "score", "pool_panel")
    out = _to_numeric_strict(out, "rank", "pool_panel")
    return out.sort_values(["date", "rank", "score"], ascending=[True, True, False]).reset_index(drop=True)


def validate_factorhub_score_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize FactorHub score panel contract."""
    out = df.copy()
    if "score" not in out.columns and "ts_score" in out.columns:
        out = out.rename(columns={"ts_score": "score"})

    ensure_columns(out, required=["date", "code", "score"], context="score_panel")
    out = normalize_date_column(out, "date")
    out = normalize_code_column(out, "code")
    out = _to_numeric_strict(out, "score", "score_panel")

    if "rank" in out.columns:
        out = _to_numeric_strict(out, "rank", "score_panel")

    return out.sort_values(["date", "score"], ascending=[True, False]).reset_index(drop=True)

