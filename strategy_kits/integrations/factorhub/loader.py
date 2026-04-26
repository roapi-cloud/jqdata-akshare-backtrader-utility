"""File loaders for FactorHub exported panels."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Union

import pandas as pd

from ...core import get_logger, log_kv
from ...core.errors import ErrorCode, StrategyKitsError
from .contracts import (
    guess_factorhub_panel_type,
    validate_factorhub_pool_panel,
    validate_factorhub_score_panel,
)

_logger = get_logger("factorhub.loader")


def _read_frame(path: Union[str, Path]) -> pd.DataFrame:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(file_path)
    if suffix == ".json":
        return pd.read_json(file_path)
    raise StrategyKitsError(
        ErrorCode.CONTRACT_INVALID_VALUE,
        f"Unsupported file suffix: {suffix}",
        details={"path": str(file_path)},
    )


def load_factorhub_panel(
    path: Union[str, Path],
    panel_type: Literal["auto", "pool_panel", "score_panel"] = "auto",
) -> pd.DataFrame:
    """Load and validate a FactorHub panel."""
    df = _read_frame(path)
    resolved = guess_factorhub_panel_type(df) if panel_type == "auto" else panel_type

    if resolved == "pool_panel":
        out = validate_factorhub_pool_panel(df)
    elif resolved == "score_panel":
        out = validate_factorhub_score_panel(df)
    else:
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            f"Unknown panel_type: {resolved}",
            details={"panel_type": resolved},
        )

    log_kv(
        _logger,
        20,
        "factorhub_panel_loaded",
        path=str(path),
        panel_type=resolved,
        rows=len(out),
        columns=len(out.columns),
    )
    return out


def load_pool_panel(path: Union[str, Path]) -> pd.DataFrame:
    """Load FactorHub pool panel from local file."""
    return load_factorhub_panel(path, panel_type="pool_panel")


def load_score_panel(path: Union[str, Path]) -> pd.DataFrame:
    """Load FactorHub score panel from local file."""
    return load_factorhub_panel(path, panel_type="score_panel")

