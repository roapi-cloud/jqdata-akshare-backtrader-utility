"""Adapters from FactorHub panels to strategy_kits inputs."""
from __future__ import annotations

from typing import Literal

import pandas as pd

from ...core import get_logger, log_kv
from ...contracts import validate_prediction_frame
from .contracts import validate_factorhub_pool_panel, validate_factorhub_score_panel

_logger = get_logger("factorhub.adapter")


WeightMode = Literal["equal", "score"]


def _normalize_weight_from_score(df: pd.DataFrame, score_col: str = "score") -> pd.Series:
    scores = pd.to_numeric(df[score_col], errors="coerce").fillna(0.0)
    min_score = float(scores.min()) if len(scores) else 0.0
    shifted = scores - min_score if min_score < 0 else scores
    total = float(shifted.sum())
    if total <= 0:
        return pd.Series([1.0 / len(df)] * len(df), index=df.index) if len(df) > 0 else pd.Series(dtype=float)
    return shifted / total


def _to_prediction_frame(
    panel: pd.DataFrame,
    top_n: int,
    weight_mode: WeightMode,
    use_rank: bool,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for dt, group in panel.groupby("date"):
        g = group.copy()
        if use_rank and "rank" in g.columns:
            g = g.sort_values("rank", ascending=True)
        else:
            g = g.sort_values("score", ascending=False)

        g = g.head(top_n)
        if g.empty:
            continue

        if weight_mode == "equal":
            g["weight"] = 1.0 / len(g)
        else:
            g["weight"] = _normalize_weight_from_score(g, score_col="score")
        g["date"] = dt
        rows.append(g[["date", "code", "weight", "score"] + (["rank"] if "rank" in g.columns else [])])

    if not rows:
        return pd.DataFrame(columns=["date", "code", "weight"])

    pred = pd.concat(rows, ignore_index=True)
    pred = validate_prediction_frame(pred)
    return pred.sort_values(["date", "weight"], ascending=[True, False]).reset_index(drop=True)


def pool_panel_to_prediction_frame(
    pool_panel: pd.DataFrame,
    top_n: int = 20,
    weight_mode: WeightMode = "score",
) -> pd.DataFrame:
    """Convert FactorHub pool panel to prediction frame for strategy templates."""
    panel = validate_factorhub_pool_panel(pool_panel)
    pred = _to_prediction_frame(panel, top_n=max(1, int(top_n)), weight_mode=weight_mode, use_rank=True)
    log_kv(_logger, 20, "factorhub_pool_adapted", rows=len(panel), output_rows=len(pred), top_n=top_n)
    return pred


def score_panel_to_prediction_frame(
    score_panel: pd.DataFrame,
    top_n: int = 20,
    weight_mode: WeightMode = "score",
) -> pd.DataFrame:
    """Convert FactorHub score panel to prediction frame for strategy templates."""
    panel = validate_factorhub_score_panel(score_panel)
    pred = _to_prediction_frame(panel, top_n=max(1, int(top_n)), weight_mode=weight_mode, use_rank=False)
    log_kv(_logger, 20, "factorhub_score_adapted", rows=len(panel), output_rows=len(pred), top_n=top_n)
    return pred


def merge_cross_sectional_with_temporal_score(
    cs_df: pd.DataFrame,
    ts_score_panel: pd.DataFrame,
    cs_score_col: str = "cs_score",
    ts_score_col: str = "score",
    lambda_ts: float = 0.3,
    out_score_col: str = "final_score",
) -> pd.DataFrame:
    """Merge cross-sectional score with temporal score enhancement."""
    if cs_score_col not in cs_df.columns:
        raise ValueError(f"cs_df missing column: {cs_score_col}")

    ts = validate_factorhub_score_panel(ts_score_panel).rename(columns={"score": ts_score_col})
    base = cs_df.copy()
    base["date"] = pd.to_datetime(base["date"]).dt.normalize()
    base["code"] = base["code"].astype(str).str.zfill(6)
    merged = base.merge(ts[["date", "code", ts_score_col]], on=["date", "code"], how="left")
    merged[ts_score_col] = merged[ts_score_col].fillna(0.0)
    merged[out_score_col] = merged[cs_score_col] + float(lambda_ts) * merged[ts_score_col]

    log_kv(
        _logger,
        20,
        "factorhub_cs_ts_merged",
        rows=len(merged),
        lambda_ts=lambda_ts,
        output_score_col=out_score_col,
    )
    return merged

