"""
Market Diagnostic Engine

Main orchestrator for the complete diagnostic workflow.
Coordinates data fetching → feature calculation → state classification → report generation.

Reference: Requirements 21.6, 22.1-22.7, design.md Section 3.6
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# ============================================================================
# Feature Type Imports (for standalone use without external dependencies)
# ============================================================================

try:
    from .states.classifier import (
        MarketStateClassifier,
        MarketStateResult,
        TrendFeatures,
        BreadthFeatures,
        SentimentFeatures,
        StyleFeatures,
        SectorFeatureResult,
        CapitalFeatures,
        RiskFeatures,
    )
    from .config import (
        PRIMARY_INDEX,
        RISK_FLAGS,
        REGIME_STRATEGY_MAPPING,
        RISK_FLAG_DESCRIPTIONS,
    )
except ImportError:
    from states.classifier import (
        MarketStateClassifier,
        MarketStateResult,
        TrendFeatures,
        BreadthFeatures,
        SentimentFeatures,
        StyleFeatures,
        SectorFeatureResult,
        CapitalFeatures,
        RiskFeatures,
    )
    from config import (
        PRIMARY_INDEX,
        RISK_FLAGS,
        REGIME_STRATEGY_MAPPING,
        RISK_FLAG_DESCRIPTIONS,
    )


# ============================================================================
# Fallback Feature Constructors
# ============================================================================

def _make_fallback_breadth_features() -> BreadthFeatures:
    """Return a neutral BreadthFeatures when breadth data is unavailable."""
    return BreadthFeatures(
        up_down_ratio=1.0,
        limit_up_rate=0.01,
        seal_rate=0.5,
        above_ma20_ratio=0.45,
        above_ma60_ratio=0.45,
        new_high_ratio=0.01,
        amount_deviation_5d=0.0,
        amount_deviation_20d=0.0,
        breadth_score=50.0,
    )


def _make_fallback_sentiment_features() -> SentimentFeatures:
    """Return a neutral SentimentFeatures when sentiment data is unavailable."""
    return SentimentFeatures(
        limit_up_down_ratio=1.0,
        continuous_limit_up=0,
        seal_rate=0.5,
        next_day_premium=0.0,
        turnover_zscore=0.0,
        sentiment_score=50.0,
    )


def _make_fallback_capital_features() -> CapitalFeatures:
    """Return a neutral CapitalFeatures when capital data is unavailable."""
    return CapitalFeatures(
        total_amount=0.0,
        amount_deviation_5d=0.0,
        amount_deviation_20d=0.0,
        amount_deviation_60d=0.0,
        north_net_flow=0.0,
        north_5d_avg=0.0,
        north_flow_trend="neutral",
        margin_balance=0.0,
        margin_delta=0.0,
        main_net_flow=0.0,
        etf_net_flow=0.0,
        data_freshness={},
        has_delayed_data=False,
    )


def _make_fallback_risk_features(index_data: Dict[str, Any]) -> RiskFeatures:
    """Return a minimal RiskFeatures computed from available index data."""
    return RiskFeatures(
        realized_volatility={},
        atr_volatility={},
        vol_ratio_short_long={},
        index_drawdown={},
        cross_index_correlation=0.0,
        sector_correlation_elevation=0.0,
        cvix_value=None,
        cvix_percentile=None,
        has_cvix_data=False,
    )


# ============================================================================
# One-Sentence Summary Generator
# ============================================================================

def generate_one_sentence_summary(state_result: MarketStateResult) -> str:
    """
    Generate a concise one-sentence market summary from a MarketStateResult.

    Parameters
    ----------
    state_result : MarketStateResult
        The classified market state.

    Returns
    -------
    str
        A single-sentence summary in Chinese.
    """
    # Regime display names
    _regime_display: Dict[str, str] = {
        "trend_risk_on_growth": "趋势进攻-成长主导",
        "trend_risk_on_smallcap": "趋势进攻-小盘主导",
        "balanced_rotation": "均衡轮动",
        "defensive_dividend": "防守-红利",
        "high_volatility_warning": "高波动预警",
        "panic_bottoming": "恐慌探底",
        "broad_weakness_hold": "全面弱势-持币观望",
    }

    regime_str = (
        state_result.composite_regime.value
        if hasattr(state_result.composite_regime, "value")
        else str(state_result.composite_regime)
    )
    regime_display = _regime_display.get(regime_str, regime_str)

    trend_str = (
        state_result.trend_state.value
        if hasattr(state_result.trend_state, "value")
        else str(state_result.trend_state)
    )
    breadth_str = (
        state_result.breadth_state.value
        if hasattr(state_result.breadth_state, "value")
        else str(state_result.breadth_state)
    )
    sentiment_str = (
        state_result.sentiment_state.value
        if hasattr(state_result.sentiment_state, "value")
        else str(state_result.sentiment_state)
    )
    risk_str = (
        state_result.risk_state.value
        if hasattr(state_result.risk_state, "value")
        else str(state_result.risk_state)
    )

    confidence_pct = int(state_result.confidence * 100)

    # Build the summary sentence
    summary = (
        f"当前市场处于【{regime_display}】状态，"
        f"趋势{trend_str}，广度{breadth_str}，情绪{sentiment_str}，"
        f"风险{risk_str}，综合得分{state_result.regime_score:.1f}，"
        f"置信度{confidence_pct}%。"
    )

    # Append key evidence if available
    if state_result.key_evidence:
        summary += state_result.key_evidence[0]

    return summary


# ============================================================================
# Diagnostic Report Data Class
# ============================================================================

class DiagnosticReport:
    """
    Structured diagnostic report containing all market state information.

    Reference: Requirements 18.1-18.10, 19.1-19.12
    """

    def __init__(
        self,
        date: str,
        trend_state: str,
        breadth_state: str,
        sentiment_state: str,
        style_state: str,
        sector_state: str,
        risk_state: str,
        composite_regime: str,
        trend_score: float,
        breadth_score: float,
        sentiment_score: float,
        risk_score: float,
        regime_score: float,
        indices: List[Dict],
        breadth_metrics: Dict,
        sentiment_metrics: Dict,
        style_metrics: Dict,
        sector_table: List[Dict],
        capital_metrics: Dict,
        risk_flags: List[str],
        one_sentence_summary: str,
        key_evidence: List[str],
        counter_evidence: List[str],
        strategy_mapping: List[str],
        confidence: float,
        missing_data: List[str],
    ):
        self.date = date
        self.trend_state = trend_state
        self.breadth_state = breadth_state
        self.sentiment_state = sentiment_state
        self.style_state = style_state
        self.sector_state = sector_state
        self.risk_state = risk_state
        self.composite_regime = composite_regime
        self.trend_score = trend_score
        self.breadth_score = breadth_score
        self.sentiment_score = sentiment_score
        self.risk_score = risk_score
        self.regime_score = regime_score
        self.indices = indices
        self.breadth_metrics = breadth_metrics
        self.sentiment_metrics = sentiment_metrics
        self.style_metrics = style_metrics
        self.sector_table = sector_table
        self.capital_metrics = capital_metrics
        self.risk_flags = risk_flags
        self.one_sentence_summary = one_sentence_summary
        self.key_evidence = key_evidence
        self.counter_evidence = counter_evidence
        self.strategy_mapping = strategy_mapping
        self.confidence = confidence
        self.missing_data = missing_data

    @classmethod
    def from_state_result(
        cls,
        state_result: MarketStateResult,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
        index_data: Dict[str, Any],
        one_sentence_summary: str,
    ) -> "DiagnosticReport":
        """Create a DiagnosticReport from a MarketStateResult and feature data."""
        # Extract state values
        trend_state = _get_enum_value(state_result.trend_state)
        breadth_state = _get_enum_value(state_result.breadth_state)
        sentiment_state = _get_enum_value(state_result.sentiment_state)
        style_state = _get_enum_value(state_result.style_state)
        sector_state = _get_enum_value(state_result.sector_state)
        risk_state = _get_enum_value(state_result.risk_state)
        composite_regime = _get_enum_value(state_result.composite_regime)

        # Build indices list
        indices = []
        for code, tf in trend_features.items():
            indices.append({
                "code": code,
                "ma5": tf.ma5,
                "ma10": tf.ma10,
                "ma20": tf.ma20,
                "ma60": tf.ma60,
                "ma_alignment": tf.ma_alignment,
                "macd_signal": tf.macd_signal,
                "rsrs_score": tf.rsrs_score,
            })

        # Build breadth metrics
        breadth_metrics = {
            "up_down_ratio": breadth_features.up_down_ratio,
            "limit_up_rate": breadth_features.limit_up_rate,
            "seal_rate": breadth_features.seal_rate,
            "above_ma20_ratio": breadth_features.above_ma20_ratio,
            "above_ma60_ratio": breadth_features.above_ma60_ratio,
            "new_high_ratio": breadth_features.new_high_ratio,
            "breadth_score": breadth_features.breadth_score,
        }

        # Build sentiment metrics
        sentiment_metrics = {
            "limit_up_down_ratio": sentiment_features.limit_up_down_ratio,
            "continuous_limit_up": sentiment_features.continuous_limit_up,
            "seal_rate": sentiment_features.seal_rate,
            "next_day_premium": sentiment_features.next_day_premium,
            "sentiment_score": sentiment_features.sentiment_score,
        }

        # Build style metrics
        style_metrics = {
            "rs_large_vs_small": style_features.rs_large_vs_small,
            "rs_300_vs_1000": style_features.rs_300_vs_1000,
            "dominant_style": style_features.dominant_style,
        }

        # Build sector table
        sector_table = []
        for sf in sector_features:
            sector_table.append({
                "industry_code": sf.industry_code,
                "industry_name": sf.industry_name,
                "strength_score": sf.strength_score,
                "persistence_score": sf.persistence_score,
                "state": sf.state,
                "amount_share": sf.amount_share,
            })

        # Build capital metrics
        capital_metrics = {
            "total_amount": capital_features.total_amount,
            "north_net_flow": capital_features.north_net_flow,
            "north_5d_avg": capital_features.north_5d_avg,
            "margin_balance": capital_features.margin_balance,
            "main_net_flow": capital_features.main_net_flow,
            "has_delayed_data": capital_features.has_delayed_data,
        }

        # Get strategy mapping
        regime_key = composite_regime
        if isinstance(composite_regime, str):
            regime_key = composite_regime
        strategy_mapping = REGIME_STRATEGY_MAPPING.get(regime_key, [])

        return cls(
            date=state_result.date,
            trend_state=trend_state,
            breadth_state=breadth_state,
            sentiment_state=sentiment_state,
            style_state=style_state,
            sector_state=sector_state,
            risk_state=risk_state,
            composite_regime=composite_regime,
            trend_score=state_result.trend_score,
            breadth_score=state_result.breadth_score,
            sentiment_score=state_result.sentiment_score,
            risk_score=state_result.risk_score,
            regime_score=state_result.regime_score,
            indices=indices,
            breadth_metrics=breadth_metrics,
            sentiment_metrics=sentiment_metrics,
            style_metrics=style_metrics,
            sector_table=sector_table,
            capital_metrics=capital_metrics,
            risk_flags=state_result.risk_flags,
            one_sentence_summary=one_sentence_summary,
            key_evidence=state_result.key_evidence,
            counter_evidence=state_result.counter_evidence,
            strategy_mapping=strategy_mapping,
            confidence=state_result.confidence,
            missing_data=state_result.missing_data,
        )

    def to_json(self) -> str:
        """Convert report to JSON string."""
        import json
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


def _get_enum_value(enum_or_str) -> str:
    """Extract string value from enum or return as-is."""
    if hasattr(enum_or_str, "value"):
        return enum_or_str.value
    return str(enum_or_str)


# ============================================================================
# Main Diagnostic Engine
# ============================================================================

class MarketDiagnosticEngine:
    """
    Orchestrates the complete market diagnostic workflow.

    Workflow:
        Step 1: Fetch data (index_series / breadth / sector / capital)
        Step 2: Calculate features (trend / breadth / sentiment / style / sector / capital / risk)
        Step 3: State classification (MarketStateClassifier.classify())
        Step 4: Build structured report (DiagnosticReport)
        Step 5: Render Markdown (optionally with LLM narrative)

    Reference: Requirements 21.6, 22.1, 22.2, 22.5, 22.6, 22.7
    """

    def __init__(
        self,
        data_manager=None,
        analyzer=None,
        enable_llm_narrative: bool = True,
    ):
        """
        Initialize the diagnostic engine.

        Parameters
        ----------
        data_manager : optional
            DataFetcherManager instance for data fetching.
            If None, uses mock data for testing.
        analyzer : optional
            LLM analyzer (e.g., GeminiAnalyzer) for narrative generation.
            If None, LLM narrative is skipped even if enable_llm_narrative=True.
        enable_llm_narrative : bool
            Whether to attempt LLM narrative generation (default True).
        """
        self.data_manager = data_manager
        self.classifier = MarketStateClassifier()
        self.analyzer = analyzer
        self.enable_llm_narrative = enable_llm_narrative

    # ------------------------------------------------------------------
    # Public Entry Point
    # ------------------------------------------------------------------

    def run(self, date: str = None) -> Tuple[DiagnosticReport, str]:
        """
        Execute the complete diagnostic workflow.

        Parameters
        ----------
        date : str, optional
            Target trading date in 'YYYY-MM-DD' format.
            Defaults to today's date.

        Returns
        -------
        Tuple[DiagnosticReport, str]
            (structured_report, markdown_string)

        Reference: Requirements 22.1, 22.2, 22.5, 22.6, 22.7
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        ts = datetime.now().isoformat()
        logger.info(f"[{ts}] MarketDiagnosticEngine.run() started for date={date}")

        missing_data: List[str] = []

        # ----------------------------------------------------------------
        # Step 1: Fetch data
        # ----------------------------------------------------------------
        index_data, breadth_data, sector_data, capital_data = self._fetch_data(
            date, missing_data
        )

        # ----------------------------------------------------------------
        # Step 2: Calculate features
        # ----------------------------------------------------------------
        (
            trend_features,
            breadth_features,
            sentiment_features,
            style_features,
            sector_features,
            capital_features,
            risk_features,
        ) = self._compute_features(
            date,
            index_data,
            breadth_data,
            sector_data,
            capital_data,
            missing_data,
        )

        # ----------------------------------------------------------------
        # Step 3: State classification
        # ----------------------------------------------------------------
        state_result = self._classify_states(
            date,
            trend_features,
            breadth_features,
            sentiment_features,
            style_features,
            sector_features,
            capital_features,
            risk_features,
            missing_data,
        )

        # ----------------------------------------------------------------
        # Step 4: Build structured report
        # ----------------------------------------------------------------
        one_sentence = generate_one_sentence_summary(state_result)

        report = DiagnosticReport.from_state_result(
            state_result=state_result,
            trend_features=trend_features,
            breadth_features=breadth_features,
            sentiment_features=sentiment_features,
            style_features=style_features,
            sector_features=sector_features,
            capital_features=capital_features,
            risk_features=risk_features,
            index_data=index_data,
            one_sentence_summary=one_sentence,
        )

        # Ensure missing_data is included in the report
        if missing_data:
            all_missing = list(dict.fromkeys(missing_data + list(report.missing_data)))
            report.missing_data = all_missing

        # ----------------------------------------------------------------
        # Step 5: Render Markdown
        # ----------------------------------------------------------------
        markdown_str = self._render_markdown(report)

        ts_end = datetime.now().isoformat()
        logger.info(
            f"[{ts_end}] MarketDiagnosticEngine.run() completed. "
            f"regime={report.composite_regime}, confidence={report.confidence:.2f}, "
            f"missing_data={len(report.missing_data)} items"
        )

        return report, markdown_str

    # ------------------------------------------------------------------
    # Step 1: Data Fetching
    # ------------------------------------------------------------------

    def _fetch_data(
        self,
        date: str,
        missing_data: List[str],
    ) -> Tuple[
        Dict[str, Any],
        Optional[BreadthFeatures],
        List[SectorFeatureResult],
        Optional[CapitalFeatures],
    ]:
        """
        Fetch all required data, logging errors and continuing on failure.

        Reference: Requirements 22.1, 22.2
        """
        ts = datetime.now().isoformat()

        # --- Index series (critical) ---
        index_data: Dict[str, Any] = {}
        if self.data_manager is not None:
            try:
                # Try to fetch from data manager
                # This is a placeholder - actual implementation would call:
                # index_data = self.data_manager.get_main_indices(date=date)
                logger.info(f"[{ts}] [DataSource] Fetching index data for {date}")
                missing_data.append("index_data: data_manager not fully configured")
            except Exception as exc:
                logger.error(
                    f"[{ts}] [DataSource: index_series] Failed to fetch index data for {date}: {exc}"
                )
                missing_data.append("index_data")
        else:
            # No data manager - use empty
            missing_data.append("index_data")

        # --- Breadth data (non-critical) ---
        breadth_data = None
        missing_data.append("breadth_data: no data manager configured")

        # --- Sector data (non-critical) ---
        sector_data: List[SectorFeatureResult] = []
        missing_data.append("sector_data: no data manager configured")

        # --- Capital flow data (non-critical, often T+1) ---
        capital_data = None
        missing_data.append("capital_data: no data manager configured")

        return index_data, breadth_data, sector_data, capital_data

    # ------------------------------------------------------------------
    # Step 2: Feature Calculation
    # ------------------------------------------------------------------

    def _compute_features(
        self,
        date: str,
        index_data: Dict[str, Any],
        breadth_data: Optional[BreadthFeatures],
        sector_data: List[SectorFeatureResult],
        capital_data: Optional[CapitalFeatures],
        missing_data: List[str],
    ) -> Tuple[
        Dict[str, TrendFeatures],
        BreadthFeatures,
        SentimentFeatures,
        StyleFeatures,
        List[SectorFeatureResult],
        CapitalFeatures,
        RiskFeatures,
    ]:
        """
        Compute all feature layers, falling back to neutral defaults on failure.

        Reference: Requirements 22.2, 22.4
        """
        ts = datetime.now().isoformat()

        # --- Trend features ---
        trend_features: Dict[str, TrendFeatures] = {}
        if index_data:
            try:
                # Build trend features from index data
                for code, data in index_data.items():
                    if isinstance(data, dict):
                        trend_features[code] = TrendFeatures(
                            code=code,
                            ma5=data.get("ma5", 0.0),
                            ma10=data.get("ma10", 0.0),
                            ma20=data.get("ma20", 0.0),
                            ma60=data.get("ma60", 0.0),
                            ma_alignment=data.get("ma_alignment", "缠绕"),
                            macd_signal=data.get("macd_signal", "中性"),
                            rsrs_score=data.get("rsrs_score", 0.5),
                            break_support=data.get("break_support", False),
                        )
            except Exception as exc:
                logger.error(f"[{ts}] [Feature: trend] Failed to compute trend features: {exc}")
                missing_data.append("trend_features")
        else:
            missing_data.append("trend_features")

        # --- Breadth features ---
        if breadth_data is not None:
            breadth_features = breadth_data
        else:
            logger.warning(f"[{ts}] [Feature: breadth] No breadth data available, using fallback")
            breadth_features = _make_fallback_breadth_features()

        # --- Sentiment features ---
        if breadth_data is not None:
            sentiment_features = _make_fallback_sentiment_features()
        else:
            sentiment_features = _make_fallback_sentiment_features()

        # --- Style features ---
        style_features = StyleFeatures(
            rs_large_vs_small=1.0,
            rs_300_vs_1000=1.0,
            dominant_style="风格冲突",
        )
        missing_data.append("style_features")

        # --- Sector features ---
        sector_features = sector_data if sector_data else []
        if not sector_features:
            missing_data.append("sector_features")

        # --- Capital features ---
        if capital_data is not None:
            capital_features = capital_data
        else:
            capital_features = _make_fallback_capital_features()

        # --- Risk features ---
        if index_data:
            risk_features = _make_fallback_risk_features(index_data)
        else:
            risk_features = _make_fallback_risk_features({})
            missing_data.append("risk_features")

        return (
            trend_features,
            breadth_features,
            sentiment_features,
            style_features,
            sector_features,
            capital_features,
            risk_features,
        )

    # ------------------------------------------------------------------
    # Step 3: State Classification
    # ------------------------------------------------------------------

    def _classify_states(
        self,
        date: str,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
        missing_data: List[str],
    ) -> MarketStateResult:
        """
        Run the MarketStateClassifier with all computed features.

        Reference: Requirement 22.5
        """
        ts = datetime.now().isoformat()
        try:
            return self.classifier.classify(
                trend_features=trend_features,
                breadth_features=breadth_features,
                sentiment_features=sentiment_features,
                style_features=style_features,
                sector_features=sector_features,
                capital_features=capital_features,
                risk_features=risk_features,
                date=date,
                missing_data=missing_data,
            )
        except Exception as exc:
            logger.error(
                f"[{ts}] [Classifier] State classification failed: {exc}. "
                "Returning default BALANCED_ROTATION state."
            )
            return self._make_default_state_result(date, missing_data)

    def _make_default_state_result(
        self, date: str, missing_data: List[str]
    ) -> MarketStateResult:
        """Return a safe default MarketStateResult when classification fails."""
        try:
            from .states.enums import (
                TrendState, BreadthState, SentimentState, StyleState,
                SectorState, RiskState, CompositeRegime,
            )
        except ImportError:
            from states.enums import (
                TrendState, BreadthState, SentimentState, StyleState,
                SectorState, RiskState, CompositeRegime,
            )

        return MarketStateResult(
            date=date,
            trend_state=TrendState.RANGING,
            breadth_state=BreadthState.NEUTRAL,
            sentiment_state=SentimentState.NEUTRAL,
            style_state=StyleState.STYLE_CONFLICT,
            sector_state=SectorState.NO_THEME,
            risk_state=RiskState.NEUTRAL,
            composite_regime=CompositeRegime.BALANCED_ROTATION,
            trend_score=50.0,
            breadth_score=50.0,
            sentiment_score=50.0,
            style_score=50.0,
            sector_score=50.0,
            risk_score=50.0,
            regime_score=50.0,
            key_evidence=["分类失败，使用默认状态"],
            counter_evidence=[],
            confidence=max(0.1, 0.5 - 0.15 * len(missing_data)),
            risk_flags=[],
            missing_data=list(missing_data),
        )

    # ------------------------------------------------------------------
    # Step 5: Markdown Rendering
    # ------------------------------------------------------------------

    def _render_markdown(self, report: DiagnosticReport) -> str:
        """Render the diagnostic report as Markdown string."""
        lines = []

        # Header
        lines.append(f"# {report.date} 大盘全维度诊断\n")

        # One-sentence summary
        lines.append(f"## 一句话结论\n")
        lines.append(f"{report.one_sentence_summary}\n")

        # State dashboard
        lines.append(f"## 状态仪表盘\n")
        lines.append(f"| 维度 | 状态 | 得分 |\n")
        lines.append(f"|------|------|------|\n")
        lines.append(f"| 趋势 | {report.trend_state} | {report.trend_score:.0f} |\n")
        lines.append(f"| 广度 | {report.breadth_state} | {report.breadth_score:.0f} |\n")
        lines.append(f"| 情绪 | {report.sentiment_state} | {report.sentiment_score:.0f} |\n")
        lines.append(f"| 风格 | {report.style_state} | - |\n")
        lines.append(f"| 板块 | {report.sector_state} | - |\n")
        lines.append(f"| 风险 | {report.risk_state} | {report.risk_score:.0f} |\n")
        lines.append(f"\n综合 Regime: **{report.composite_regime}** (得分 {report.regime_score:.1f})\n")

        # Risk flags
        if report.risk_flags:
            lines.append(f"## 风险警报\n")
            for flag in report.risk_flags:
                desc = RISK_FLAG_DESCRIPTIONS.get(flag, flag)
                lines.append(f"- **{flag}**: {desc}\n")

        # Evidence section
        lines.append(f"\n## 证据与置信度\n")
        lines.append(f"**支持证据**:\n")
        for i, evidence in enumerate(report.key_evidence, 1):
            lines.append(f"{i}. {evidence}\n")

        if report.counter_evidence:
            lines.append(f"\n**反向证据**:\n")
            for i, evidence in enumerate(report.counter_evidence, 1):
                lines.append(f"{i}. {evidence}\n")

        lines.append(f"\n置信度: {report.confidence:.0%}\n")

        # Strategy mapping
        if report.strategy_mapping:
            lines.append(f"\n## 策略映射建议\n")
            for group in report.strategy_mapping:
                lines.append(f"- {group}\n")

        # Missing data
        if report.missing_data:
            lines.append(f"\n## 数据缺失\n")
            for item in report.missing_data:
                lines.append(f"- {item}\n")

        return "".join(lines)
