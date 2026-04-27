"""
Sector Feature Calculation

Computes sector (industry) strength, persistence, and state classification.
Includes multi-period returns, excess returns, breadth metrics, turnover metrics,
leadership scores, and composite strength/persistence scores.

Requirements: 6.1-6.8, 16.1-16.5
"""

from __future__ import annotations

import concurrent.futures
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..data.models import SectorDailyData


# Sector strength score weights
SECTOR_STRENGTH_WEIGHTS = {
    "ret_5d_excess": 0.25,
    "ret_20d_excess": 0.20,
    "breadth_20": 0.20,
    "new_high_ratio": 0.10,
    "amount_share_delta": 0.10,
    "leadership_score": 0.10,
    "crowding_score": -0.05,
}

# Sector thresholds
SECTOR_THRESHOLDS = {
    "strength_strong": 2.0,
    "strength_moderate": 1.5,
    "strength_weak": -0.5,
    "persistence_high": 0.7,
    "persistence_moderate": 0.4,
}


@dataclass
class SectorFeatureResult:
    """
    Sector feature calculation result.

    Attributes:
        industry_code: Industry code (e.g., 'BK0447')
        industry_name: Industry name (e.g., '电子')
        strength_score: Industry strength score (Z-score weighted composite)
        persistence_score: Industry persistence score (0-1)
        crowding_score: Industry crowding score (Z-score of amount_share)
        leadership_score: Leadership score based on limit-up count
        state: Sector state classification
    """
    industry_code: str
    industry_name: str
    strength_score: float
    persistence_score: float
    crowding_score: float
    leadership_score: float
    state: str


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _compute_z_score(value: float, values: List[float]) -> float:
    """
    Compute Z-score for a value relative to a list of values.

    Parameters
    ----------
    value : float
        The value to compute Z-score for
    values : List[float]
        List of all values for computing mean and stdev

    Returns
    -------
    float
        Z-score (standardized value)
    """
    if len(values) < 2:
        return 0.0

    mean = statistics.mean(values)
    try:
        stdev = statistics.stdev(values)
    except statistics.StatisticsError:
        return 0.0

    if stdev == 0:
        return 0.0

    return (value - mean) / stdev


def compute_sector_strength_score(
    sector: SectorDailyData,
    all_sectors: List[SectorDailyData],
) -> float:
    """
    Compute sector strength score using weighted Z-score formula.

    Formula:
        strength_score =
            0.25 * z(ret_5d_excess) +
            0.20 * z(ret_20d_excess) +
            0.20 * z(breadth_20) +
            0.10 * z(new_high_ratio) +
            0.10 * z(amount_share_delta) +
            0.10 * z(leadership_score) -
            0.05 * z(crowding_score)

    Parameters
    ----------
    sector : SectorDailyData
        The sector to compute strength score for
    all_sectors : List[SectorDailyData]
        All sectors for cross-sectional Z-score calculation

    Returns
    -------
    float
        Sector strength score (typically in range [-3, 3])

    Requirements: 6.7
    """
    if not all_sectors:
        return 0.0

    # Extract values for Z-score calculation
    ret_5d_values = [s.ret_5d for s in all_sectors]
    ret_20d_values = [s.ret_20d for s in all_sectors]
    breadth_20_values = [s.breadth_20 for s in all_sectors]
    new_high_ratio_values = [s.new_high_ratio for s in all_sectors]
    amount_share_delta_values = [s.amount_share_delta for s in all_sectors]
    limit_up_values = [float(s.limit_up_count) for s in all_sectors]
    amount_share_values = [s.amount_share for s in all_sectors]

    # Compute Z-scores
    z_ret_5d = _compute_z_score(sector.ret_5d, ret_5d_values)
    z_ret_20d = _compute_z_score(sector.ret_20d, ret_20d_values)
    z_breadth_20 = _compute_z_score(sector.breadth_20, breadth_20_values)
    z_new_high_ratio = _compute_z_score(sector.new_high_ratio, new_high_ratio_values)
    z_amount_share_delta = _compute_z_score(sector.amount_share_delta, amount_share_delta_values)
    z_leadership = _compute_z_score(float(sector.limit_up_count), limit_up_values)
    z_crowding = _compute_z_score(sector.amount_share, amount_share_values)

    # Apply weighted formula
    strength_score = (
        SECTOR_STRENGTH_WEIGHTS["ret_5d_excess"] * z_ret_5d +
        SECTOR_STRENGTH_WEIGHTS["ret_20d_excess"] * z_ret_20d +
        SECTOR_STRENGTH_WEIGHTS["breadth_20"] * z_breadth_20 +
        SECTOR_STRENGTH_WEIGHTS["new_high_ratio"] * z_new_high_ratio +
        SECTOR_STRENGTH_WEIGHTS["amount_share_delta"] * z_amount_share_delta +
        SECTOR_STRENGTH_WEIGHTS["leadership_score"] * z_leadership +
        SECTOR_STRENGTH_WEIGHTS["crowding_score"] * z_crowding
    )

    return strength_score


def compute_sector_persistence_score(
    sector: SectorDailyData,
    historical_rankings: Optional[List[int]] = None,
    amount_share_trend: float = 0.0,
) -> float:
    """
    Compute sector persistence score based on ranking history.

    Parameters
    ----------
    sector : SectorDailyData
        The sector to compute persistence for
    historical_rankings : List[int], optional
        Historical rankings over past N days (1=strongest, 31=weakest)
    amount_share_trend : float, optional
        Trend in amount_share over time (positive = increasing)

    Returns
    -------
    float
        Persistence score in range [0, 1]

    Requirements: 6.8
    """
    # Simplified persistence calculation when historical rankings unavailable
    if historical_rankings is None or len(historical_rankings) == 0:
        # Use multi-period return consistency as proxy
        ret_1d_positive = 1.0 if sector.ret_1d > 0 else 0.0
        ret_5d_positive = 1.0 if sector.ret_5d > 0 else 0.0
        ret_20d_positive = 1.0 if sector.ret_20d > 0 else 0.0

        base_score = (
            0.2 * ret_1d_positive +
            0.3 * ret_5d_positive +
            0.5 * ret_20d_positive
        )

        if amount_share_trend > 0:
            base_score = min(1.0, base_score + 0.1)

        return base_score

    # Full calculation with historical rankings
    avg_ranking = statistics.mean(historical_rankings)
    persistence_score = max(0.0, min(1.0, (31 - avg_ranking) / 30))

    top_5_count = sum(1 for r in historical_rankings if r <= 5)
    if top_5_count >= len(historical_rankings) * 0.6:
        persistence_score = min(1.0, persistence_score + 0.1)

    return persistence_score


def classify_sector_state(
    strength_score: float,
    persistence_score: float,
    ret_20d: float,
) -> str:
    """
    Classify sector state based on strength and persistence.

    States:
    - 主升趋势 (main uptrend): strength > 2.0 AND persistence > 0.7
    - 趋势强化 (trend strengthening): strength > 1.5 AND 0.4 < persistence < 0.7
    - 震荡整理 (consolidation): -0.5 < strength < 1.5
    - 超跌反弹 (oversold bounce): 0.5 < strength < 1.5 AND ret_20d < -10%
    - 弱势退潮 (weak fading): strength < -0.5

    Parameters
    ----------
    strength_score : float
        Sector strength score
    persistence_score : float
        Sector persistence score (0-1)
    ret_20d : float
        20-day return (as percentage, e.g., -10 for -10%)

    Returns
    -------
    str
        Sector state classification

    Requirements: 16.1-16.5
    """
    # Requirement 16.1: Main uptrend
    if (strength_score > SECTOR_THRESHOLDS["strength_strong"] and
        persistence_score > SECTOR_THRESHOLDS["persistence_high"]):
        return "主升趋势"

    # Requirement 16.4: Oversold bounce (check before trend strengthening)
    if (0.5 < strength_score < SECTOR_THRESHOLDS["strength_moderate"] and
        ret_20d < -10):
        return "超跌反弹"

    # Requirement 16.2: Trend strengthening
    if (strength_score > SECTOR_THRESHOLDS["strength_moderate"] and
        SECTOR_THRESHOLDS["persistence_moderate"] < persistence_score < SECTOR_THRESHOLDS["persistence_high"]):
        return "趋势强化"

    # Requirement 16.5: Weak fading
    if strength_score < SECTOR_THRESHOLDS["strength_weak"]:
        return "弱势退潮"

    # Requirement 16.3: Consolidation (default)
    return "震荡整理"


def compute_sector_features(
    sector: SectorDailyData,
    all_sectors: List[SectorDailyData],
    historical_rankings: Optional[List[int]] = None,
    amount_share_trend: float = 0.0,
) -> SectorFeatureResult:
    """
    Compute comprehensive sector features.

    Parameters
    ----------
    sector : SectorDailyData
        The sector to analyze
    all_sectors : List[SectorDailyData]
        All sectors for cross-sectional analysis
    historical_rankings : List[int], optional
        Historical rankings for persistence calculation
    amount_share_trend : float, optional
        Trend in amount_share over time

    Returns
    -------
    SectorFeatureResult
        Complete sector feature analysis

    Requirements: 6.1-6.8, 16.1-16.5
    """
    # Compute strength score
    strength_score = compute_sector_strength_score(sector, all_sectors)

    # Compute persistence score
    persistence_score = compute_sector_persistence_score(
        sector,
        historical_rankings,
        amount_share_trend,
    )

    # Compute crowding score (Z-score of amount_share)
    amount_share_values = [s.amount_share for s in all_sectors]
    crowding_score = _compute_z_score(sector.amount_share, amount_share_values)

    # Compute leadership score (Z-score of limit_up_count)
    limit_up_values = [float(s.limit_up_count) for s in all_sectors]
    leadership_score = _compute_z_score(float(sector.limit_up_count), limit_up_values)

    # Classify sector state
    state = classify_sector_state(strength_score, persistence_score, sector.ret_20d)

    return SectorFeatureResult(
        industry_code=sector.industry_code,
        industry_name=sector.industry_name,
        strength_score=strength_score,
        persistence_score=persistence_score,
        crowding_score=crowding_score,
        leadership_score=leadership_score,
        state=state,
    )


def compute_all_sector_features(
    sectors: List[SectorDailyData],
    all_sectors: Optional[List[SectorDailyData]] = None,
    max_workers: int = 4,
) -> List[SectorFeatureResult]:
    """
    Compute sector features for all sectors in parallel.

    Parameters
    ----------
    sectors : List[SectorDailyData]
        The list of sectors to compute features for
    all_sectors : List[SectorDailyData], optional
        The full cross-sectional list used for Z-score calculations
    max_workers : int, optional
        Maximum number of worker threads (default: 4)

    Returns
    -------
    List[SectorFeatureResult]
        Feature results in the same order as ``sectors``

    Requirements: 23.3, 23.4
    """
    if not sectors:
        return []

    cross_section: List[SectorDailyData] = all_sectors if all_sectors is not None else sectors

    def _compute_one(sector: SectorDailyData) -> SectorFeatureResult:
        return compute_sector_features(sector, cross_section)

    # Use ThreadPoolExecutor for I/O-friendly parallel execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_compute_one, s) for s in sectors]
        results = [f.result() for f in futures]

    return results
