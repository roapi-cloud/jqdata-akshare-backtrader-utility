"""
Market State Classifier for the Market Diagnostic System.

Classifies market state across 6 dimensions and computes composite regime,
confidence scores, evidence extraction, and risk flag monitoring.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .enums import (
    BreadthState,
    CompositeRegime,
    RiskState,
    SectorState,
    SentimentState,
    StyleState,
    TrendState,
    REGIME_STRATEGY_MAPPING,
    BREADTH_THRESHOLDS,
)


@dataclass
class MarketStateResult:
    """
    Result of market state classification.

    Includes all dimension states, composite regime, scores (0-100),
    evidence lists, confidence (0-1), risk flags, and missing data.
    """
    date: str
    # Dimension states
    trend_state: TrendState
    breadth_state: BreadthState
    sentiment_state: SentimentState
    style_state: StyleState
    sector_state: SectorState
    risk_state: RiskState
    composite_regime: CompositeRegime
    # Scores (0-100)
    trend_score: float
    breadth_score: float
    sentiment_score: float
    style_score: float
    sector_score: float
    risk_score: float
    regime_score: float  # 0.20*trend + 0.15*breadth + 0.15*sentiment + 0.15*style + 0.15*sector - 0.20*risk
    # Evidence
    key_evidence: List[str]  # 3 key supporting evidence items
    counter_evidence: List[str]  # Counter-evidence items
    # Confidence and risk
    confidence: float  # 0-1
    risk_flags: List[str]  # Active risk flag names
    missing_data: List[str]  # Unavailable data items
    # Strategy
    strategy_groups: List[str]  # Recommended strategy groups for this regime


class MarketStateClassifier:
    """
    Main classifier for market state across all 6 dimensions.

    Classification logic:
    - Trend: Based on MA alignment, MACD signal, RSRS score (primary: 沪深300)
    - Breadth: Based on above_ma20_ratio (strictly monotonic thresholds)
    - Sentiment: Based on limit_up_rate, seal_rate, continuous_limit_up
    - Style: Based on relative strength of style pairs
    - Sector: Based on strength_score distribution across industries
    - Risk: Based on realized_vol, drawdown, risk_flags count
    - Composite: Priority-based rule mapping to 7 regimes
    """

    def __init__(self):
        self._prev_breadth_ratio: Optional[float] = None  # For breadth_collapse detection

    def classify(
        self,
        date: str,
        trend_features: Dict[str, "TrendFeatures"],
        breadth_features: "BreadthFeatures",
        sentiment_features: "SentimentFeatures",
        style_features: "StyleFeatures",
        sector_features: List["SectorFeatureResult"],
        capital_features: "CapitalFeatures",
        risk_features: "RiskFeatures",
        prev_breadth_ratio: Optional[float] = None,
    ) -> MarketStateResult:
        """
        Full market state classification across all dimensions.

        Args:
            date: Trading date string (YYYY-MM-DD)
            trend_features: Dict of code -> TrendFeatures for indices
            breadth_features: Market breadth features
            sentiment_features: Market sentiment features
            style_features: Style features
            sector_features: List of sector feature results
            capital_features: Capital flow features
            risk_features: Risk features
            prev_breadth_ratio: Previous day's above_ma20_ratio for collapse detection

        Returns:
            MarketStateResult with all states, scores, evidence, confidence
        """
        self._prev_breadth_ratio = prev_breadth_ratio

        # Step 1: Classify each dimension
        trend_state, trend_score = self._classify_trend(trend_features)
        breadth_state, breadth_score = self._classify_breadth(breadth_features)
        sentiment_state, sentiment_score = self._classify_sentiment(sentiment_features)
        style_state, style_score = self._classify_style(style_features)
        sector_state, sector_score = self._classify_sector(sector_features)
        risk_state, risk_score, risk_flags = self._classify_risk(risk_features, breadth_features)

        # Step 2: Compute composite regime
        composite_regime = self._classify_composite(
            trend_state, breadth_state, sentiment_state, style_state, sector_state, risk_state
        )

        # Step 3: Compute regime score
        regime_score = self._compute_regime_score(
            trend_score, breadth_score, sentiment_score, style_score, sector_score, risk_score
        )

        # Step 4: Extract evidence
        key_evidence, counter_evidence = self._extract_evidence(
            date, trend_features, breadth_features, sentiment_features, style_features,
            sector_features, capital_features, risk_features,
            trend_state, breadth_state, sentiment_state, style_state, sector_state,
            risk_state, composite_regime
        )

        # Step 5: Compute confidence
        confidence = self._compute_confidence(
            missing_data=[],  # Will be populated by caller
            trend_state=trend_state,
            breadth_state=breadth_state,
            sentiment_state=sentiment_state,
        )

        # Step 6: Get strategy groups
        strategy_groups = REGIME_STRATEGY_MAPPING.get(composite_regime.value, [])

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
            missing_data=[],
            strategy_groups=strategy_groups,
        )

    # -------------------------------------------------------------------------
    # Trend Classification
    # -------------------------------------------------------------------------

    def _classify_trend(self, features: Dict[str, "TrendFeatures"]) -> Tuple[TrendState, float]:
        """
        Classify trend state based on 沪深300 (sh000300) as primary.

        Thresholds:
        - 强趋势上行: MA5>MA10>MA20>MA60 AND MACD金叉 AND RSRS>0.7
        - 趋势上行中的回调: 多头排列但MA5<MA10
        - 震荡: 均线缠绕(无明确多头/空头), MACD在零轴附近
        - 趋势转弱: MA5<MA10<MA20 OR MACD死叉
        - 破位下行: 跌破MA60 AND RSRS<0.3
        """
        primary_code = "sh000300"
        f = features.get(primary_code)

        if f is None:
            # Fallback: use first available index
            if not features:
                return TrendState.RANGING, 50.0
            f = next(iter(features.values()))

        ma_alignment = f.ma_alignment
        macd_signal = f.macd_signal
        rsrs = f.rsrs_score
        near_high = f.near_high_20d
        break_support = f.break_support

        # Compute individual signal strength
        ma_bullish = ma_alignment == "多头排列"
        ma_bearish = ma_alignment == "空头排列"
        macd_bullish = macd_signal == "金叉"
        macd_bearish = macd_signal == "死叉"

        # Count bullish/bearish signals
        bullish_count = sum([ma_bullish, macd_bullish, near_high])
        bearish_count = sum([ma_bearish, macd_bearish, break_support])

        # Strong uptrend: full bullish alignment + MACD golden cross + RSRS strong
        if ma_bullish and macd_bullish and rsrs > 0.7:
            score = 80.0 + min(rsrs * 20, 20.0)
            return TrendState.STRONG_UP, min(score, 100.0)

        # Pullback in uptrend: bullish alignment but MA5 < MA10
        if ma_bullish and not macd_bullish:
            score = 60.0 + (1 - rsrs) * 15
            return TrendState.PULLBACK_IN_UPTREND, max(30.0, min(score, 75.0))

        # Breakdown: broke below MA60 AND RSRS weak
        if break_support and rsrs < 0.3:
            score = 20.0 + rsrs * 20
            return TrendState.BREAKDOWN, max(10.0, min(score, 40.0))

        # Weakening: bearish alignment OR MACD death cross
        if ma_bearish or macd_bearish:
            score = 35.0 - rsrs * 15
            return TrendState.WEAKENING, max(15.0, min(score, 50.0))

        # Ranging: tangled MAs, MACD near zero
        score = 50.0
        return TrendState.RANGING, score

    # -------------------------------------------------------------------------
    # Breadth Classification
    # -------------------------------------------------------------------------

    def _classify_breadth(self, f: "BreadthFeatures") -> Tuple[BreadthState, float]:
        """
        Classify breadth state based on above_ma20_ratio (strictly monotonic).

        Thresholds:
        - 极弱 (EXTREME_WEAK): above_ma20_ratio < 0.20
        - 偏弱 (WEAK): 0.20 <= ratio < 0.35
        - 中性 (NEUTRAL): 0.35 <= ratio < 0.55
        - 偏强 (STRONG): 0.55 <= ratio < 0.70
        - 过热 (OVERHEATED): ratio >= 0.70
        """
        r = f.above_ma20_ratio

        if r < BREADTH_THRESHOLDS["extreme_weak"]:
            # Scale from 0-20 for EXTREME_WEAK range
            score = 10.0 + (r / BREADTH_THRESHOLDS["extreme_weak"]) * 10.0
            return BreadthState.EXTREME_WEAK, max(5.0, min(score, 19.0))

        if r < BREADTH_THRESHOLDS["weak"]:
            # Scale from 20-35 for WEAK range
            normalized = (r - BREADTH_THRESHOLDS["extreme_weak"]) / (BREADTH_THRESHOLDS["weak"] - BREADTH_THRESHOLDS["extreme_weak"])
            score = 20.0 + normalized * 15.0
            return BreadthState.WEAK, max(20.0, min(score, 34.0))

        if r < BREADTH_THRESHOLDS["neutral"]:
            # Scale from 35-55 for NEUTRAL range
            normalized = (r - BREADTH_THRESHOLDS["weak"]) / (BREADTH_THRESHOLDS["neutral"] - BREADTH_THRESHOLDS["weak"])
            score = 35.0 + normalized * 20.0
            return BreadthState.NEUTRAL, max(35.0, min(score, 54.0))

        if r < BREADTH_THRESHOLDS["strong"]:
            # Scale from 55-70 for STRONG range
            normalized = (r - BREADTH_THRESHOLDS["neutral"]) / (BREADTH_THRESHOLDS["strong"] - BREADTH_THRESHOLDS["neutral"])
            score = 55.0 + normalized * 20.0
            return BreadthState.STRONG, max(55.0, min(score, 69.0))

        # OVERHEATED: ratio >= 0.70
        normalized = min((r - BREADTH_THRESHOLDS["strong"]) / (1.0 - BREADTH_THRESHOLDS["strong"]), 1.0)
        score = 70.0 + normalized * 30.0
        return BreadthState.OVERHEATED, min(score, 100.0)

    # -------------------------------------------------------------------------
    # Sentiment Classification
    # -------------------------------------------------------------------------

    def _classify_sentiment(self, f: "SentimentFeatures") -> Tuple[SentimentState, float]:
        """
        Classify sentiment state based on limit_up_rate, seal_rate, continuous_limit_up.

        - 冰点 (FROZEN): very low limit_up_rate, high limit_down, low seal_rate
        - 回暖 (WARMING): recovering limit_up_rate, improving seal_rate
        - 中性 (NEUTRAL): moderate values
        - 活跃 (ACTIVE): high limit_up_rate, high seal_rate, positive premium
        - 狂热 (EUPHORIC): extreme limit_up_rate, very high seal_rate, strong continuous
        """
        limit_rate = f.limit_up_rate
        seal_rate = f.seal_rate
        continuous = f.continuous_limit_up
        next_day_premium = getattr(f, 'next_day_premium', 0.0)

        # Composite sentiment score (0-100)
        sentiment_score = (
            limit_rate * 40 +
            seal_rate * 30 +
            min(continuous / 10, 1.0) * 15 +
            (next_day_premium + 5) / 10 * 15
        )
        sentiment_score = max(0.0, min(100.0, sentiment_score))

        if sentiment_score < 15:
            return SentimentState.FROZEN, sentiment_score
        elif sentiment_score < 35:
            return SentimentState.WARMING, sentiment_score
        elif sentiment_score < 60:
            return SentimentState.NEUTRAL, sentiment_score
        elif sentiment_score < 80:
            return SentimentState.ACTIVE, sentiment_score
        else:
            return SentimentState.EUPHORIC, sentiment_score

    # -------------------------------------------------------------------------
    # Style Classification
    # -------------------------------------------------------------------------

    def _classify_style(self, f: "StyleFeatures") -> Tuple[StyleState, float]:
        """
        Classify style state based on relative strength of style pairs.

        - 大盘防守: large_cap outperforming AND dividend outperforming growth
        - 小盘进攻: small_cap outperforming large_cap
        - 成长主导: growth significantly outperforming value
        - 红利防守: dividend outperforming growth
        - 风格冲突: conflicting signals across dimensions
        """
        rs_300_1000 = f.rs_300_1000  # 沪深300 vs 中证1000 (>0 means small cap outperformance)
        rs_50_growth = f.rs_50_growth  # 上证50 vs 创业板 (>0 means growth outperformance)
        rs_500_1000 = f.rs_500_1000  # 中证500 vs 中证1000

        # Normalize to -1 to +1 scale (0 is neutral)
        small_cap_signal = (rs_300_1000 - 0.5) * 2  # >0 = small cap out
        growth_signal = (rs_50_growth - 0.5) * 2  # >0 = growth out
        mid_small_signal = (rs_500_1000 - 0.5) * 2

        # Compute style score
        style_score = 50.0 + (small_cap_signal * 15) + (growth_signal * 10)

        # Count directional signals
        large_cap_signal = -small_cap_signal
        dividend_signal = growth_signal  # Approximation: growth = non-dividend

        # Classify based on dominant style
        if small_cap_signal > 0.3 and growth_signal > 0.2:
            return StyleState.SMALL_CAP_OFFENSIVE, min(100.0, max(style_score, 60.0))
        elif large_cap_signal > 0.3 and dividend_signal > 0.2:
            return StyleState.LARGE_CAP_DEFENSIVE, min(100.0, max(style_score, 60.0))
        elif growth_signal > 0.4:
            return StyleState.GROWTH_DOMINANT, min(100.0, max(style_score, 65.0))
        elif dividend_signal > 0.4:
            return StyleState.DIVIDEND_DEFENSIVE, min(100.0, max(style_score, 65.0))

        # Check for style conflict (conflicting signals across dimensions)
        signal_variance = np.var([small_cap_signal, growth_signal, mid_small_signal])
        if signal_variance > 0.3:
            return StyleState.STYLE_CONFLICT, max(30.0, min(style_score, 55.0))

        return StyleState.STYLE_CONFLICT, style_score

    # -------------------------------------------------------------------------
    # Sector Classification
    # -------------------------------------------------------------------------

    def _classify_sector(self, sectors: List["SectorFeatureResult"]) -> Tuple[SectorState, float]:
        """
        Classify sector rotation state based on strength_score distribution.

        - 无主线 (NO_THEME): no sector with strength_score > 1.5
        - 单主线 (SINGLE_THEME): exactly one sector strength_score > 2.0 AND persistence > 0.7
        - 双主线并行 (DUAL_THEME): two sectors strength_score > 1.8 AND persistence > 0.6
        - 高速轮动 (FAST_ROTATION): top-5 rankings change significantly over 5 days
        - 退潮分化 (FADING): declining strength + breadth across previously strong sectors
        """
        if not sectors:
            return SectorState.NO_THEME, 30.0

        sorted_sectors = sorted(sectors, key=lambda x: x.strength_score, reverse=True)
        strong_sectors = [s for s in sorted_sectors if s.strength_score > 1.5]
        very_strong = [s for s in sorted_sectors if s.strength_score > 2.0]
        strong_persistent = [s for s in sorted_sectors
                             if s.strength_score > 1.8 and s.persistence_score > 0.6]

        # Count sectors in each state
        main_uptrend = len([s for s in sectors if s.state == "主升趋势"])
        weakening = len([s for s in sectors if s.strength_score < -0.5])

        # Compute sector score
        if sorted_sectors:
            top_strength = sorted_sectors[0].strength_score
            sector_score = 30.0 + top_strength * 15
        else:
            sector_score = 30.0

        # Classification logic
        if len(very_strong) == 1 and very_strong[0].persistence_score > 0.7:
            return SectorState.SINGLE_THEME, min(100.0, sector_score)

        if len(strong_persistent) >= 2:
            return SectorState.DUAL_THEME, min(100.0, sector_score)

        if len(strong_sectors) == 0:
            return SectorState.NO_THEME, min(100.0, sector_score)

        # Fast rotation: many sectors in "主升趋势" but with low persistence
        if main_uptrend >= 3:
            avg_persistence = np.mean([s.persistence_score for s in sectors if s.state == "主升趋势"])
            if avg_persistence < 0.4:
                return SectorState.FAST_ROTATION, min(100.0, sector_score)

        # Fading: many weak sectors
        if weakening >= len(sectors) * 0.4:
            return SectorState.FADING, min(100.0, sector_score)

        return SectorState.NO_THEME, min(100.0, sector_score)

    # -------------------------------------------------------------------------
    # Risk Classification & Risk Flag Monitoring
    # -------------------------------------------------------------------------

    def _classify_risk(
        self,
        f: "RiskFeatures",
        breadth_f: "BreadthFeatures",
    ) -> Tuple[RiskState, float, List[str]]:
        """
        Classify risk state and detect risk flags.

        Risk flags (6 total):
        1. vol_spike: realized_vol > 2x historical average
        2. breadth_collapse: above_ma20_ratio dropped > 10pct from previous day
        3. sector_overcrowding: top sector amount_share > mean + 2*std
        4. northbound_outflow: north_net_flow < 0 for 3+ consecutive days
        5. leadership_breakdown: top-5 sector leader stocks avg decline > 2%
        6. index_break_support: 沪深300 closed below MA60
        """
        risk_flags: List[str] = []

        # Flag 1: vol_spike
        if f.vol_spike_detected:
            risk_flags.append("vol_spike")

        # Flag 2: breadth_collapse (requires previous day's ratio)
        if self._prev_breadth_ratio is not None:
            drop = self._prev_breadth_ratio - breadth_f.above_ma20_ratio
            if drop > 0.10:
                risk_flags.append("breadth_collapse")

        # Flag 3: sector_overcrowding
        if f.sector_overcrowded:
            risk_flags.append("sector_overcrowding")

        # Flag 4: northbound_outflow
        if f.north_outflow_3d:
            risk_flags.append("northbound_outflow")

        # Flag 5: leadership_breakdown
        if f.leadership_breakdown:
            risk_flags.append("leadership_breakdown")

        # Flag 6: index_break_support
        if f.index_broke_support:
            risk_flags.append("index_break_support")

        # Compute risk score (0-100, higher = riskier)
        vol_component = min(f.realized_vol / 0.30 * 40, 40)  # vol > 30% -> max vol component
        drawdown_component = min(f.max_drawdown / 0.15 * 30, 30)  # drawdown > 15% -> max
        flag_component = min(len(risk_flags) * 15, 30)  # 2+ flags -> max flag component
        risk_score = min(100.0, vol_component + drawdown_component + flag_component)

        # Classify risk state
        if risk_score < 20 and len(risk_flags) == 0:
            return RiskState.LOW, risk_score, risk_flags
        elif risk_score < 45 and len(risk_flags) <= 1:
            return RiskState.NEUTRAL, risk_score, risk_flags
        elif risk_score < 70 or len(risk_flags) <= 2:
            return RiskState.HIGH, risk_score, risk_flags
        else:
            return RiskState.EXTREME, risk_score, risk_flags

    # -------------------------------------------------------------------------
    # Composite Regime Classification
    # -------------------------------------------------------------------------

    def _classify_composite(
        self,
        trend: TrendState,
        breadth: BreadthState,
        sentiment: SentimentState,
        style: StyleState,
        sector: SectorState,
        risk: RiskState,
    ) -> CompositeRegime:
        """
        Map dimension states to composite regime using priority rules.

        Priority (highest to lowest):
        1. risk == EXTREME -> HIGH_VOL_WARNING
        2. breadth == EXTREME_WEAK AND sentiment == FROZEN -> PANIC_BOTTOMING
        3. trend in (BREAKDOWN, WEAKENING) AND breadth in (EXTREME_WEAK, WEAK) -> BROAD_WEAKNESS_HOLD
        4. trend == STRONG_UP AND style == GROWTH_DOMINANT -> TREND_RISK_ON_GROWTH
        5. trend == STRONG_UP AND style == SMALL_CAP_OFFENSIVE -> TREND_RISK_ON_SMALLCAP
        6. style == DIVIDEND_DEFENSIVE -> DEFENSIVE_DIVIDEND
        7. default -> BALANCED_ROTATION
        """
        # Priority 1: Extreme risk
        if risk == RiskState.EXTREME:
            return CompositeRegime.HIGH_VOL_WARNING

        # Priority 2: Panic bottoming
        if breadth == BreadthState.EXTREME_WEAK and sentiment == SentimentState.FROZEN:
            return CompositeRegime.PANIC_BOTTOMING

        # Priority 3: Broad weakness hold
        if trend in (TrendState.BREAKDOWN, TrendState.WEAKENING) and \
           breadth in (BreadthState.EXTREME_WEAK, BreadthState.WEAK):
            return CompositeRegime.BROAD_WEAKNESS_HOLD

        # Priority 4: Trend + Growth
        if trend == TrendState.STRONG_UP and style == StyleState.GROWTH_DOMINANT:
            return CompositeRegime.TREND_RISK_ON_GROWTH

        # Priority 5: Trend + Smallcap
        if trend == TrendState.STRONG_UP and style == StyleState.SMALL_CAP_OFFENSIVE:
            return CompositeRegime.TREND_RISK_ON_SMALLCAP

        # Priority 6: Defensive dividend
        if style == StyleState.DIVIDEND_DEFENSIVE:
            return CompositeRegime.DEFENSIVE_DIVIDEND

        # Default: Balanced rotation
        return CompositeRegime.BALANCED_ROTATION

    # -------------------------------------------------------------------------
    # Score Calculations
    # -------------------------------------------------------------------------

    def _compute_regime_score(
        self,
        trend_score: float,
        breadth_score: float,
        sentiment_score: float,
        style_score: float,
        sector_score: float,
        risk_score: float,
    ) -> float:
        """
        Compute composite regime score.

        Formula: 0.20*trend + 0.15*breadth + 0.15*sentiment + 0.15*style + 0.15*sector - 0.20*risk

        Note: risk_score is subtracted (higher risk = lower regime score).
        """
        regime_score = (
            0.20 * trend_score +
            0.15 * breadth_score +
            0.15 * sentiment_score +
            0.15 * style_score +
            0.15 * sector_score -
            0.20 * risk_score
        )
        return max(0.0, min(100.0, regime_score))

    # -------------------------------------------------------------------------
    # Evidence Extraction
    # -------------------------------------------------------------------------

    def _extract_evidence(
        self,
        date: str,
        trend_features: Dict[str, "TrendFeatures"],
        breadth_features: "BreadthFeatures",
        sentiment_features: "SentimentFeatures",
        style_features: "StyleFeatures",
        sector_features: List["SectorFeatureResult"],
        capital_features: "CapitalFeatures",
        risk_features: "RiskFeatures",
        trend_state: TrendState,
        breadth_state: BreadthState,
        sentiment_state: SentimentState,
        style_state: StyleState,
        sector_state: SectorState,
        risk_state: RiskState,
        regime: CompositeRegime,
    ) -> Tuple[List[str], List[str]]:
        """
        Extract 3 key supporting evidence items and counter-evidence items.

        Evidence is drawn from the most extreme / significant indicators
        that support the current regime classification.
        """
        evidence = []
        counter = []

        # Trend evidence
        f300 = trend_features.get("sh000300")
        if f300:
            if f300.ma_alignment == "多头排列":
                evidence.append(f"沪深300均线多头排列（MA5>{MA10}>{MA20}>{MA60}）")
            elif f300.ma_alignment == "空头排列":
                evidence.append(f"沪深300均线空头排列（MA5<{MA10}<{MA20}<{MA60}）")
            if f300.macd_signal == "金叉":
                evidence.append(f"MACD指标出现金叉信号")
            elif f300.macd_signal == "死叉":
                counter.append(f"MACD指标出现死叉信号")

        # Breadth evidence
        if breadth_state in (BreadthState.EXTREME_WEAK, BreadthState.WEAK):
            counter.append(f"站上MA20个股比例仅{breadth_features.above_ma20_ratio:.1%}，市场广度极弱")
        elif breadth_state == BreadthState.OVERHEATED:
            evidence.append(f"站上MA20个股比例达{breadth_features.above_ma20_ratio:.1%}，市场过热")

        # Sentiment evidence
        if sentiment_state == SentimentState.EUPHORIC:
            evidence.append(f"情绪极度狂热（涨停{int(sentiment_features.limit_up_rate * 100)}家，封板率{sentiment_features.seal_rate:.1%}）")
        elif sentiment_state == SentimentState.FROZEN:
            counter.append(f"情绪冰点（涨停家数极少，封板率低迷）")

        # Sector evidence
        if sector_features:
            top = max(sector_features, key=lambda x: x.strength_score)
            if top.strength_score > 1.5:
                evidence.append(f"行业主线清晰：{top.industry_name}强度得分{top.strength_score:.2f}，持续性{top.persistence_score:.1%}")
            weak = min(sector_features, key=lambda x: x.strength_score)
            if weak.strength_score < -1.0:
                counter.append(f"{weak.industry_name}行业走弱，得分{weak.strength_score:.2f}")

        # Capital evidence
        if capital_features.north_net_flow < -50:
            counter.append(f"北向资金大幅流出{-capital_features.north_net_flow:.1f}亿元")
        elif capital_features.north_net_flow > 50:
            evidence.append(f"北向资金净流入{capital_features.north_net_flow:.1f}亿元")

        # Risk evidence
        if risk_state == RiskState.EXTREME:
            counter.append(f"风险指标极高（得分{risk_features.realized_vol:.1%}），建议防御为主")
        elif risk_state == RiskState.LOW:
            evidence.append(f"市场风险偏低，可适当积极配置")

        # Style evidence
        if style_state == StyleState.SMALL_CAP_OFFENSIVE:
            evidence.append(f"小盘股风格占优，资金流向中证1000")
        elif style_state == StyleState.LARGE_CAP_DEFENSIVE:
            evidence.append(f"大盘防守风格，资金流向权重蓝筹")

        # Limit to 3 key evidence + counter
        key_evidence = evidence[:3]
        if len(key_evidence) < 3:
            # Add additional evidence if needed
            for c in counter[:3 - len(key_evidence)]:
                key_evidence.append(f"[警示] {c}")

        counter_evidence = counter[:3]

        # Ensure exactly 3 key evidence
        while len(key_evidence) < 3:
            key_evidence.append("市场运行平稳，无明显异常信号")

        return key_evidence[:3], counter_evidence[:3]

    # -------------------------------------------------------------------------
    # Confidence Calculation
    # -------------------------------------------------------------------------

    def _compute_confidence(
        self,
        missing_data: List[str],
        trend_state: TrendState,
        breadth_state: BreadthState,
        sentiment_state: SentimentState,
    ) -> float:
        """
        Compute confidence score (0.1 to 1.0).

        Base = 1.0
        - Each missing core indicator: -0.15
        - Signal consistency across dimensions (trend/breadth/sentiment aligned): +0.10
        - Extreme anomalous values detected: -0.10
        - Proxy/estimated data items: -0.05 each

        Clamped to [0.1, 1.0]
        """
        base = 1.0

        # Deduct for missing core indicators
        core_indicators = ["index_price", "breadth_data", "sentiment_data"]
        for indicator in core_indicators:
            if indicator in missing_data:
                base -= 0.15

        # Signal consistency bonus
        # Check if trend/breadth/sentiment are directionally aligned
        trend_dir = _trend_direction(trend_state)
        breadth_dir = _breadth_direction(breadth_state)
        sentiment_dir = _sentiment_direction(sentiment_state)

        if trend_dir == breadth_dir == sentiment_dir:
            base += 0.10

        # Extreme value penalty
        extreme_states = {
            TrendState.BREAKDOWN, TrendState.STRONG_UP,
            BreadthState.EXTREME_WEAK, BreadthState.OVERHEATED,
            SentimentState.EUPHORIC, SentimentState.FROZEN,
        }
        extreme_count = sum(1 for s in [trend_state, breadth_state, sentiment_state]
                           if s in extreme_states)
        if extreme_count >= 2:
            base -= 0.10

        # Proxy data penalty
        proxy_count = sum(1 for d in missing_data if "proxy" in d or "estimate" in d)
        base -= proxy_count * 0.05

        return max(0.1, min(1.0, base))


# -------------------------------------------------------------------------
# Helper functions for confidence calculation
# -------------------------------------------------------------------------

def _trend_direction(state: TrendState) -> int:
    """Trend direction: 1 = bullish, 0 = neutral, -1 = bearish"""
    if state in (TrendState.STRONG_UP, TrendState.PULLBACK_IN_UPTREND):
        return 1
    elif state in (TrendState.BREAKDOWN, TrendState.WEAKENING):
        return -1
    return 0


def _breadth_direction(state: BreadthState) -> int:
    """Breadth direction: 1 = positive, 0 = neutral, -1 = negative"""
    if state in (BreadthState.STRONG, BreadthState.OVERHEATED):
        return 1
    elif state in (BreadthState.EXTREME_WEAK, BreadthState.WEAK):
        return -1
    return 0


def _sentiment_direction(state: SentimentState) -> int:
    """Sentiment direction: 1 = positive, 0 = neutral, -1 = negative"""
    if state in (SentimentState.ACTIVE, SentimentState.EUPHORIC):
        return 1
    elif state in (SentimentState.FROZEN,):
        return -1
    return 0


# -------------------------------------------------------------------------
# Type stubs for feature classes (imported from features module)
# These are defined here to avoid circular imports
# -------------------------------------------------------------------------

@dataclass
class TrendFeatures:
    """Trend features for a single index."""
    code: str
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    ma120: float
    ma_alignment: str  # "多头排列" / "空头排列" / "缠绕"
    bias_ma5: float
    bias_ma20: float
    bias_ma60: float
    macd_dif: float
    macd_dea: float
    macd_bar: float
    macd_signal: str  # "金叉" / "死叉" / "中性"
    atr_20: float
    rsrs_score: float  # 0-1
    near_high_20d: bool
    break_support: bool
    rs_vs_300: float


@dataclass
class BreadthFeatures:
    """Market breadth features."""
    up_down_ratio: float
    limit_up_rate: float
    seal_rate: float
    above_ma20_ratio: float
    new_high_ratio: float
    amount_deviation_5d: float
    amount_deviation_20d: float
    breadth_score: float  # 0-100


@dataclass
class SentimentFeatures:
    """Market sentiment features."""
    limit_up_rate: float
    limit_down_rate: float
    seal_rate: float
    continuous_limit_up: int
    next_day_premium: float
    sentiment_score: float  # 0-100


@dataclass
class StyleFeatures:
    """Style rotation features."""
    rs_50_growth: float  # Relative strength: 上证50 vs 创业板
    rs_300_1000: float  # 沪深300 vs 中证1000
    rs_500_1000: float  # 中证500 vs 中证1000
    style_score: float  # 0-100


@dataclass
class SectorFeatureResult:
    """Sector feature result for one industry."""
    industry_code: str
    industry_name: str
    strength_score: float
    persistence_score: float
    crowding_score: float
    leadership_score: float
    state: str  # 主升趋势/趋势强化/震荡整理/超跌反弹/弱势退潮


@dataclass
class CapitalFeatures:
    """Capital flow features."""
    total_amount: float
    amount_deviation_5d: float
    amount_deviation_20d: float
    north_net_flow: float
    north_5d_avg: float
    margin_balance: float
    margin_delta: float
    main_net_flow: float
    etf_net_flow: float
    data_freshness: Dict[str, str] = field(default_factory=dict)


@dataclass
class RiskFeatures:
    """Risk features."""
    realized_vol: float
    atr_vol: float
    vol_ratio: float  # short-term / long-term
    max_drawdown: float
    cross_asset_corr: float
    sector_corr_elevation: float
    vol_spike_detected: bool = False
    sector_overcrowded: bool = False
    north_outflow_3d: bool = False
    leadership_breakdown: bool = False
    index_broke_support: bool = False
    risk_score: float = 0.0
