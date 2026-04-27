"""
Market State Classifier

Classifies market conditions across all dimensions and synthesizes a composite regime.
Reference: Requirements 9-17, design.md Section 3.4
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .enums import (
        TrendState, BreadthState, SentimentState, StyleState,
        SectorState, RiskState, CompositeRegime,
    )


# =============================================================================
# Data Classes for Feature Types (minimal definitions for standalone use)
# =============================================================================

@dataclass
class TrendFeatures:
    """Trend features for a single index."""
    code: str
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    ma120: float = 0.0
    ma_alignment: str = "缠绕"  # "多头排列" / "空头排列" / "缠绕"
    bias_ma5: float = 0.0
    bias_ma20: float = 0.0
    bias_ma60: float = 0.0
    macd_dif: float = 0.0
    macd_dea: float = 0.0
    macd_bar: float = 0.0
    macd_signal: str = "中性"   # "金叉" / "死叉" / "中性"
    atr_20: float = 0.0
    rsrs_score: float = 0.5    # 0-1, normalized
    near_high_20d: bool = False
    break_support: bool = False
    rs_vs_300: float = 0.0     # Relative strength vs CSI300


@dataclass
class BreadthFeatures:
    """Market breadth features."""
    up_down_ratio: float = 1.0
    limit_up_rate: float = 0.01
    seal_rate: float = 0.5
    above_ma20_ratio: float = 0.45
    above_ma60_ratio: float = 0.45
    new_high_ratio: float = 0.01
    amount_deviation_5d: float = 0.0
    amount_deviation_20d: float = 0.0
    breadth_score: float = 50.0  # 0-100 composite score


@dataclass
class SentimentFeatures:
    """Market sentiment features."""
    limit_up_down_ratio: float = 1.0
    continuous_limit_up: int = 0
    seal_rate: float = 0.5
    next_day_premium: float = 0.0
    turnover_zscore: float = 0.0
    sentiment_score: float = 50.0  # 0-100 composite score


@dataclass
class StyleFeatures:
    """Market style features."""
    rs_large_vs_small: float = 1.0   # Large-cap vs small-cap relative strength
    rs_300_vs_1000: float = 1.0     # CSI300 vs CSI1000 relative strength
    rs_500_vs_1000: float = 1.0     # CSI500 vs CSI1000 relative strength
    ret_1d: Dict[str, float] = field(default_factory=dict)
    ret_5d: Dict[str, float] = field(default_factory=dict)
    ret_20d: Dict[str, float] = field(default_factory=dict)
    amount_share: Dict[str, float] = field(default_factory=dict)
    dominant_style: str = "风格冲突"  # "大盘防守" / "小盘进攻" / "成长主导" / "红利防守" / "风格冲突"


@dataclass
class SectorFeatureResult:
    """Sector feature result for a single industry."""
    industry_code: str
    industry_name: str
    strength_score: float = 0.0
    persistence_score: float = 0.0
    crowding_score: float = 0.0
    leadership_score: float = 0.0
    state: str = "震荡整理"  # "主升趋势" / "趋势强化" / "震荡整理" / "超跌反弹" / "弱势退潮"
    ret_1d: float = 0.0
    ret_5d: float = 0.0
    ret_20d: float = 0.0
    excess_ret_1d: float = 0.0
    breadth_20: float = 0.0
    new_high_ratio: float = 0.0
    amount_share: float = 0.0
    amount_share_delta: float = 0.0
    limit_up_count: int = 0
    turnover: float = 0.0


@dataclass
class CapitalFeatures:
    """Capital flow features."""
    total_amount: float = 0.0
    amount_deviation_5d: float = 0.0
    amount_deviation_20d: float = 0.0
    amount_deviation_60d: float = 0.0
    north_net_flow: float = 0.0
    north_5d_avg: float = 0.0
    north_flow_trend: str = "neutral"  # "inflow" / "outflow" / "neutral"
    margin_balance: float = 0.0
    margin_delta: float = 0.0
    main_net_flow: float = 0.0
    etf_net_flow: float = 0.0
    data_freshness: Dict[str, str] = field(default_factory=dict)
    has_delayed_data: bool = False


@dataclass
class RiskFeatures:
    """Risk measurement features."""
    realized_volatility: Dict[str, float] = field(default_factory=dict)
    atr_volatility: Dict[str, float] = field(default_factory=dict)
    vol_ratio_short_long: Dict[str, float] = field(default_factory=dict)  # Short-term / Long-term vol
    index_drawdown: Dict[str, float] = field(default_factory=dict)  # Drawdown from recent peak (%)
    cross_index_correlation: float = 0.0
    sector_correlation_elevation: float = 0.0
    cvix_value: Optional[float] = None
    cvix_percentile: Optional[float] = None
    has_cvix_data: bool = False


# =============================================================================
# MarketStateResult
# =============================================================================

@dataclass
class MarketStateResult:
    """
    Complete market state classification result.

    Attributes:
        date: Trading date
        trend_state: Trend state classification
        breadth_state: Breadth state classification
        sentiment_state: Sentiment state classification
        style_state: Style state classification
        sector_state: Sector rotation state
        risk_state: Risk level classification
        composite_regime: Composite regime classification
        trend_score: Trend dimension score (0-100)
        breadth_score: Breadth dimension score (0-100)
        sentiment_score: Sentiment dimension score (0-100)
        style_score: Style dimension score (0-100)
        sector_score: Sector dimension score (0-100)
        risk_score: Risk dimension score (0-100, higher = more risk)
        regime_score: Composite regime score (0-100)
        key_evidence: 3 key supporting evidence items
        counter_evidence: Counter-evidence items
        confidence: Confidence level (0.1-1.0)
        risk_flags: List of active risk flag names
        missing_data: List of unavailable data items

    Reference: Requirements 17.1-17.7, 15.8
    """
    date: str
    trend_state: "TrendState"
    breadth_state: "BreadthState"
    sentiment_state: "SentimentState"
    style_state: "StyleState"
    sector_state: "SectorState"
    risk_state: "RiskState"
    composite_regime: "CompositeRegime"

    # Dimension scores (0-100)
    trend_score: float = 50.0
    breadth_score: float = 50.0
    sentiment_score: float = 50.0
    style_score: float = 50.0
    sector_score: float = 50.0
    risk_score: float = 50.0

    # Composite regime score
    # Formula: 0.20*trend + 0.15*breadth + 0.15*sentiment + 0.15*style + 0.15*sector - 0.20*risk
    regime_score: float = 50.0

    # Evidence (Req 17.1-17.2)
    key_evidence: List[str] = field(default_factory=list)
    counter_evidence: List[str] = field(default_factory=list)

    # Reliability (Req 17.3-17.7)
    confidence: float = 1.0
    risk_flags: List[str] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================

_CSI300_CODE = "sh000300"


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi] range."""
    return max(lo, min(hi, value))


def _valid(v: float) -> bool:
    """Check if a value is valid (not NaN)."""
    return not math.isnan(v)


# =============================================================================
# MarketStateClassifier
# =============================================================================

class MarketStateClassifier:
    """
    Classifies market state across all dimensions and synthesizes a composite regime.

    The classifier takes features from all dimensions and produces:
    - Individual state classifications for each dimension
    - Composite regime that synthesizes all dimensions
    - Confidence score reflecting data quality
    - Key evidence and counter-evidence for transparency

    Reference: Requirements 9.1-9.6, 10.1-10.6, 11.1-11.6, 12.1-12.5,
               13.1-13.5, 14.1-14.10, 15.1-15.8, 16.1-16.5, 17.1-17.7
    """

    # ------------------------------------------------------------------
    # Public Entry Point
    # ------------------------------------------------------------------

    def classify(
        self,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
        date: str = "",
        missing_data: Optional[List[str]] = None,
    ) -> MarketStateResult:
        """
        Orchestrate all sub-classifiers and return a complete MarketStateResult.

        Parameters
        ----------
        trend_features : Dict[str, TrendFeatures]
            Trend features for each index code (keyed by index code)
        breadth_features : BreadthFeatures
            Market breadth features
        sentiment_features : SentimentFeatures
            Market sentiment features
        style_features : StyleFeatures
            Market style features
        sector_features : List[SectorFeatureResult]
            List of sector feature results
        capital_features : CapitalFeatures
            Capital flow features
        risk_features : RiskFeatures
            Risk measurement features
        date : str
            Trading date in 'YYYY-MM-DD' format
        missing_data : List[str], optional
            List of missing data items

        Returns
        -------
        MarketStateResult
            Complete market state classification result
        """
        if missing_data is None:
            missing_data = []

        # --- Sub-state classification ---
        trend_state = self._classify_trend(trend_features)
        breadth_state = self._classify_breadth(breadth_features)
        sentiment_state = self._classify_sentiment(sentiment_features)
        style_state = self._classify_style(style_features)
        sector_state = self._classify_sector(sector_features)
        risk_state, risk_flags = self._classify_risk(
            risk_features, breadth_features, sector_features, capital_features
        )

        # --- Dimension scores ---
        trend_score = self._score_trend(trend_state)
        breadth_score = self._score_breadth(breadth_state, breadth_features)
        sentiment_score = self._score_sentiment(sentiment_state, sentiment_features)
        style_score = self._score_style(style_state)
        sector_score = self._score_sector(sector_state, sector_features)
        risk_score = self._score_risk(risk_state)

        # --- Composite regime (Req 15.1-15.7) ---
        composite_regime = self._classify_composite(
            trend_state, breadth_state, sentiment_state,
            style_state, sector_state, risk_state,
        )

        # --- Regime score (Req 15.8) ---
        # Formula: 0.20*trend + 0.15*breadth + 0.15*sentiment + 0.15*style + 0.15*sector - 0.20*risk
        regime_score = (
            0.20 * trend_score
            + 0.15 * breadth_score
            + 0.15 * sentiment_score
            + 0.15 * style_score
            + 0.15 * sector_score
            - 0.20 * risk_score
        )
        regime_score = _clamp(regime_score, 0.0, 100.0)

        # --- Evidence extraction (Req 17.1-17.2) ---
        key_evidence, counter_evidence = self._extract_evidence(
            trend_state, breadth_state, sentiment_state,
            style_state, sector_state, risk_state,
            trend_features, breadth_features, sentiment_features,
            style_features, sector_features, capital_features, risk_features,
        )

        # --- Confidence computation (Req 17.3-17.7) ---
        all_states = [trend_state, breadth_state, sentiment_state,
                      style_state, sector_state, risk_state]
        confidence = self._compute_confidence(
            missing_data, all_states,
            trend_features, breadth_features, sentiment_features,
            capital_features, risk_features,
        )

        return MarketStateResult(
            date=date,
            trend_state=trend_state,
            breadth_state=breadth_state,
            sentiment_state=sentiment_state,
            style_state=style_state,
            sector_state=sector_state,
            risk_state=risk_state,
            composite_regime=composite_regime,
            trend_score=trend_score,
            breadth_score=breadth_score,
            sentiment_score=sentiment_score,
            style_score=style_score,
            sector_score=sector_score,
            risk_score=risk_score,
            regime_score=regime_score,
            key_evidence=key_evidence,
            counter_evidence=counter_evidence,
            confidence=confidence,
            risk_flags=risk_flags,
            missing_data=list(missing_data),
        )

    # ------------------------------------------------------------------
    # Trend Classification (Req 9.1-9.5)
    # ------------------------------------------------------------------

    def _classify_trend(self, features: Dict[str, TrendFeatures]) -> "TrendState":
        """
        Classify trend state based on CSI300 (sh000300) features.

        Classification rules (priority order):
        1. BREAKDOWN: price breaks below MA60 AND RSRS<0.3
        2. STRONG_UP: MA5>MA10>MA20>MA60 AND MACD golden cross AND RSRS>0.7
        3. WEAKENING: MA5<MA10<MA20 OR MACD death cross
        4. PULLBACK_IN_UPTREND: bullish alignment but MA5<MA10
        5. RANGING: tangled MAs and MACD near zero (default)

        Reference: Requirements 9.1-9.5
        """
        # Get CSI300 features; fall back to first available index
        tf = features.get(_CSI300_CODE) or features.get("000300")
        if tf is None and features:
            tf = next(iter(features.values()))
        if tf is None:
            return TrendState.RANGING

        ma5, ma10, ma20, ma60 = tf.ma5, tf.ma10, tf.ma20, tf.ma60

        # Req 9.5: Breakdown — highest priority
        if tf.break_support and _valid(ma60) and tf.rsrs_score < 0.3:
            return TrendState.BREAKDOWN

        # Req 9.1: Strong uptrend
        if (
            _valid(ma5) and _valid(ma10) and _valid(ma20) and _valid(ma60)
            and ma5 > ma10 > ma20 > ma60
            and tf.macd_signal == "金叉"
            and tf.rsrs_score > 0.7
        ):
            return TrendState.STRONG_UP

        # Req 9.4: Weakening — MA5<MA10<MA20 OR death cross
        if (
            (_valid(ma5) and _valid(ma10) and _valid(ma20) and ma5 < ma10 < ma20)
            or tf.macd_signal == "死叉"
        ):
            return TrendState.WEAKENING

        # Req 9.2: Pullback in uptrend — bullish alignment but MA5<MA10
        if (
            tf.ma_alignment == "多头排列"
            and _valid(ma5) and _valid(ma10)
            and ma5 < ma10
        ):
            return TrendState.PULLBACK_IN_UPTREND

        # Req 9.3: Ranging — tangled MAs and MACD near zero
        if tf.ma_alignment == "缠绕" and abs(tf.macd_bar) < 0.01:
            return TrendState.RANGING

        # Default: ranging
        return TrendState.RANGING

    # ------------------------------------------------------------------
    # Breadth Classification (Req 10.1-10.5)
    # ------------------------------------------------------------------

    def _classify_breadth(self, f: BreadthFeatures) -> "BreadthState":
        """
        Classify breadth state based on above_ma20_ratio.

        Thresholds:
        - EXTREME_WEAK: < 20%
        - WEAK: 20-35%
        - NEUTRAL: 35-55%
        - STRONG: 55-70%
        - OVERHEATED: >= 70%

        Reference: Requirements 10.1-10.5
        """
        r = f.above_ma20_ratio
        if r < 0.20:
            return BreadthState.EXTREME_WEAK
        if r < 0.35:
            return BreadthState.WEAK
        if r < 0.55:
            return BreadthState.NEUTRAL
        if r < 0.70:
            return BreadthState.STRONG
        return BreadthState.OVERHEATED

    # ------------------------------------------------------------------
    # Sentiment Classification (Req 11.1-11.5)
    # ------------------------------------------------------------------

    def _classify_sentiment(self, f: SentimentFeatures) -> "SentimentState":
        """
        Classify sentiment state based on limit-up/limit-down ratio,
        seal rate, and next-day premium.

        Reference: Requirements 11.1-11.5
        """
        score = f.sentiment_score  # 0-100 composite score

        # Req 11.5: EUPHORIC - extreme conditions
        if score >= 80 or (f.limit_up_down_ratio >= 5.0 and f.seal_rate >= 0.85
                           and f.continuous_limit_up >= 20):
            return SentimentState.EUPHORIC

        # Req 11.4: ACTIVE - positive conditions
        if score >= 60 or (f.limit_up_down_ratio >= 2.5 and f.seal_rate >= 0.70
                           and f.next_day_premium > 0):
            return SentimentState.ACTIVE

        # Req 11.3: NEUTRAL - moderate conditions
        if score >= 40 or (f.limit_up_down_ratio >= 1.0 and f.seal_rate >= 0.50):
            return SentimentState.NEUTRAL

        # Req 11.2: WARMING - recovering conditions
        if score >= 20 or (f.limit_up_down_ratio >= 0.5 and f.seal_rate >= 0.30):
            return SentimentState.WARMING

        # Req 11.1: FROZEN - very weak conditions
        return SentimentState.FROZEN

    # ------------------------------------------------------------------
    # Style Classification (Req 12.1-12.5)
    # ------------------------------------------------------------------

    def _classify_style(self, f: StyleFeatures) -> "StyleState":
        """
        Classify style state based on dominant_style string.

        Reference: Requirements 12.1-12.5
        """
        mapping = {
            "大盘防守": StyleState.LARGE_CAP_DEFENSIVE,
            "小盘进攻": StyleState.SMALL_CAP_OFFENSIVE,
            "成长主导": StyleState.GROWTH_DOMINANT,
            "红利防守": StyleState.DIVIDEND_DEFENSIVE,
            "风格冲突": StyleState.STYLE_CONFLICT,
        }
        return mapping.get(f.dominant_style, StyleState.STYLE_CONFLICT)

    # ------------------------------------------------------------------
    # Sector Classification (Req 13.1-13.5)
    # ------------------------------------------------------------------

    def _classify_sector(self, sectors: List[SectorFeatureResult]) -> "SectorState":
        """
        Classify sector rotation state based on sector strength scores.

        Reference: Requirements 13.1-13.5
        """
        if not sectors:
            return SectorState.NO_THEME

        strong_single = [s for s in sectors if s.strength_score > 2.0 and s.persistence_score > 0.7]
        dual_candidates = [s for s in sectors if s.strength_score > 1.8 and s.persistence_score > 0.6]
        above_threshold = [s for s in sectors if s.strength_score > 1.5]

        # Req 13.2: SINGLE_THEME - exactly one dominant sector
        if len(strong_single) == 1:
            return SectorState.SINGLE_THEME

        # Req 13.3: DUAL_THEME - two strong sectors
        if len(dual_candidates) >= 2:
            return SectorState.DUAL_THEME

        # Req 13.1: NO_THEME - no strong sectors
        if not above_threshold:
            return SectorState.NO_THEME

        # Req 13.5: FADING - declining strength across strong sectors
        fading_count = sum(1 for s in sectors if s.state == "弱势退潮")
        if fading_count > len(sectors) * 0.4:
            return SectorState.FADING

        # Req 13.4: FAST_ROTATION - high turnover without persistence
        moderate = [s for s in sectors if 1.5 < s.strength_score <= 2.0]
        if len(moderate) >= 3:
            return SectorState.FAST_ROTATION

        return SectorState.NO_THEME

    # ------------------------------------------------------------------
    # Risk Classification (Req 14.1-14.10)
    # ------------------------------------------------------------------

    def _classify_risk(
        self,
        risk_features: RiskFeatures,
        breadth_features: BreadthFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
    ) -> tuple["RiskState", List[str]]:
        """
        Classify risk state and return active risk flags.

        Risk flags (Req 14.5-14.10):
        - vol_spike: realized vol > 2x historical mean (vol_ratio > 2.0)
        - breadth_collapse: above_ma20_ratio < 0.15
        - sector_overcrowding: top sector amount_share > 0.25
        - northbound_outflow: north_5d_avg < -10 (亿元)
        - leadership_breakdown: top sectors have low leadership scores
        - index_break_support: CSI300 below MA60 (drawdown < -5%)

        Reference: Requirements 14.1-14.10
        """
        flags: List[str] = []

        # Req 14.5: vol_spike
        csi300_vol_ratio = risk_features.vol_ratio_short_long.get(
            _CSI300_CODE,
            risk_features.vol_ratio_short_long.get("000300", 1.0)
        )
        if csi300_vol_ratio > 2.0:
            flags.append("vol_spike")

        # Req 14.6: breadth_collapse
        if breadth_features.above_ma20_ratio < 0.15:
            flags.append("breadth_collapse")

        # Req 14.7: sector_overcrowding
        if sector_features:
            raw_shares = [getattr(s, "amount_share", None) for s in sector_features]
            raw_shares = [v for v in raw_shares if v is not None]
            if raw_shares and max(raw_shares) > 0.25:
                flags.append("sector_overcrowding")
            else:
                max_crowding = max((s.crowding_score for s in sector_features), default=0.0)
                if max_crowding > 2.0:
                    flags.append("sector_overcrowding")

        # Req 14.8: northbound_outflow
        if capital_features.north_5d_avg < -10.0:
            flags.append("northbound_outflow")

        # Req 14.9: leadership_breakdown
        if sector_features:
            top5 = sorted(sector_features, key=lambda s: s.strength_score, reverse=True)[:5]
            if top5:
                avg_leadership = sum(s.leadership_score for s in top5) / len(top5)
                if avg_leadership < -0.5:
                    flags.append("leadership_breakdown")

        # Req 14.10: index_break_support
        csi300_drawdown = risk_features.index_drawdown.get(
            _CSI300_CODE,
            risk_features.index_drawdown.get("000300", 0.0)
        )
        if csi300_drawdown < -5.0:
            flags.append("index_break_support")

        # --- Classify risk state based on flags, volatility, and drawdown ---
        n_flags = len(flags)
        csi300_vol = risk_features.realized_volatility.get(
            _CSI300_CODE,
            risk_features.realized_volatility.get("000300", 0.0)
        )
        csi300_dd = abs(csi300_drawdown)

        # Req 14.4: EXTREME risk
        if n_flags >= 3 or csi300_vol > 0.40 or csi300_dd > 20.0:
            return RiskState.EXTREME, flags

        # Req 14.3: HIGH risk
        if n_flags >= 1 or csi300_vol > 0.25 or csi300_dd > 10.0:
            return RiskState.HIGH, flags

        # Req 14.2: NEUTRAL risk
        if csi300_vol > 0.15 or csi300_dd > 5.0:
            return RiskState.NEUTRAL, flags

        # Req 14.1: LOW risk
        return RiskState.LOW, flags

    # ------------------------------------------------------------------
    # Composite Regime Classification (Req 15.1-15.7)
    # ------------------------------------------------------------------

    def _classify_composite(
        self,
        trend: "TrendState",
        breadth: "BreadthState",
        sentiment: "SentimentState",
        style: "StyleState",
        sector: "SectorState",
        risk: "RiskState",
    ) -> "CompositeRegime":
        """
        Synthesize all dimension states into a composite regime.

        Priority-ordered mapping rules:
        1. risk==EXTREME → HIGH_VOL_WARNING
        2. breadth==EXTREME_WEAK and sentiment==FROZEN → PANIC_BOTTOMING
        3. trend in (BREAKDOWN, WEAKENING) and breadth in (EXTREME_WEAK, WEAK) → BROAD_WEAKNESS_HOLD
        4. trend==STRONG_UP and style==GROWTH_DOMINANT → TREND_RISK_ON_GROWTH
        5. trend==STRONG_UP and style==SMALL_CAP_OFFENSIVE → TREND_RISK_ON_SMALLCAP
        6. style==DIVIDEND_DEFENSIVE → DEFENSIVE_DIVIDEND
        7. default → BALANCED_ROTATION

        Reference: Requirements 15.1-15.7
        """
        # Rule 1: Extreme risk
        if risk == RiskState.EXTREME:
            return CompositeRegime.HIGH_VOL_WARNING

        # Rule 2: Panic bottoming
        if breadth == BreadthState.EXTREME_WEAK and sentiment == SentimentState.FROZEN:
            return CompositeRegime.PANIC_BOTTOMING

        # Rule 3: Broad weakness hold
        if (trend in (TrendState.BREAKDOWN, TrendState.WEAKENING)
                and breadth in (BreadthState.EXTREME_WEAK, BreadthState.WEAK)):
            return CompositeRegime.BROAD_WEAKNESS_HOLD

        # Rule 4: Trend risk on growth
        if trend == TrendState.STRONG_UP and style == StyleState.GROWTH_DOMINANT:
            return CompositeRegime.TREND_RISK_ON_GROWTH

        # Rule 5: Trend risk on smallcap
        if trend == TrendState.STRONG_UP and style == StyleState.SMALL_CAP_OFFENSIVE:
            return CompositeRegime.TREND_RISK_ON_SMALLCAP

        # Rule 6: Defensive dividend
        if style == StyleState.DIVIDEND_DEFENSIVE:
            return CompositeRegime.DEFENSIVE_DIVIDEND

        # Rule 7: Default balanced rotation
        return CompositeRegime.BALANCED_ROTATION

    # ------------------------------------------------------------------
    # Dimension Scores
    # ------------------------------------------------------------------

    def _score_trend(self, state: "TrendState") -> float:
        """Map trend state to 0-100 score. Reference: Req 9.6"""
        mapping = {
            TrendState.STRONG_UP: 90.0,
            TrendState.PULLBACK_IN_UPTREND: 65.0,
            TrendState.RANGING: 50.0,
            TrendState.WEAKENING: 30.0,
            TrendState.BREAKDOWN: 10.0,
        }
        return mapping.get(state, 50.0)

    def _score_breadth(self, state: "BreadthState", f: BreadthFeatures) -> float:
        """Map breadth state to 0-100 score. Reference: Req 10.6"""
        return _clamp(f.breadth_score, 0.0, 100.0)

    def _score_sentiment(self, state: "SentimentState", f: SentimentFeatures) -> float:
        """Map sentiment state to 0-100 score. Reference: Req 11.6"""
        return _clamp(f.sentiment_score, 0.0, 100.0)

    def _score_style(self, state: "StyleState") -> float:
        """Map style state to 0-100 score."""
        mapping = {
            StyleState.GROWTH_DOMINANT: 80.0,
            StyleState.SMALL_CAP_OFFENSIVE: 75.0,
            StyleState.STYLE_CONFLICT: 50.0,
            StyleState.LARGE_CAP_DEFENSIVE: 40.0,
            StyleState.DIVIDEND_DEFENSIVE: 35.0,
        }
        return mapping.get(state, 50.0)

    def _score_sector(self, state: "SectorState", sectors: List[SectorFeatureResult]) -> float:
        """Map sector state to 0-100 score."""
        mapping = {
            SectorState.SINGLE_THEME: 80.0,
            SectorState.DUAL_THEME: 70.0,
            SectorState.FAST_ROTATION: 55.0,
            SectorState.NO_THEME: 40.0,
            SectorState.FADING: 25.0,
        }
        return mapping.get(state, 50.0)

    def _score_risk(self, state: "RiskState") -> float:
        """
        Map risk state to 0-100 score.
        Higher score means higher risk.
        """
        mapping = {
            RiskState.LOW: 10.0,
            RiskState.NEUTRAL: 35.0,
            RiskState.HIGH: 65.0,
            RiskState.EXTREME: 90.0,
        }
        return mapping.get(state, 35.0)

    # ------------------------------------------------------------------
    # Evidence Extraction (Req 17.1-17.2)
    # ------------------------------------------------------------------

    def _extract_evidence(
        self,
        trend: "TrendState",
        breadth: "BreadthState",
        sentiment: "SentimentState",
        style: "StyleState",
        sector: "SectorState",
        risk: "RiskState",
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
    ) -> tuple[List[str], List[str]]:
        """
        Extract 3 key supporting evidence items and counter-evidence.

        Req 17.1: 3 most important supporting evidence items
        Req 17.2: counter-evidence that contradicts the main conclusion
        """
        key_evidence: List[str] = []
        counter_evidence: List[str] = []

        # --- Supporting Evidence ---
        # Trend evidence
        tf = trend_features.get(_CSI300_CODE) or trend_features.get("000300")
        if tf is not None:
            if trend == TrendState.STRONG_UP:
                key_evidence.append(
                    f"沪深300 MA多头排列(MA5={tf.ma5:.1f}>MA10={tf.ma10:.1f}>MA20={tf.ma20:.1f}>MA60={tf.ma60:.1f})"
                    f"，MACD{tf.macd_signal}，RSRS={tf.rsrs_score:.2f}"
                )
            elif trend == TrendState.BREAKDOWN:
                key_evidence.append(
                    f"沪深300 跌破MA60({tf.ma60:.1f})，RSRS={tf.rsrs_score:.2f}<0.3，趋势破位"
                )
            elif trend == TrendState.WEAKENING:
                key_evidence.append(
                    f"沪深300 均线走弱(MA5={tf.ma5:.1f}<MA10={tf.ma10:.1f})，MACD{tf.macd_signal}"
                )
            elif trend == TrendState.PULLBACK_IN_UPTREND:
                key_evidence.append(
                    f"沪深300 多头排列中回调(MA5={tf.ma5:.1f}<MA10={tf.ma10:.1f})，趋势未破坏"
                )
            else:
                key_evidence.append(
                    f"沪深300 均线缠绕，MACD柱={tf.macd_bar:.4f}，市场震荡"
                )

        # Breadth evidence
        r = breadth_features.above_ma20_ratio
        key_evidence.append(
            f"市场广度：站上MA20个股比例={r:.1%}({breadth.value})，"
            f"涨跌比={breadth_features.up_down_ratio:.2f}"
        )

        # Sentiment evidence
        key_evidence.append(
            f"市场情绪：涨停/跌停比={sentiment_features.limit_up_down_ratio:.2f}，"
            f"封板率={sentiment_features.seal_rate:.1%}，"
            f"情绪分={sentiment_features.sentiment_score:.0f}({sentiment.value})"
        )

        # Keep only top 3 evidence items
        key_evidence = key_evidence[:3]

        # --- Counter-Evidence ---
        # Bullish trend but weak breadth
        if trend in (TrendState.STRONG_UP, TrendState.PULLBACK_IN_UPTREND):
            if breadth in (BreadthState.EXTREME_WEAK, BreadthState.WEAK):
                counter_evidence.append(
                    f"指数走强但广度偏弱(MA20比例={r:.1%})，上涨缺乏普遍参与"
                )

        # Bearish trend but positive sentiment
        if trend in (TrendState.WEAKENING, TrendState.BREAKDOWN):
            if sentiment in (SentimentState.ACTIVE, SentimentState.EUPHORIC):
                counter_evidence.append(
                    f"趋势走弱但情绪仍{sentiment.value}，可能存在结构性分化"
                )

        # High risk but strong trend
        if risk in (RiskState.HIGH, RiskState.EXTREME):
            if trend == TrendState.STRONG_UP:
                counter_evidence.append(
                    f"趋势强劲但风险状态为{risk.value}，需警惕波动放大"
                )

        # Capital outflow despite positive trend
        if capital_features.north_5d_avg < -5.0 and trend in (
            TrendState.STRONG_UP, TrendState.PULLBACK_IN_UPTREND
        ):
            counter_evidence.append(
                f"北向资金5日均值={capital_features.north_5d_avg:.1f}亿，外资持续流出"
            )

        # Overheated breadth as risk
        if breadth == BreadthState.OVERHEATED:
            counter_evidence.append(
                f"广度过热(MA20比例={r:.1%})，短期回调风险上升"
            )

        return key_evidence, counter_evidence

    # ------------------------------------------------------------------
    # Confidence Computation (Req 17.3-17.7)
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        missing_data: List[str],
        states: List,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
    ) -> float:
        """
        Compute confidence score based on data quality and signal consistency.

        Req 17.3: -0.15 per missing core indicator
        Req 17.4: +0.10 when signals consistent across trend/breadth/sentiment
        Req 17.5: -0.10 for extreme anomalous values
        Req 17.6: -0.05 per estimated/proxy data item
        Req 17.7: clamp to [0.1, 1.0]
        """
        confidence = 1.0

        # Req 17.3: Penalize missing core indicators
        core_indicators = [
            "index_data", "breadth_data", "sentiment_data",
            "capital_data", "risk_data",
        ]
        for indicator in core_indicators:
            if any(indicator in m for m in missing_data):
                confidence -= 0.15

        # Also penalize each item in missing_data list directly
        confidence -= 0.15 * len(missing_data)

        # Req 17.4: Boost for consistent signals
        trend_states = [s for s in states if isinstance(s, TrendState)]
        breadth_states = [s for s in states if isinstance(s, BreadthState)]
        sentiment_states = [s for s in states if isinstance(s, SentimentState)]

        if trend_states and breadth_states and sentiment_states:
            t = trend_states[0]
            b = breadth_states[0]
            s = sentiment_states[0]

            bullish_trend = t in (TrendState.STRONG_UP, TrendState.PULLBACK_IN_UPTREND)
            bullish_breadth = b in (BreadthState.STRONG, BreadthState.OVERHEATED)
            bullish_sentiment = s in (SentimentState.ACTIVE, SentimentState.EUPHORIC)

            bearish_trend = t in (TrendState.WEAKENING, TrendState.BREAKDOWN)
            bearish_breadth = b in (BreadthState.EXTREME_WEAK, BreadthState.WEAK)
            bearish_sentiment = s in (SentimentState.FROZEN, SentimentState.WARMING)

            if (bullish_trend and bullish_breadth and bullish_sentiment) or \
               (bearish_trend and bearish_breadth and bearish_sentiment):
                confidence += 0.10

        # Req 17.5: Penalize extreme anomalous values
        for code, vol_ratio in risk_features.vol_ratio_short_long.items():
            if vol_ratio > 3.0:
                confidence -= 0.10
                break

        if sentiment_features.limit_up_down_ratio > 10.0 or \
           sentiment_features.limit_up_down_ratio == 0.0:
            confidence -= 0.10

        # Req 17.6: Penalize estimated/proxy data
        proxy_count = 0
        if capital_features.has_delayed_data:
            proxy_count += 1
        if not risk_features.has_cvix_data:
            proxy_count += 1
        for freshness in capital_features.data_freshness.values():
            if "T+1" in freshness or "proxy" in freshness.lower() or "估计" in freshness:
                proxy_count += 1

        confidence -= 0.05 * proxy_count

        # Req 17.7: Clamp to [0.1, 1.0]
        return _clamp(confidence, 0.1, 1.0)
