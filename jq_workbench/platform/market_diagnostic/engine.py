"""
Market Diagnostic Engine - Main Entry Point

Orchestrates the full diagnostic pipeline:
1. Data fetching (indices, breadth, sentiment, sector, capital, risk)
2. Feature computation (trend, breadth, sentiment, style, sector, capital, risk)
3. State classification (MarketStateClassifier)
4. Report construction (DiagnosticReport)
5. Markdown rendering (optional LLM narrative)

Usage:
    engine = MarketDiagnosticEngine(data_manager=data_manager)
    report, markdown = engine.run(date="2024-01-15")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
from datetime import datetime

from .states.enums import (
    CompositeRegime,
    TrendState,
    BreadthState,
    SentimentState,
    StyleState,
    SectorState,
    RiskState,
    REGIME_STRATEGY_MAPPING,
)
from .states.classifier import MarketStateClassifier, MarketStateResult
from .reports.schema import DiagnosticReport

logger = logging.getLogger(__name__)


class MarketDiagnosticEngine:
    """
    Main diagnostic engine coordinating data -> features -> states -> report.

    Args:
        data_manager: DataFetcherManager instance for data retrieval
        analyzer: Optional LLM analyzer for narrative generation
        enable_llm_narrative: Whether to generate LLM narrative (default: True)
    """

    def __init__(
        self,
        data_manager: Any = None,
        analyzer: Any = None,
        enable_llm_narrative: bool = True,
    ):
        self.data_manager = data_manager
        self.analyzer = analyzer
        self.enable_llm_narrative = enable_llm_narrative
        self.classifier = MarketStateClassifier()
        self._prev_breadth_ratio: Optional[float] = None  # For breadth collapse detection

    def run(self, date: Optional[str] = None) -> Tuple[DiagnosticReport, str]:
        """
        Run full diagnostic pipeline for a trading date.

        Args:
            date: Trading date string (YYYY-MM-DD). Defaults to today.

        Returns:
            Tuple of (DiagnosticReport, markdown_str)

        Raises:
            Exception: Propagates data/processing errors with descriptive messages
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"Starting market diagnostic for {date}")

        try:
            # Step 1: Fetch data
            data = self._fetch_data(date)
            missing_data = data.get("missing_data", [])

            # Step 2: Compute features
            features = self._compute_features(data, date)

            # Step 3: Classify states
            state_result = self.classifier.classify(
                date=date,
                trend_features=features["trend"],
                breadth_features=features["breadth"],
                sentiment_features=features["sentiment"],
                style_features=features["style"],
                sector_features=features["sector"],
                capital_features=features["capital"],
                risk_features=features["risk"],
                prev_breadth_ratio=self._prev_breadth_ratio,
            )
            state_result.missing_data = missing_data

            # Update previous breadth ratio for next run
            self._prev_breadth_ratio = features["breadth"].above_ma20_ratio

            # Step 4: Build DiagnosticReport
            report = self._build_report(date, state_result, features, data)

            # Step 5: Render Markdown
            markdown = self._render_markdown(report)

            logger.info(f"Diagnostic complete for {date}: regime={state_result.composite_regime.value}")
            return report, markdown

        except Exception as e:
            logger.error(f"Diagnostic failed for {date}: {e}", exc_info=True)
            raise

    # -------------------------------------------------------------------------
    # Step 1: Data Fetching
    # -------------------------------------------------------------------------

    def _fetch_data(self, date: str) -> Dict[str, Any]:
        """
        Fetch all required data for diagnostic.

        Returns:
            Dict with keys: index_data, breadth_data, sector_data, capital_data, missing_data
        """
        result = {
            "index_data": {},
            "breadth_data": None,
            "sector_data": [],
            "capital_data": None,
            "sentiment_data": None,
            "missing_data": [],
        }

        # Fetch index data
        result["index_data"] = self._fetch_index_data(date)

        # Fetch market breadth data
        result["breadth_data"] = self._fetch_breadth_data(date)

        # Fetch sector data
        result["sector_data"] = self._fetch_sector_data(date)

        # Fetch capital flow data
        result["capital_data"] = self._fetch_capital_data(date)

        # Fetch sentiment data (embedded in breadth for simplicity)
        result["sentiment_data"] = result["breadth_data"]

        return result

    def _fetch_index_data(self, date: str) -> Dict[str, Any]:
        """Fetch index daily data for core indices."""
        INDEX_POOL = {
            "sh000001": "上证指数",
            "sz399001": "深证成指",
            "sz399006": "创业板指",
            "sh000688": "科创50",
            "sh000016": "上证50",
            "sh000300": "沪深300",
            "sh000905": "中证500",
            "sh000852": "中证1000",
        }

        if self.data_manager is None:
            logger.warning("No data_manager, using mock index data")
            return self._mock_index_data(date, INDEX_POOL)

        try:
            indices_data = {}
            for code, name in INDEX_POOL.items():
                try:
                    if hasattr(self.data_manager, "get_main_indices"):
                        data = self.data_manager.get_main_indices(code=code, end_date=date)
                    elif hasattr(self.data_manager, "get_index_daily"):
                        data = self.data_manager.get_index_daily(code=code, end_date=date)
                    else:
                        data = None

                    if data is not None:
                        indices_data[code] = {
                            "code": code,
                            "name": name,
                            "date": date,
                            "close": getattr(data, "close", 0),
                            "open": getattr(data, "open", 0),
                            "high": getattr(data, "high", 0),
                            "low": getattr(data, "low", 0),
                            "volume": getattr(data, "volume", 0),
                            "amount": getattr(data, "amount", 0),
                            "change_pct": getattr(data, "change_pct", 0),
                            "close_series": getattr(data, "close_series", []),
                        }
                    else:
                        indices_data[code] = self._mock_single_index_data(code, name, date)
                except Exception as e:
                    logger.warning(f"Failed to fetch index {code}: {e}")
                    indices_data[code] = self._mock_single_index_data(code, name, date)
            return indices_data
        except Exception as e:
            logger.warning(f"Index data fetch failed: {e}, using mock data")
            return self._mock_index_data(date, INDEX_POOL)

    def _fetch_breadth_data(self, date: str) -> Optional[Any]:
        """Fetch market breadth data."""
        if self.data_manager is None:
            return self._mock_breadth_data(date)

        try:
            if hasattr(self.data_manager, "get_market_stats"):
                data = self.data_manager.get_market_stats(date=date)
            else:
                data = None

            if data is not None:
                return data
        except Exception as e:
            logger.warning(f"Breadth data fetch failed: {e}")

        return self._mock_breadth_data(date)

    def _fetch_sector_data(self, date: str) -> List[Any]:
        """Fetch sector data for Shenwan Level-1 industries."""
        if self.data_manager is None:
            return self._mock_sector_data(date)

        try:
            if hasattr(self.data_manager, "get_sector_rankings"):
                data = self.data_manager.get_sector_rankings(date=date)
                if data:
                    return data
        except Exception as e:
            logger.warning(f"Sector data fetch failed: {e}")

        return self._mock_sector_data(date)

    def _fetch_capital_data(self, date: str) -> Optional[Any]:
        """Fetch capital flow data."""
        if self.data_manager is None:
            return self._mock_capital_data(date)

        try:
            if hasattr(self.data_manager, "get_capital_flow"):
                data = self.data_manager.get_capital_flow(date=date)
                if data:
                    return data
        except Exception as e:
            logger.warning(f"Capital data fetch failed: {e}")

        return self._mock_capital_data(date)

    # -------------------------------------------------------------------------
    # Step 2: Feature Computation
    # -------------------------------------------------------------------------

    def _compute_features(self, data: Dict[str, Any], date: str) -> Dict[str, Any]:
        """
        Compute all feature vectors from raw data.

        Returns:
            Dict with keys: trend, breadth, sentiment, style, sector, capital, risk
        """
        features = {}

        # Trend features
        features["trend"] = self._compute_trend_features(data["index_data"])

        # Breadth features
        if data["breadth_data"]:
            features["breadth"] = self._compute_breadth_features(data["breadth_data"])
        else:
            features["breadth"] = self._default_breadth_features()

        # Sentiment features
        if data["sentiment_data"]:
            features["sentiment"] = self._compute_sentiment_features(data["sentiment_data"])
        else:
            features["sentiment"] = self._default_sentiment_features()

        # Style features
        features["style"] = self._compute_style_features(data["index_data"])

        # Sector features
        features["sector"] = self._compute_sector_features(data["sector_data"])

        # Capital features
        if data["capital_data"]:
            features["capital"] = self._compute_capital_features(data["capital_data"])
        else:
            features["capital"] = self._default_capital_features()

        # Risk features
        features["risk"] = self._compute_risk_features(
            data["index_data"], features["breadth"], features["sector"]
        )

        return features

    def _compute_trend_features(self, index_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute trend features for all indices using numpy."""
        import numpy as np
        from .states.classifier import TrendFeatures

        result = {}
        for code, d in index_data.items():
            close_series = d.get("close_series", [])
            if not close_series or len(close_series) < 60:
                close = d.get("close", 0)
                close_series = [close] * 60

            closes = np.array(close_series[-60:], dtype=float)

            ma5 = float(np.mean(closes[-5:]))
            ma10 = float(np.mean(closes[-10:]))
            ma20 = float(np.mean(closes[-20:]))
            ma60 = float(np.mean(closes[-60:])) if len(closes) >= 60 else ma20
            ma120 = float(np.mean(closes[-120:])) if len(closes) >= 120 else ma60

            if ma5 > ma10 > ma20 > ma60:
                ma_alignment = "多头排列"
            elif ma5 < ma10 < ma20 < ma60:
                ma_alignment = "空头排列"
            else:
                ma_alignment = "缠绕"

            ema12 = _ema(closes, 12)
            ema26 = _ema(closes, 26)
            dif = ema12 - ema26
            dea_vals = np.array([dif])
            dea = _ema(dea_vals, 9)
            macd_bar = 2 * (dif - dea)

            if dif > dea and dif > 0:
                macd_signal = "金叉"
            elif dif < dea and dif < 0:
                macd_signal = "死叉"
            else:
                macd_signal = "中性"

            close = closes[-1]
            bias_ma5 = (close - ma5) / ma5 if ma5 != 0 else 0
            bias_ma20 = (close - ma20) / ma20 if ma20 != 0 else 0
            bias_ma60 = (close - ma60) / ma60 if ma60 != 0 else 0

            rsrs_score = max(0, min(1, 0.5 + bias_ma20 * 5))
            near_high_20d = close >= max(closes[-20:]) * 0.98
            break_support = close < ma60
            atr_20 = _atr(closes, 20)

            result[code] = TrendFeatures(
                code=code,
                ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60, ma120=ma120,
                ma_alignment=ma_alignment,
                bias_ma5=bias_ma5, bias_ma20=bias_ma20, bias_ma60=bias_ma60,
                macd_dif=dif, macd_dea=dea, macd_bar=macd_bar,
                macd_signal=macd_signal,
                atr_20=atr_20,
                rsrs_score=rsrs_score,
                near_high_20d=near_high_20d,
                break_support=break_support,
                rs_vs_300=0.0,
            )

        return result

    def _compute_breadth_features(self, data: Any) -> Any:
        """Compute breadth features from market breadth data."""
        from .states.classifier import BreadthFeatures

        up_count = getattr(data, "up_count", 0)
        down_count = getattr(data, "down_count", 0)
        flat_count = getattr(data, "flat_count", 0)
        total = up_count + down_count + flat_count
        if total == 0:
            total = 1

        up_down_ratio = up_count / total if total > 0 else 0.5
        limit_up = getattr(data, "limit_up_count", 0)
        limit_up_rate = limit_up / total if total > 0 else 0.0
        seal_rate = getattr(data, "seal_rate", 0.5)
        above_ma20_ratio = getattr(data, "above_ma20_ratio", 0.4)
        new_high_ratio = getattr(data, "new_high_ratio", 0.05)
        amount = getattr(data, "total_amount", 0)
        amount_ma5 = getattr(data, "amount_ma5", amount)

        amount_dev_5d = (amount - amount_ma5) / amount_ma5 if amount_ma5 != 0 else 0

        breadth_score = (
            up_down_ratio * 30 +
            above_ma20_ratio * 40 +
            min(limit_up_rate * 500, 20) +
            min(new_high_ratio * 200, 10)
        )

        return BreadthFeatures(
            up_down_ratio=up_down_ratio,
            limit_up_rate=limit_up_rate,
            seal_rate=seal_rate,
            above_ma20_ratio=above_ma20_ratio,
            new_high_ratio=new_high_ratio,
            amount_deviation_5d=amount_dev_5d,
            amount_deviation_20d=0.0,
            breadth_score=breadth_score,
        )

    def _compute_sentiment_features(self, data: Any) -> Any:
        """Compute sentiment features."""
        from .states.classifier import SentimentFeatures

        limit_up = getattr(data, "limit_up_count", 0)
        limit_down = getattr(data, "limit_down_count", 0)
        total = limit_up + limit_down
        if total == 0:
            total = 1

        limit_up_rate = limit_up / total
        limit_down_rate = limit_down / total
        seal_rate = getattr(data, "seal_rate", 0.5)
        continuous = getattr(data, "continuous_limit_up", 0)
        next_day_premium = 0.0

        sentiment_score = (
            limit_up_rate * 40 +
            seal_rate * 30 +
            min(continuous / 10, 1.0) * 15 +
            0.15
        )

        return SentimentFeatures(
            limit_up_rate=limit_up_rate,
            limit_down_rate=limit_down_rate,
            seal_rate=seal_rate,
            continuous_limit_up=continuous,
            next_day_premium=next_day_premium,
            sentiment_score=sentiment_score,
        )

    def _compute_style_features(self, index_data: Dict[str, Any]) -> Any:
        """Compute style features from index relative strength."""
        from .states.classifier import StyleFeatures

        rs = {"rs_50_growth": 0.5, "rs_300_1000": 0.5, "rs_500_1000": 0.5}
        pairs = [
            ("sh000016", "sz399006", "rs_50_growth"),
            ("sh000300", "sh000852", "rs_300_1000"),
            ("sh000905", "sh000852", "rs_500_1000"),
        ]
        for code_a, code_b, key in pairs:
            data_a = index_data.get(code_a, {})
            data_b = index_data.get(code_b, {})
            close_a = data_a.get("close", 0)
            close_b = data_b.get("close", 0)
            if close_a > 0 and close_b > 0:
                rs[key] = close_b / close_a if close_a != 0 else 0.5

        return StyleFeatures(
            rs_50_growth=rs["rs_50_growth"],
            rs_300_1000=rs["rs_300_1000"],
            rs_500_1000=rs["rs_500_1000"],
            style_score=50.0,
        )

    def _compute_sector_features(self, sector_data: List) -> List:
        """Compute sector features from sector data."""
        from .states.classifier import SectorFeatureResult

        if not sector_data:
            return []

        results = []
        for s in sector_data:
            strength = getattr(s, "strength_score", 0.0)
            persistence = getattr(s, "persistence_score", 0.5)

            if strength > 2.0 and persistence > 0.7:
                state = "主升趋势"
            elif strength > 1.5 and 0.4 <= persistence <= 0.7:
                state = "趋势强化"
            elif -0.5 <= strength <= 1.5:
                state = "震荡整理"
            elif 0.5 <= strength <= 1.5 and getattr(s, "ret_20d", 0) < -0.10:
                state = "超跌反弹"
            else:
                state = "弱势退潮"

            results.append(SectorFeatureResult(
                industry_code=getattr(s, "industry_code", ""),
                industry_name=getattr(s, "industry_name", ""),
                strength_score=strength,
                persistence_score=persistence,
                crowding_score=getattr(s, "crowding_score", 0.0),
                leadership_score=getattr(s, "leadership_score", 0.0),
                state=state,
            ))

        return results

    def _compute_capital_features(self, data: Any) -> Any:
        """Compute capital flow features."""
        from .states.classifier import CapitalFeatures

        return CapitalFeatures(
            total_amount=getattr(data, "total_amount", 0),
            amount_deviation_5d=getattr(data, "amount_deviation_5d", 0),
            amount_deviation_20d=getattr(data, "amount_deviation_20d", 0),
            north_net_flow=getattr(data, "north_net_flow", 0),
            north_5d_avg=getattr(data, "north_5d_avg", 0),
            margin_balance=getattr(data, "margin_balance", 0),
            margin_delta=getattr(data, "margin_delta", 0),
            main_net_flow=getattr(data, "main_net_flow", 0),
            etf_net_flow=getattr(data, "etf_net_flow", 0),
        )

    def _compute_risk_features(
        self,
        index_data: Dict[str, Any],
        breadth_features: Any,
        sector_features: List,
    ) -> Any:
        """Compute risk features and detect risk flags."""
        from .states.classifier import RiskFeatures
        import numpy as np

        f300_data = index_data.get("sh000300", {})
        close_series = f300_data.get("close_series", [])

        realized_vol = 0.15
        max_drawdown = 0.05

        if len(close_series) >= 20:
            closes = np.array(close_series[-20:], dtype=float)
            returns = np.diff(closes) / closes[:-1]
            realized_vol = float(np.std(returns) * np.sqrt(252))
            peak = np.maximum.accumulate(closes)
            drawdown = (closes - peak) / peak
            max_drawdown = float(np.min(drawdown))

        vol_spike_detected = realized_vol > 0.30

        sector_overcrowded = False
        if sector_features:
            top_amount_share = max(getattr(s, "amount_share", 0) for s in sector_features)
            sector_overcrowded = top_amount_share > 0.25

        close = f300_data.get("close", 0)
        ma60_proxy = close_series[-60] if len(close_series) >= 60 else close
        index_broke_support = close < ma60_proxy * 0.95

        return RiskFeatures(
            realized_vol=realized_vol,
            atr_vol=realized_vol * 1.2,
            vol_ratio=1.5,
            max_drawdown=abs(max_drawdown),
            cross_asset_corr=0.5,
            sector_corr_elevation=0.1,
            vol_spike_detected=vol_spike_detected,
            sector_overcrowded=sector_overcrowded,
            north_outflow_3d=False,
            leadership_breakdown=False,
            index_broke_support=index_broke_support,
            risk_score=0.0,
        )

    # -------------------------------------------------------------------------
    # Report Building
    # -------------------------------------------------------------------------

    def _build_report(
        self,
        date: str,
        state: MarketStateResult,
        features: Dict[str, Any],
        data: Dict[str, Any],
    ) -> DiagnosticReport:
        """Build DiagnosticReport from classification results."""
        summary = self._generate_summary(state)

        strategy_mapping = []
        for group in state.strategy_groups:
            strategy_mapping.append({
                "group": group,
                "allocation": "标准配置",
                "rationale": self._strategy_rationale(state.composite_regime, group),
            })

        return DiagnosticReport(
            date=date,
            trend_state=state.trend_state.value,
            breadth_state=state.breadth_state.value,
            sentiment_state=state.sentiment_state.value,
            style_state=state.style_state.value,
            sector_state=state.sector_state.value,
            risk_state=state.risk_state.value,
            composite_regime=state.composite_regime.value,
            trend_score=state.trend_score,
            breadth_score=state.breadth_score,
            sentiment_score=state.sentiment_score,
            risk_score=state.risk_score,
            regime_score=state.regime_score,
            indices=self._build_indices_table(features["trend"], data["index_data"]),
            breadth_metrics=self._build_breadth_metrics(features["breadth"]),
            sentiment_metrics=self._build_sentiment_metrics(features["sentiment"]),
            style_metrics=self._build_style_metrics(features["style"]),
            sector_table=self._build_sector_table(features["sector"]),
            capital_metrics=self._build_capital_metrics(features["capital"]),
            risk_flags=state.risk_flags,
            one_sentence_summary=summary,
            key_evidence=state.key_evidence,
            counter_evidence=state.counter_evidence,
            strategy_mapping=strategy_mapping,
            confidence=state.confidence,
            missing_data=state.missing_data,
        )

    def _generate_summary(self, state: MarketStateResult) -> str:
        """Generate one-sentence market summary."""
        regime = state.composite_regime.value
        trend = state.trend_state.value
        breadth = state.breadth_state.value
        risk = state.risk_state.value

        summaries = {
            "trend_risk_on_growth": f"市场处于{trend}状态，成长风格主导，建议顺势而为",
            "trend_risk_on_smallcap": f"市场处于{trend}状态，小盘股活跃，可关注主题投资",
            "balanced_rotation": f"市场{trend}，{breadth}，风格轮动较快，建议均衡配置",
            "defensive_dividend": f"市场偏弱，防御风格占优，建议增加红利资产配置",
            "high_volatility_warning": f"市场风险较高({risk})，波动率显著放大，建议降仓防御",
            "panic_bottoming": f"市场极度弱势({breadth})，情绪冰点，可能处于恐慌底部区域",
            "broad_weakness_hold": f"市场趋势转弱({trend})，广度不足({breadth})，建议观望等待信号",
        }
        return summaries.get(regime, f"市场{trend}，{breadth}，{risk}")

    def _strategy_rationale(self, regime: CompositeRegime, group: str) -> str:
        """Get strategy allocation rationale."""
        rationale_map = {
            "趋势ETF组": "追踪市场趋势，适合趋势明确的行情",
            "行业轮动组": "顺应行业主线轮动，适合结构性机会",
            "小市值进攻组": "小盘股弹性大，适合市场活跃度高时配置",
            "红利价值组": "防御性配置，适合市场不确定性高时",
            "股债平衡组": "分散风险，适合震荡市和风险管理优先场景",
            "全天候组": "多资产配置，穿越周期波动",
            "高现金": "规避风险，等待更好的入场时机",
        }
        return rationale_map.get(group, "标准配置策略")

    # -------------------------------------------------------------------------
    # Markdown Rendering
    # -------------------------------------------------------------------------

    def _render_markdown(self, report: DiagnosticReport) -> str:
        """Render DiagnosticReport as Markdown string."""
        lines = []

        lines.append(f"## {report.date} 大盘全维度诊断")
        lines.append("")
        lines.append(f"### 一句话结论")
        lines.append(f"{report.one_sentence_summary}")
        lines.append("")
        lines.append(f"### 状态仪表盘")
        lines.append(f"| 维度 | 状态 | 得分 |")
        lines.append(f"|------|------|------|")
        lines.append(f"| 趋势 | {report.trend_state} | {report.trend_score:.1f} |")
        lines.append(f"| 广度 | {report.breadth_state} | {report.breadth_score:.1f} |")
        lines.append(f"| 情绪 | {report.sentiment_state} | {report.sentiment_score:.1f} |")
        lines.append(f"| 风险 | {report.risk_state} | {report.risk_score:.1f} |")
        lines.append(f"| **综合Regime** | **{report.composite_regime}** | {report.regime_score:.1f} |")
        lines.append("")

        if report.risk_flags:
            lines.append(f"### 风险警报")
            for flag in report.risk_flags:
                lines.append(f"- **{flag}**")
            lines.append("")

        lines.append(f"### 证据与置信度")
        lines.append(f"**支持证据**: {', '.join(report.key_evidence)}")
        lines.append(f"**反向证据**: {', '.join(report.counter_evidence)}")
        lines.append(f"**置信度**: {report.confidence:.0%}")
        if report.missing_data:
            lines.append(f"**缺失数据**: {', '.join(report.missing_data)}")
        lines.append("")

        if report.strategy_mapping:
            lines.append(f"### 策略映射建议")
            lines.append(f"| 策略组 | 建议配置 | 逻辑 |")
            lines.append(f"|------|------|------|")
            for s in report.strategy_mapping:
                lines.append(f"| {s['group']} | {s['allocation']} | {s['rationale']} |")
            lines.append("")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Table builders
    # -------------------------------------------------------------------------

    def _build_indices_table(self, trend_features: Dict, index_data: Dict) -> List[Dict]:
        result = []
        for code, f in trend_features.items():
            d = index_data.get(code, {})
            result.append({
                "code": code,
                "name": d.get("name", code),
                "close": d.get("close", 0),
                "change_pct": d.get("change_pct", 0),
                "ma_alignment": f.ma_alignment,
                "macd_signal": f.macd_signal,
                "rsrs_score": f.rsrs_score,
            })
        return result

    def _build_breadth_metrics(self, f: Any) -> Dict:
        return {
            "up_down_ratio": f.up_down_ratio,
            "limit_up_rate": f.limit_up_rate,
            "seal_rate": f.seal_rate,
            "above_ma20_ratio": f.above_ma20_ratio,
            "new_high_ratio": f.new_high_ratio,
            "amount_deviation_5d": f.amount_deviation_5d,
            "breadth_score": f.breadth_score,
        }

    def _build_sentiment_metrics(self, f: Any) -> Dict:
        return {
            "limit_up_rate": f.limit_up_rate,
            "limit_down_rate": f.limit_down_rate,
            "seal_rate": f.seal_rate,
            "continuous_limit_up": f.continuous_limit_up,
            "sentiment_score": f.sentiment_score,
        }

    def _build_style_metrics(self, f: Any) -> Dict:
        return {
            "rs_50_growth": f.rs_50_growth,
            "rs_300_1000": f.rs_300_1000,
            "rs_500_1000": f.rs_500_1000,
            "style_score": f.style_score,
        }

    def _build_sector_table(self, sectors: List) -> List[Dict]:
        sorted_sectors = sorted(sectors, key=lambda x: x.strength_score, reverse=True)[:10]
        return [
            {
                "industry_name": s.industry_name,
                "strength_score": s.strength_score,
                "persistence_score": s.persistence_score,
                "state": s.state,
            }
            for s in sorted_sectors
        ]

    def _build_capital_metrics(self, f: Any) -> Dict:
        return {
            "total_amount": f.total_amount,
            "amount_deviation_5d": f.amount_deviation_5d,
            "north_net_flow": f.north_net_flow,
            "north_5d_avg": f.north_5d_avg,
            "margin_balance": f.margin_balance,
            "main_net_flow": f.main_net_flow,
        }

    # -------------------------------------------------------------------------
    # Default / Mock Data
    # -------------------------------------------------------------------------

    def _default_breadth_features(self):
        from .states.classifier import BreadthFeatures
        return BreadthFeatures(0.5, 0.03, 0.6, 0.4, 0.05, 0.0, 0.0, 50.0)

    def _default_sentiment_features(self):
        from .states.classifier import SentimentFeatures
        return SentimentFeatures(0.03, 0.02, 0.6, 5, 0.0, 45.0)

    def _default_capital_features(self):
        from .states.classifier import CapitalFeatures
        return CapitalFeatures(8000, 0, 0, 0, 0, 14000, 0, 0, 0)

    def _mock_index_data(self, date: str, pool: Dict[str, str]) -> Dict[str, Any]:
        import numpy as np
        np.random.seed(hash(date) % 2**32)

        result = {}
        for code, name in pool.items():
            base = 3000 if "000" in code else 1000
            close = base + np.random.randn() * 100
            close_series = [close + np.random.randn() * 20 for _ in range(60)]
            result[code] = {
                "code": code, "name": name, "date": date,
                "close": close,
                "open": close - np.random.rand() * 20,
                "high": close + np.random.rand() * 30,
                "low": close - np.random.rand() * 30,
                "volume": np.random.rand() * 1e9,
                "amount": np.random.rand() * 1e11,
                "change_pct": np.random.randn() * 2,
                "close_series": close_series,
            }
        return result

    def _mock_single_index_data(self, code: str, name: str, date: str) -> Dict:
        import numpy as np
        np.random.seed(hash(code) % 2**32)
        close = 3000 + np.random.randn() * 200
        close_series = [close + np.random.randn() * 30 for _ in range(60)]
        return {
            "code": code, "name": name, "date": date,
            "close": close,
            "open": close - np.random.rand() * 20,
            "high": close + np.random.rand() * 30,
            "low": close - np.random.rand() * 30,
            "volume": np.random.rand() * 1e9,
            "amount": np.random.rand() * 1e11,
            "change_pct": np.random.randn() * 2,
            "close_series": close_series,
        }

    def _mock_breadth_data(self, date: str):
        import numpy as np
        np.random.seed(hash(date) % 2**32)

        class MockBreadth:
            up_count = int(1500 + np.random.randn() * 500)
            down_count = int(2500 + np.random.randn() * 500)
            flat_count = 500
            limit_up_count = int(50 + np.random.rand() * 100)
            limit_down_count = int(20 + np.random.rand() * 50)
            explode_count = 10
            seal_rate = 0.65
            continuous_limit_up = 15
            above_ma20_ratio = 0.35 + np.random.rand() * 0.30
            above_ma60_ratio = 0.30 + np.random.rand() * 0.25
            new_high_count = 30
            new_low_count = 20
            total_amount = 8000 + np.random.rand() * 3000
            amount_ma5 = 8500
            amount_ma20 = 8200

        return MockBreadth()

    def _mock_sector_data(self, date: str) -> List:
        import numpy as np
        np.random.seed(42)

        industries = [
            "电子", "计算机", "医药生物", "电力设备", "汽车",
            "食品饮料", "银行", "非银金融", "房地产", "建筑材料",
        ]

        class MockSector:
            def __init__(self, code, name):
                self.industry_code = code
                self.industry_name = name
                self.ret_1d = np.random.randn() * 0.02
                self.ret_5d = np.random.randn() * 0.05
                self.ret_20d = np.random.randn() * 0.10
                self.excess_ret_1d = np.random.randn() * 0.01
                self.breadth_20 = 0.3 + np.random.rand() * 0.4
                self.new_high_ratio = 0.05 + np.random.rand() * 0.10
                self.amount = 500 + np.random.rand() * 2000
                self.amount_share = 0.03 + np.random.rand() * 0.08
                self.amount_share_delta = np.random.randn() * 0.01
                self.limit_up_count = int(np.random.rand() * 10)
                self.turnover = np.random.rand() * 5
                self.strength_score = np.random.randn() * 1.5
                self.persistence_score = np.random.rand()
                self.crowding_score = np.random.rand()
                self.leadership_score = np.random.rand()

        return [MockSector(f"sw_{i:02d}", name) for i, name in enumerate(industries)]

    def _mock_capital_data(self, date: str):
        import numpy as np
        np.random.seed(hash(date) % 2**32)

        class MockCapital:
            north_net_flow = np.random.randn() * 50
            north_5d_avg = np.random.randn() * 30
            margin_balance = 14000 + np.random.randn() * 500
            margin_delta = np.random.randn() * 100
            main_net_flow = np.random.randn() * 200
            etf_net_flow = np.random.randn() * 100

        return MockCapital()


# -------------------------------------------------------------------------
# Technical Indicator Helpers
# -------------------------------------------------------------------------

def _ema(series: np.ndarray, period: int) -> float:
    """Compute EMA for a period."""
    if len(series) < period:
        return float(np.mean(series))
    alpha = 2 / (period + 1)
    ema = series[0]
    for v in series[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return float(ema)


def _atr(closes: np.ndarray, period: int) -> float:
    """Compute ATR (Average True Range)."""
    import numpy as np
    if len(closes) < period + 1:
        return float(np.std(closes) * np.sqrt(252))
    tr = np.abs(np.diff(closes))
    return float(np.mean(tr[-period:]))
