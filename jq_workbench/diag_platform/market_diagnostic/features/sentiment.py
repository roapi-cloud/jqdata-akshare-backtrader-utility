"""
Sentiment Feature Calculation

Computes market sentiment indicators from MarketBreadthData.
Includes limit-up/down ratio, continuous limit-up count, seal rate,
next-day premium, turnover Z-score, and composite sentiment score.

Requirements: 4.1-4.6
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from ..data.models import MarketBreadthData


@dataclass
class SentimentFeatures:
    """
    Market sentiment features.

    Attributes:
        limit_up_down_ratio: limit_up_count / limit_down_count
        continuous_limit_up: stocks with 2+ consecutive limit-ups
        seal_rate: limit_up / (limit_up + explode)
        next_day_premium: next-day premium for yesterday's limit-up stocks
        turnover_zscore: turnover rate Z-score vs historical
        sentiment_score: composite 0-100
    """
    limit_up_down_ratio: float
    continuous_limit_up: int
    seal_rate: float
    next_day_premium: float
    turnover_zscore: float
    sentiment_score: float


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to [0, 1] range, clamping to bounds."""
    if max_val == min_val:
        return 0.5
    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def _compute_zscore(value: float, historical: List[float]) -> float:
    """Compute Z-score of value vs historical distribution."""
    if not historical or len(historical) < 2:
        return 0.0

    hist_array = np.array(historical)
    mean = float(np.mean(hist_array))
    std = float(np.std(hist_array, ddof=1))

    if std == 0:
        return 0.0

    return (value - mean) / std


def compute_sentiment_features(
    data: MarketBreadthData,
    historical_amounts: Optional[List[float]] = None,
    next_day_premium: float = 0.0,
) -> SentimentFeatures:
    """
    Compute sentiment features from market breadth data.

    Parameters
    ----------
    data : MarketBreadthData
        Market-wide breadth metrics
    historical_amounts : List[float], optional
        Historical turnover amounts for Z-score calculation
    next_day_premium : float
        Next-day premium for yesterday's limit-up stocks (default 0.0)

    Returns
    -------
    SentimentFeatures
        Computed sentiment indicators

    Requirements: 4.1-4.6
    """
    # Requirement 4.1: Limit-up to limit-down ratio
    limit_up_down_ratio = _safe_divide(
        data.limit_up_count,
        data.limit_down_count,
        default=0.0
    )

    # Requirement 4.2: Continuous limit-up count
    continuous_limit_up = data.continuous_limit_up

    # Requirement 4.3: Seal rate
    seal_rate = data.seal_rate

    # Requirement 4.4: Next-day premium
    next_day_premium_val = next_day_premium

    # Requirement 4.5: Turnover rate Z-score
    if historical_amounts is not None and len(historical_amounts) > 0:
        turnover_zscore = _compute_zscore(data.total_amount, historical_amounts)
    else:
        turnover_zscore = 0.0

    # Requirement 4.6: Composite sentiment score (0-100)
    score_components = [
        25 * _normalize(limit_up_down_ratio, 0, 5),
        25 * _normalize(seal_rate, 0, 1),
        25 * _normalize(continuous_limit_up / 500, 0, 1),
        25 * _normalize(turnover_zscore + 3, 0, 6),
    ]
    sentiment_score = sum(score_components)
    sentiment_score = max(0.0, min(100.0, sentiment_score))

    return SentimentFeatures(
        limit_up_down_ratio=limit_up_down_ratio,
        continuous_limit_up=continuous_limit_up,
        seal_rate=seal_rate,
        next_day_premium=next_day_premium_val,
        turnover_zscore=turnover_zscore,
        sentiment_score=sentiment_score,
    )
