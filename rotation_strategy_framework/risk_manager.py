# -*- coding: utf-8 -*-
"""
风控系统: 多层风控体系、实时监控、动态仓位调整、熔断机制、风险预算分配

核心类:
- RiskLimits: 风险限制 (max_drawdown, max_single_loss, max_portfolio_vol, max_correlation, max_turnover, circuit_breaker_threshold)
- RiskMetrics: 风险指标 (current_dd, portfolio_vol, var_95, max_single_exposure, correlation_break, drawdown_duration)
- RiskMonitor: 风险监控器 (实时计算风险指标，触发警报)
- RiskController: 风控控制器 (根据风险水平调整仓位，熔断)
- CircuitBreaker: 熔断器 (分级熔断: 警告/减仓/清仓)

风控层级:
1. 策略级: 单策略止损、动量变化检查、波动率过滤
2. 组合级: 组合回撤、VaR、风险贡献、相关性突变
3. 系统级: 市场极端行情、流动性枯竭、系统性风险

熔断分级:
- Level 0 (正常): 无限制
- Level 1 (警告): 回撤>5%，发送警报
- Level 2 (减仓): 回撤>10%，仓位降至50%
- Level 3 (清仓): 回撤>15%，全部清仓
- Level 4 (熔断): 回撤>20%，停止交易N天
"""

import logging
import datetime
import math
from typing import Optional, Dict, List, Tuple, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
from copy import deepcopy

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# 熔断等级枚举
# ---------------------------------------------------------------------------
class CircuitBreakerLevel(Enum):
    """熔断等级"""

    NORMAL = 0  # 正常，无限制
    WARNING = 1  # 警告，发送警报
    REDUCE = 2  # 减仓，仓位降至50%
    LIQUIDATE = 3  # 清仓，全部清仓
    HALT = 4  # 熔断，停止交易N天


class RiskLayer(Enum):
    """风控层级"""

    STRATEGY = "strategy"  # 策略级
    PORTFOLIO = "portfolio"  # 组合级
    SYSTEM = "system"  # 系统级


class RiskAlertLevel(Enum):
    """警报等级"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


# ---------------------------------------------------------------------------
# RiskLimits: 风险限制
# ---------------------------------------------------------------------------
@dataclass
class RiskLimits:
    """
    风险限制配置

    Attributes:
        max_drawdown: 最大允许回撤 (小数，如 0.20 表示 20%)
        max_single_loss: 单策略最大亏损 (小数)
        max_portfolio_vol: 组合最大年化波动率 (小数)
        max_correlation: 策略间最大允许相关性 (小数)
        max_turnover: 最大日换手率 (小数)
        circuit_breaker_threshold: 熔断触发阈值 (小数，回撤超过此值触发熔断)
        max_single_exposure: 单策略最大暴露 (占总组合比例)
        max_var_95: 最大允许 VaR(95%) (小数)
        max_drawdown_duration: 最大回撤持续天数
        min_liquidity_score: 最低流动性评分 (0-100)
        volatility_filter_threshold: 波动率过滤阈值 (日波动率)
        momentum_change_threshold: 动量变化阈值 (绝对值)
        strategy_stop_loss: 策略级止损线 (小数)
        portfolio_stop_loss: 组合级止损线 (小数)
        halt_days: 熔断后停止交易天数
        risk_budget_per_strategy: 单策略最大风险贡献比例
        max_sector_concentration: 最大行业集中度
    """

    max_drawdown: float = 0.20
    max_single_loss: float = 0.08
    max_portfolio_vol: float = 0.25
    max_correlation: float = 0.80
    max_turnover: float = 0.50
    circuit_breaker_threshold: float = 0.15
    max_single_exposure: float = 0.30
    max_var_95: float = 0.03
    max_drawdown_duration: int = 60
    min_liquidity_score: float = 30.0
    volatility_filter_threshold: float = 0.03
    momentum_change_threshold: float = 0.10
    strategy_stop_loss: float = 0.10
    portfolio_stop_loss: float = 0.15
    halt_days: int = 5
    risk_budget_per_strategy: float = 0.25
    max_sector_concentration: float = 0.40

    def __post_init__(self):
        if not (0 < self.max_drawdown <= 1):
            raise ValueError("max_drawdown 必须在 (0, 1] 范围内")
        if not (0 < self.max_single_loss <= 1):
            raise ValueError("max_single_loss 必须在 (0, 1] 范围内")
        if self.max_portfolio_vol <= 0:
            raise ValueError("max_portfolio_vol 必须 > 0")
        if not (0 < self.max_correlation <= 1):
            raise ValueError("max_correlation 必须在 (0, 1] 范围内")
        if self.max_turnover < 0:
            raise ValueError("max_turnover 不能为负")
        if self.circuit_breaker_threshold <= 0:
            raise ValueError("circuit_breaker_threshold 必须 > 0")
        if self.halt_days < 0:
            raise ValueError("halt_days 不能为负")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RiskLimits":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return (
            f"RiskLimits(max_dd={self.max_drawdown:.0%}, "
            f"circuit_breaker={self.circuit_breaker_threshold:.0%}, "
            f"max_vol={self.max_portfolio_vol:.0%})"
        )


# ---------------------------------------------------------------------------
# RiskMetrics: 风险指标
# ---------------------------------------------------------------------------
@dataclass
class RiskMetrics:
    """
    风险指标快照

    Attributes:
        current_dd: 当前回撤 (小数)
        portfolio_vol: 组合年化波动率 (小数)
        var_95: VaR(95%) (小数)
        max_single_exposure: 最大单策略暴露 (小数)
        correlation_break: 相关性突破标志 (True 表示有策略间相关性超过限制)
        drawdown_duration: 当前回撤持续天数
        strategy_metrics: 各策略风险指标 {strategy_name: {dd, loss, vol, exposure}}
        turnover: 当前换手率 (小数)
        liquidity_score: 流动性评分 (0-100)
        momentum_changes: 动量变化 {strategy_name: change}
        circuit_breaker_level: 当前熔断等级
        risk_contributions: 各策略风险贡献 {strategy_name: contribution}
        timestamp: 指标计算时间
        layer_violations: 各层级违规 {RiskLayer: [violation_descriptions]}
    """

    current_dd: float = 0.0
    portfolio_vol: float = 0.0
    var_95: float = 0.0
    max_single_exposure: float = 0.0
    correlation_break: bool = False
    drawdown_duration: int = 0
    strategy_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    turnover: float = 0.0
    liquidity_score: float = 100.0
    momentum_changes: Dict[str, float] = field(default_factory=dict)
    circuit_breaker_level: CircuitBreakerLevel = CircuitBreakerLevel.NORMAL
    risk_contributions: Dict[str, float] = field(default_factory=dict)
    timestamp: Optional[datetime.datetime] = None
    layer_violations: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["circuit_breaker_level"] = self.circuit_breaker_level.value
        if self.timestamp:
            d["timestamp"] = self.timestamp.isoformat()
        return d

    def is_healthy(self) -> bool:
        """检查是否所有指标正常"""
        return self.circuit_breaker_level == CircuitBreakerLevel.NORMAL

    def summary(self) -> str:
        """生成风险指标摘要"""
        return (
            f"RiskMetrics(dd={self.current_dd:.2%}, vol={self.portfolio_vol:.2%}, "
            f"var95={self.var_95:.2%}, exposure={self.max_single_exposure:.2%}, "
            f"dd_duration={self.drawdown_duration}d, "
            f"cb_level={self.circuit_breaker_level.name})"
        )

    def __repr__(self) -> str:
        return self.summary()


# ---------------------------------------------------------------------------
# RiskAlert: 风险警报
# ---------------------------------------------------------------------------
@dataclass
class RiskAlert:
    """
    风险警报记录

    Attributes:
        timestamp: 警报时间
        level: 警报等级
        layer: 风控层级
        message: 警报消息
        metric_name: 触发警报的指标名称
        metric_value: 触发值
        threshold: 阈值
        action_taken: 已采取的行动
    """

    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    level: RiskAlertLevel = RiskAlertLevel.INFO
    layer: RiskLayer = RiskLayer.STRATEGY
    message: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    action_taken: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "layer": self.layer.value,
            "message": self.message,
            "metric_name": self.metric_name,
            "metric_value": round(self.metric_value, 6),
            "threshold": round(self.threshold, 6),
            "action_taken": self.action_taken,
        }

    def __repr__(self) -> str:
        return (
            f"RiskAlert({self.level.value}, {self.layer.value}, "
            f"{self.metric_name}={self.metric_value:.4f} > {self.threshold:.4f})"
        )


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def calculate_var(
    returns: Union[np.ndarray, List[float], pd.Series], confidence: float = 0.95
) -> float:
    """
    计算历史 VaR

    Args:
        returns: 收益率序列
        confidence: 置信水平

    Returns:
        VaR 值 (正数表示最大可能损失)
    """
    if isinstance(returns, pd.Series):
        arr = returns.dropna().values
    else:
        arr = np.array(returns, dtype=float)

    if len(arr) < 10:
        return 0.0

    alpha = 1 - confidence
    return float(-np.percentile(arr, alpha * 100))


def calculate_expected_shortfall(
    returns: Union[np.ndarray, List[float], pd.Series], confidence: float = 0.95
) -> float:
    """
    计算预期亏损 (CVaR / ES)

    Args:
        returns: 收益率序列
        confidence: 置信水平

    Returns:
        CVaR 值
    """
    if isinstance(returns, pd.Series):
        arr = returns.dropna().values
    else:
        arr = np.array(returns, dtype=float)

    if len(arr) < 10:
        return 0.0

    var = calculate_var(arr, confidence)
    tail = arr[arr <= -var]
    if len(tail) == 0:
        return var
    return float(-np.mean(tail))


def calculate_max_drawdown(
    equity_curve: Union[np.ndarray, List[float], pd.Series],
) -> Tuple[float, int, int]:
    """
    计算最大回撤

    Args:
        equity_curve: 净值曲线

    Returns:
        (max_drawdown, peak_index, trough_index)
    """
    if isinstance(equity_curve, pd.Series):
        arr = equity_curve.dropna().values
    else:
        arr = np.array(equity_curve, dtype=float)

    if len(arr) < 2:
        return 0.0, 0, 0

    running_max = np.maximum.accumulate(arr)
    drawdown = (arr - running_max) / running_max
    max_dd_idx = int(np.argmin(drawdown))
    max_dd = float(-drawdown[max_dd_idx])

    peak_idx = int(np.argmax(arr[: max_dd_idx + 1]))

    return max_dd, peak_idx, max_dd_idx


def calculate_drawdown_duration(
    equity_curve: Union[np.ndarray, List[float], pd.Series],
) -> int:
    """
    计算当前回撤持续天数

    Args:
        equity_curve: 净值曲线

    Returns:
        回撤持续天数
    """
    if isinstance(equity_curve, pd.Series):
        arr = equity_curve.dropna().values
    else:
        arr = np.array(equity_curve, dtype=float)

    if len(arr) < 2:
        return 0

    running_max = np.maximum.accumulate(arr)
    in_drawdown = arr < running_max

    if not in_drawdown[-1]:
        return 0

    duration = 0
    for i in range(len(arr) - 1, -1, -1):
        if in_drawdown[i]:
            duration += 1
        else:
            break

    return duration


def calculate_portfolio_volatility(
    weights: np.ndarray, cov_matrix: np.ndarray, annualize: bool = True
) -> float:
    """
    计算组合波动率

    Args:
        weights: 权重向量
        cov_matrix: 协方差矩阵
        annualize: 是否年化

    Returns:
        组合波动率
    """
    vol = float(np.sqrt(np.dot(weights, np.dot(cov_matrix, weights))))
    if annualize:
        vol *= math.sqrt(TRADING_DAYS_PER_YEAR)
    return vol


def calculate_risk_contribution(
    weights: np.ndarray, cov_matrix: np.ndarray
) -> np.ndarray:
    """
    计算各资产的风险贡献

    Args:
        weights: 权重向量
        cov_matrix: 协方差矩阵

    Returns:
        各资产风险贡献向量
    """
    marginal_risk = np.dot(cov_matrix, weights)
    rc = weights * marginal_risk
    total_rc = rc.sum()
    if total_rc > 1e-12:
        rc = rc / total_rc
    return rc


def calculate_correlation_break(
    current_corr: np.ndarray, historical_avg_corr: np.ndarray, threshold: float
) -> Tuple[bool, List[Tuple[int, int]]]:
    """
    检测相关性突破

    Args:
        current_corr: 当前相关性矩阵
        historical_avg_corr: 历史平均相关性矩阵
        threshold: 突破阈值 (绝对变化)

    Returns:
        (has_break, broken_pairs)
    """
    n = current_corr.shape[0]
    broken_pairs = []
    has_break = False

    for i in range(n):
        for j in range(i + 1, n):
            change = abs(current_corr[i, j] - historical_avg_corr[i, j])
            if change > threshold:
                has_break = True
                broken_pairs.append((i, j))

    return has_break, broken_pairs


# ---------------------------------------------------------------------------
# RiskMonitor: 风险监控器
# ---------------------------------------------------------------------------
class RiskMonitor:
    """
    实时风险监控器

    每个交易日检查风险指标，触发警报。
    支持三层风控体系: 策略级、组合级、系统级。

    Attributes:
        limits: 风险限制配置
        alerts: 历史警报列表
        metrics_history: 历史风险指标快照
        correlation_history: 相关性历史 (用于检测突变)
    """

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.alerts: List[RiskAlert] = []
        self.metrics_history: List[Dict[str, Any]] = []
        self.correlation_history: deque = deque(maxlen=60)
        self._peak_equity = 0.0
        self._dd_start_date: Optional[datetime.date] = None
        self._last_check_date: Optional[datetime.date] = None

    def check_risk(self, portfolio_state: Dict[str, Any]) -> RiskMetrics:
        """
        全面检查风险指标

        Args:
            portfolio_state: 组合状态，包含:
                - equity_curve: 净值序列 (pd.Series 或 list)
                - returns: 日收益率序列 (pd.Series 或 list)
                - positions: 当前仓位 {strategy_name: {weight, value, returns, ...}}
                - strategy_returns: 各策略收益率 {name: pd.Series}
                - correlation_matrix: 当前策略相关性矩阵 (可选)
                - market_state: 市场状态 {volatility, liquidity_score, ...} (可选)
                - date: 当前日期 (可选)

        Returns:
            RiskMetrics
        """
        current_date = portfolio_state.get("date")
        if current_date is None:
            current_date = datetime.date.today()
        elif isinstance(current_date, (pd.Timestamp, datetime.datetime)):
            current_date = current_date.date()

        equity_curve = portfolio_state.get("equity_curve", [])
        returns = portfolio_state.get("returns", [])
        positions = portfolio_state.get("positions", {})
        strategy_returns = portfolio_state.get("strategy_returns", {})
        corr_matrix = portfolio_state.get("correlation_matrix")
        market_state = portfolio_state.get("market_state", {})

        metrics = RiskMetrics(timestamp=datetime.datetime.now())

        self._update_peak_and_dd(equity_curve, current_date)

        metrics.current_dd = self._calc_current_drawdown(equity_curve)
        metrics.drawdown_duration = calculate_drawdown_duration(equity_curve)

        metrics.portfolio_vol = self._calc_portfolio_vol(returns)
        metrics.var_95 = self._calc_var(returns)
        metrics.max_single_exposure = self._calc_max_exposure(positions)
        metrics.turnover = portfolio_state.get("turnover", 0.0)
        metrics.liquidity_score = market_state.get("liquidity_score", 100.0)

        self._calc_strategy_metrics(positions, strategy_returns, metrics)
        self._calc_risk_contributions(positions, portfolio_state, metrics)
        self._check_correlation_break(corr_matrix, metrics)
        self._check_momentum_changes(strategy_returns, metrics)

        metrics.circuit_breaker_level = self._determine_circuit_breaker_level(metrics)

        violations = self._check_all_layers(metrics, positions, market_state)
        metrics.layer_violations = violations

        self._generate_alerts(metrics)

        self.metrics_history.append(
            {
                "date": current_date.isoformat() if current_date else None,
                "metrics": metrics.to_dict(),
            }
        )
        self._last_check_date = current_date

        return metrics

    def _update_peak_and_dd(
        self, equity_curve: Any, current_date: datetime.date
    ) -> None:
        if isinstance(equity_curve, pd.Series):
            vals = equity_curve.dropna().values
        elif isinstance(equity_curve, (list, np.ndarray)):
            vals = np.array(equity_curve, dtype=float)
        else:
            return

        if len(vals) == 0:
            return

        current_equity = vals[-1]
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
            self._dd_start_date = current_date

    def _calc_current_drawdown(self, equity_curve: Any) -> float:
        if isinstance(equity_curve, pd.Series):
            vals = equity_curve.dropna().values
        elif isinstance(equity_curve, (list, np.ndarray)):
            vals = np.array(equity_curve, dtype=float)
        else:
            return 0.0

        if len(vals) == 0 or self._peak_equity <= 0:
            return 0.0

        current = vals[-1]
        dd = (self._peak_equity - current) / self._peak_equity
        return max(0.0, float(dd))

    def _calc_portfolio_vol(self, returns: Any) -> float:
        if isinstance(returns, pd.Series):
            arr = returns.dropna().values
        elif isinstance(returns, (list, np.ndarray)):
            arr = np.array(returns, dtype=float)
        else:
            return 0.0

        if len(arr) < 10:
            return 0.0

        return float(np.std(arr, ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))

    def _calc_var(self, returns: Any, confidence: float = 0.95) -> float:
        if isinstance(returns, pd.Series):
            arr = returns.dropna().values
        elif isinstance(returns, (list, np.ndarray)):
            arr = np.array(returns, dtype=float)
        else:
            return 0.0

        return calculate_var(arr, confidence)

    def _calc_max_exposure(self, positions: Dict[str, Any]) -> float:
        if not positions:
            return 0.0

        max_exp = 0.0
        for name, pos in positions.items():
            weight = pos.get("weight", 0.0)
            max_exp = max(max_exp, abs(weight))

        return max_exp

    def _calc_strategy_metrics(
        self,
        positions: Dict[str, Any],
        strategy_returns: Dict[str, Any],
        metrics: RiskMetrics,
    ) -> None:
        for name, pos in positions.items():
            sm = {}
            sm["weight"] = pos.get("weight", 0.0)
            sm["value"] = pos.get("value", 0.0)

            entry_price = pos.get("entry_price", 0.0)
            current_price = pos.get("current_price", 0.0)
            if entry_price > 0:
                sm["pnl_pct"] = (current_price - entry_price) / entry_price
            else:
                sm["pnl_pct"] = pos.get("pnl_pct", 0.0)

            if name in strategy_returns:
                rets = strategy_returns[name]
                if isinstance(rets, pd.Series):
                    rets = rets.dropna().values[-60:]
                if len(rets) >= 10:
                    sm["vol"] = float(
                        np.std(rets, ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)
                    )
                else:
                    sm["vol"] = 0.0
            else:
                sm["vol"] = 0.0

            metrics.strategy_metrics[name] = sm

    def _calc_risk_contributions(
        self,
        positions: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        metrics: RiskMetrics,
    ) -> None:
        cov_matrix = portfolio_state.get("cov_matrix")
        if cov_matrix is None:
            return

        strategy_names = list(positions.keys())
        if len(strategy_names) < 2:
            for name in strategy_names:
                metrics.risk_contributions[name] = 1.0
            return

        try:
            if isinstance(cov_matrix, pd.DataFrame):
                cov = np.array(
                    [
                        [cov_matrix.loc[i, j] for j in strategy_names]
                        for i in strategy_names
                    ]
                )
            else:
                cov = np.array(cov_matrix)

            weights = np.array(
                [positions.get(s, {}).get("weight", 0.0) for s in strategy_names]
            )
            rc = calculate_risk_contribution(weights, cov)

            for i, name in enumerate(strategy_names):
                metrics.risk_contributions[name] = float(rc[i])
        except Exception:
            pass

    def _check_correlation_break(
        self, corr_matrix: Optional[Any], metrics: RiskMetrics
    ) -> None:
        if corr_matrix is None:
            return

        try:
            if isinstance(corr_matrix, pd.DataFrame):
                current = corr_matrix.values
            else:
                current = np.array(corr_matrix)

            self.correlation_history.append(current.copy())

            if len(self.correlation_history) >= 20:
                hist_avg = np.mean(list(self.correlation_history)[:-1], axis=0)
                has_break, _ = calculate_correlation_break(current, hist_avg, 0.15)
                metrics.correlation_break = has_break
        except Exception:
            pass

    def _check_momentum_changes(
        self,
        strategy_returns: Dict[str, Any],
        metrics: RiskMetrics,
    ) -> None:
        threshold = self.limits.momentum_change_threshold

        for name, rets in strategy_returns.items():
            try:
                if isinstance(rets, pd.Series):
                    arr = rets.dropna().values
                else:
                    arr = np.array(rets, dtype=float)

                if len(arr) < 40:
                    continue

                recent = arr[-20:]
                prior = arr[-40:-20]

                recent_mean = np.mean(recent)
                prior_mean = np.mean(prior)

                if abs(prior_mean) > 1e-8:
                    change = abs(recent_mean - prior_mean) / abs(prior_mean)
                else:
                    change = abs(recent_mean - prior_mean)

                metrics.momentum_changes[name] = float(change)
            except Exception:
                metrics.momentum_changes[name] = 0.0

    def _determine_circuit_breaker_level(
        self, metrics: RiskMetrics
    ) -> CircuitBreakerLevel:
        dd = metrics.current_dd

        if dd > self.limits.max_drawdown:
            return CircuitBreakerLevel.HALT
        elif dd > self.limits.circuit_breaker_threshold:
            return CircuitBreakerLevel.LIQUIDATE
        elif dd > 0.10:
            return CircuitBreakerLevel.REDUCE
        elif dd > 0.05:
            return CircuitBreakerLevel.WARNING
        else:
            return CircuitBreakerLevel.NORMAL

    def _check_all_layers(
        self,
        metrics: RiskMetrics,
        positions: Dict[str, Any],
        market_state: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        violations: Dict[str, List[str]] = {
            RiskLayer.STRATEGY.value: [],
            RiskLayer.PORTFOLIO.value: [],
            RiskLayer.SYSTEM.value: [],
        }

        self._check_strategy_layer(
            metrics, positions, violations[RiskLayer.STRATEGY.value]
        )
        self._check_portfolio_layer(metrics, violations[RiskLayer.PORTFOLIO.value])
        self._check_system_layer(
            metrics, market_state, violations[RiskLayer.SYSTEM.value]
        )

        return violations

    def _check_strategy_layer(
        self,
        metrics: RiskMetrics,
        positions: Dict[str, Any],
        violations: List[str],
    ) -> None:
        for name, sm in metrics.strategy_metrics.items():
            pnl = sm.get("pnl_pct", 0.0)
            if pnl < -self.limits.strategy_stop_loss:
                violations.append(
                    f"策略 {name} 触发止损: {pnl:.2%} < -{self.limits.strategy_stop_loss:.0%}"
                )

            vol = sm.get("vol", 0.0)
            if vol > self.limits.volatility_filter_threshold * math.sqrt(
                TRADING_DAYS_PER_YEAR
            ):
                violations.append(f"策略 {name} 波动率过高: {vol:.2%}")

            mc = metrics.momentum_changes.get(name, 0.0)
            if mc > self.limits.momentum_change_threshold:
                violations.append(f"策略 {name} 动量变化过大: {mc:.2%}")

    def _check_portfolio_layer(
        self, metrics: RiskMetrics, violations: List[str]
    ) -> None:
        if metrics.current_dd > self.limits.max_drawdown:
            violations.append(
                f"组合回撤超限: {metrics.current_dd:.2%} > {self.limits.max_drawdown:.0%}"
            )

        if metrics.portfolio_vol > self.limits.max_portfolio_vol:
            violations.append(
                f"组合波动率超限: {metrics.portfolio_vol:.2%} > {self.limits.max_portfolio_vol:.0%}"
            )

        if metrics.var_95 > self.limits.max_var_95:
            violations.append(
                f"VaR(95%) 超限: {metrics.var_95:.2%} > {self.limits.max_var_95:.0%}"
            )

        if metrics.max_single_exposure > self.limits.max_single_exposure:
            violations.append(
                f"单策略暴露超限: {metrics.max_single_exposure:.2%} > {self.limits.max_single_exposure:.0%}"
            )

        if metrics.correlation_break:
            violations.append("策略间相关性发生突变")

        if metrics.drawdown_duration > self.limits.max_drawdown_duration:
            violations.append(
                f"回撤持续时间超限: {metrics.drawdown_duration}d > {self.limits.max_drawdown_duration}d"
            )

        for name, rc in metrics.risk_contributions.items():
            if rc > self.limits.risk_budget_per_strategy:
                violations.append(
                    f"策略 {name} 风险贡献超限: {rc:.2%} > {self.limits.risk_budget_per_strategy:.0%}"
                )

    def _check_system_layer(
        self,
        metrics: RiskMetrics,
        market_state: Dict[str, Any],
        violations: List[str],
    ) -> None:
        market_vol = market_state.get("market_volatility", 0.0)
        if market_vol > 0.04:
            violations.append(f"市场波动率极端: {market_vol:.2%}")

        liquidity = metrics.liquidity_score
        if liquidity < self.limits.min_liquidity_score:
            violations.append(
                f"流动性枯竭: 评分 {liquidity:.0f} < {self.limits.min_liquidity_score:.0f}"
            )

        market_stress = market_state.get("stress_indicator", 0.0)
        if market_stress > 0.8:
            violations.append(f"系统性风险指标异常: {market_stress:.2f}")

        vix = market_state.get("vix", 0.0)
        if vix > 40:
            violations.append(f"VIX 极端行情: {vix:.1f}")

    def _generate_alerts(self, metrics: RiskMetrics) -> None:
        if metrics.circuit_breaker_level == CircuitBreakerLevel.WARNING:
            self.alerts.append(
                RiskAlert(
                    level=RiskAlertLevel.WARNING,
                    layer=RiskLayer.PORTFOLIO,
                    message=f"组合回撤 {metrics.current_dd:.2%} 触发警告",
                    metric_name="current_dd",
                    metric_value=metrics.current_dd,
                    threshold=0.05,
                    action_taken="发送警报",
                )
            )
        elif metrics.circuit_breaker_level == CircuitBreakerLevel.REDUCE:
            self.alerts.append(
                RiskAlert(
                    level=RiskAlertLevel.CRITICAL,
                    layer=RiskLayer.PORTFOLIO,
                    message=f"组合回撤 {metrics.current_dd:.2%} 触发减仓",
                    metric_name="current_dd",
                    metric_value=metrics.current_dd,
                    threshold=0.10,
                    action_taken="仓位降至50%",
                )
            )
        elif metrics.circuit_breaker_level == CircuitBreakerLevel.LIQUIDATE:
            self.alerts.append(
                RiskAlert(
                    level=RiskAlertLevel.EMERGENCY,
                    layer=RiskLayer.PORTFOLIO,
                    message=f"组合回撤 {metrics.current_dd:.2%} 触发清仓",
                    metric_name="current_dd",
                    metric_value=metrics.current_dd,
                    threshold=self.limits.circuit_breaker_threshold,
                    action_taken="全部清仓",
                )
            )
        elif metrics.circuit_breaker_level == CircuitBreakerLevel.HALT:
            self.alerts.append(
                RiskAlert(
                    level=RiskAlertLevel.EMERGENCY,
                    layer=RiskLayer.SYSTEM,
                    message=f"组合回撤 {metrics.current_dd:.2%} 触发熔断",
                    metric_name="current_dd",
                    metric_value=metrics.current_dd,
                    threshold=self.limits.max_drawdown,
                    action_taken=f"停止交易 {self.limits.halt_days} 天",
                )
            )

        for layer_name, layer_violations in metrics.layer_violations.items():
            for violation in layer_violations:
                self.alerts.append(
                    RiskAlert(
                        level=RiskAlertLevel.WARNING,
                        layer=RiskLayer(layer_name),
                        message=violation,
                    )
                )

    def get_alerts(
        self,
        since: Optional[datetime.datetime] = None,
        level: Optional[RiskAlertLevel] = None,
        layer: Optional[RiskLayer] = None,
    ) -> List[RiskAlert]:
        """
        查询历史警报

        Args:
            since: 起始时间
            level: 警报等级过滤
            layer: 风控层级过滤

        Returns:
            符合条件的警报列表
        """
        results = self.alerts
        if since:
            results = [a for a in results if a.timestamp >= since]
        if level:
            results = [a for a in results if a.level == level]
        if layer:
            results = [a for a in results if a.layer == layer]
        return results

    def get_latest_metrics(self) -> Optional[RiskMetrics]:
        """获取最新一次风险指标"""
        if not self.metrics_history:
            return None
        latest = self.metrics_history[-1]
        d = latest["metrics"]
        d["circuit_breaker_level"] = CircuitBreakerLevel(d["circuit_breaker_level"])
        if d.get("timestamp"):
            d["timestamp"] = datetime.datetime.fromisoformat(d["timestamp"])
        return RiskMetrics(
            **{k: v for k, v in d.items() if k in RiskMetrics.__dataclass_fields__}
        )

    def reset(self) -> None:
        """重置监控状态"""
        self._peak_equity = 0.0
        self._dd_start_date = None
        self.correlation_history.clear()


# ---------------------------------------------------------------------------
# CircuitBreaker: 熔断器
# ---------------------------------------------------------------------------
class CircuitBreaker:
    """
    分级熔断器

    Level 0 (正常): 无限制
    Level 1 (警告): 回撤>5%，发送警报
    Level 2 (减仓): 回撤>10%，仓位降至50%
    Level 3 (清仓): 回撤>15%，全部清仓
    Level 4 (熔断): 回撤>20%，停止交易N天

    Attributes:
        limits: 风险限制
        current_level: 当前熔断等级
        halt_until: 熔断解除日期
        history: 熔断历史
    """

    THRESHOLDS = {
        CircuitBreakerLevel.NORMAL: 0.0,
        CircuitBreakerLevel.WARNING: 0.05,
        CircuitBreakerLevel.REDUCE: 0.10,
        CircuitBreakerLevel.LIQUIDATE: 0.15,
        CircuitBreakerLevel.HALT: 0.20,
    }

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.current_level = CircuitBreakerLevel.NORMAL
        self.halt_until: Optional[datetime.date] = None
        self.history: List[Dict[str, Any]] = []
        self._level_changes: List[
            Tuple[datetime.datetime, CircuitBreakerLevel, str]
        ] = []

    def check(
        self,
        current_drawdown: float,
        current_date: Optional[datetime.date] = None,
        additional_signals: Optional[Dict[str, float]] = None,
    ) -> Tuple[CircuitBreakerLevel, str]:
        """
        检查熔断状态

        Args:
            current_drawdown: 当前回撤
            current_date: 当前日期
            additional_signals: 额外信号 {signal_name: value}

        Returns:
            (熔断等级, 行动描述)
        """
        if current_date is None:
            current_date = datetime.date.today()

        if self.current_level == CircuitBreakerLevel.HALT:
            if self.halt_until and current_date < self.halt_until:
                remaining = (self.halt_until - current_date).days
                return (
                    CircuitBreakerLevel.HALT,
                    f"熔断中，剩余 {remaining} 天",
                )
            else:
                self._record_level_change(
                    CircuitBreakerLevel.HALT,
                    CircuitBreakerLevel.NORMAL,
                    current_date,
                    "熔断期结束",
                )
                self.current_level = CircuitBreakerLevel.NORMAL
                self.halt_until = None

        level = self._evaluate_level(current_drawdown, additional_signals)

        if level != self.current_level:
            action = self._get_action_description(level)
            self._record_level_change(self.current_level, level, current_date, action)
            self.current_level = level

            if level == CircuitBreakerLevel.HALT:
                self.halt_until = current_date + datetime.timedelta(
                    days=self.limits.halt_days
                )

            self.history.append(
                {
                    "date": current_date.isoformat(),
                    "from_level": self._level_changes[-2][1].name
                    if len(self._level_changes) >= 2
                    else "N/A",
                    "to_level": level.name,
                    "drawdown": current_drawdown,
                    "action": action,
                }
            )

            return level, action

        return level, "no change"

    def _evaluate_level(
        self,
        drawdown: float,
        additional_signals: Optional[Dict[str, float]] = None,
    ) -> CircuitBreakerLevel:
        cb_threshold = self.limits.circuit_breaker_threshold
        max_dd = self.limits.max_drawdown

        thresholds = {
            CircuitBreakerLevel.HALT: max_dd,
            CircuitBreakerLevel.LIQUIDATE: cb_threshold,
            CircuitBreakerLevel.REDUCE: 0.10,
            CircuitBreakerLevel.WARNING: 0.05,
        }

        for level, threshold in sorted(
            thresholds.items(), key=lambda x: x[1], reverse=True
        ):
            if drawdown >= threshold:
                return level

        if additional_signals:
            stress = additional_signals.get("market_stress", 0.0)
            if stress > 0.9:
                return CircuitBreakerLevel.LIQUIDATE
            elif stress > 0.7:
                return CircuitBreakerLevel.REDUCE

        return CircuitBreakerLevel.NORMAL

    def _get_action_description(self, level: CircuitBreakerLevel) -> str:
        actions = {
            CircuitBreakerLevel.NORMAL: "恢复正常交易",
            CircuitBreakerLevel.WARNING: "发送风险警报，加强监控",
            CircuitBreakerLevel.REDUCE: "仓位降至50%，关闭新开仓",
            CircuitBreakerLevel.LIQUIDATE: "全部清仓，停止所有策略",
            CircuitBreakerLevel.HALT: f"触发熔断，停止交易 {self.limits.halt_days} 天",
        }
        return actions.get(level, "未知行动")

    def _record_level_change(
        self,
        from_level: CircuitBreakerLevel,
        to_level: CircuitBreakerLevel,
        date: datetime.date,
        action: str,
    ) -> None:
        self._level_changes.append((datetime.datetime.now(), to_level, action))
        logger.warning(
            f"CircuitBreaker: {from_level.name} -> {to_level.name} | {action}"
        )

    def is_trading_allowed(
        self, current_date: Optional[datetime.date] = None
    ) -> Tuple[bool, str]:
        """
        检查是否允许交易

        Args:
            current_date: 当前日期

        Returns:
            (是否允许, 原因)
        """
        if current_date is None:
            current_date = datetime.date.today()

        if self.current_level == CircuitBreakerLevel.HALT:
            if self.halt_until and current_date < self.halt_until:
                remaining = (self.halt_until - current_date).days
                return False, f"熔断中，剩余 {remaining} 天"
            else:
                self.current_level = CircuitBreakerLevel.NORMAL
                self.halt_until = None
                return True, "熔断期结束"

        if self.current_level == CircuitBreakerLevel.LIQUIDATE:
            return False, "已清仓，需手动恢复"

        if self.current_level == CircuitBreakerLevel.REDUCE:
            return True, "减仓模式，允许交易但仓位受限"

        return True, "正常交易"

    def get_position_scale(self) -> float:
        """
        获取当前仓位缩放因子

        Returns:
            缩放因子 (0.0 - 1.0)
        """
        scales = {
            CircuitBreakerLevel.NORMAL: 1.0,
            CircuitBreakerLevel.WARNING: 1.0,
            CircuitBreakerLevel.REDUCE: 0.5,
            CircuitBreakerLevel.LIQUIDATE: 0.0,
            CircuitBreakerLevel.HALT: 0.0,
        }
        return scales.get(self.current_level, 0.0)

    def reset(self) -> None:
        """重置熔断器"""
        self.current_level = CircuitBreakerLevel.NORMAL
        self.halt_until = None
        self._level_changes.clear()

    def get_history(self) -> List[Dict[str, Any]]:
        """获取熔断历史"""
        return self.history.copy()


# ---------------------------------------------------------------------------
# RiskController: 风控控制器
# ---------------------------------------------------------------------------
class RiskController:
    """
    风控控制器

    根据风险水平调整仓位，执行熔断。
    整合 RiskMonitor 和 CircuitBreaker，提供统一的风控接口。

    Attributes:
        limits: 风险限制
        monitor: 风险监控器
        breaker: 熔断器
        position_history: 仓位调整历史
    """

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.monitor = RiskMonitor(self.limits)
        self.breaker = CircuitBreaker(self.limits)
        self.position_history: List[Dict[str, Any]] = []

    def check_risk(self, portfolio_state: Dict[str, Any]) -> RiskMetrics:
        """
        检查风险并返回指标

        Args:
            portfolio_state: 组合状态

        Returns:
            RiskMetrics
        """
        return self.monitor.check_risk(portfolio_state)

    def apply_risk_limits(
        self,
        positions: Dict[str, Dict[str, Any]],
        risk_metrics: RiskMetrics,
    ) -> Dict[str, Dict[str, Any]]:
        """
        根据风险水平调整仓位

        Args:
            positions: 当前仓位 {strategy_name: {weight, value, ...}}
            risk_metrics: 风险指标

        Returns:
            调整后的仓位
        """
        adjusted = deepcopy(positions)

        scale = self.breaker.get_position_scale()

        if scale < 1.0:
            for name in adjusted:
                if "weight" in adjusted[name]:
                    adjusted[name]["weight"] *= scale
                    adjusted[name]["_risk_scaled"] = True
                    adjusted[name]["_scale_factor"] = scale

        adjusted = self._enforce_single_exposure(adjusted)
        adjusted = self._enforce_strategy_stop_loss(adjusted, risk_metrics)
        adjusted = self._enforce_volatility_filter(adjusted, risk_metrics)
        adjusted = self._normalize_weights(adjusted)

        self.position_history.append(
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "circuit_breaker_level": self.breaker.current_level.name,
                "scale_factor": scale,
                "positions_before": {
                    n: p.get("weight", 0.0) for n, p in positions.items()
                },
                "positions_after": {
                    n: p.get("weight", 0.0) for n, p in adjusted.items()
                },
            }
        )

        return adjusted

    def circuit_breaker_check(
        self,
        metrics: Optional[RiskMetrics] = None,
        current_drawdown: Optional[float] = None,
        current_date: Optional[datetime.date] = None,
        additional_signals: Optional[Dict[str, float]] = None,
    ) -> Tuple[CircuitBreakerLevel, str]:
        """
        执行熔断检查

        Args:
            metrics: 风险指标 (如果提供，使用 metrics.current_dd)
            current_drawdown: 当前回撤 (如果 metrics 未提供)
            current_date: 当前日期
            additional_signals: 额外信号

        Returns:
            (熔断等级, 行动描述)
        """
        if metrics is not None:
            dd = metrics.current_dd
        elif current_drawdown is not None:
            dd = current_drawdown
        else:
            dd = 0.0

        return self.breaker.check(dd, current_date, additional_signals)

    def risk_budget_allocation(
        self,
        strategies: List[Dict[str, Any]],
        risk_limits: Optional[RiskLimits] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        风险预算分配

        根据策略风险特征分配风险预算，确保每个策略的风险贡献在限制内。

        Args:
            strategies: 策略列表，每个策略包含:
                - name: 策略名称
                - expected_return: 预期年化收益
                - volatility: 年化波动率
                - sharpe: 夏普比率 (可选)
                - max_weight: 最大权重 (可选)
            risk_limits: 风险限制 (覆盖全局配置)

        Returns:
            {strategy_name: {risk_budget, weight, risk_contribution}}
        """
        limits = risk_limits or self.limits
        n = len(strategies)

        if n == 0:
            return {}

        if n == 1:
            name = strategies[0]["name"]
            return {
                name: {
                    "risk_budget": 1.0,
                    "weight": 1.0,
                    "risk_contribution": 1.0,
                }
            }

        vols = []
        sharpe = []
        names = []
        max_weights = []

        for s in strategies:
            vols.append(s.get("volatility", 0.15))
            sharpe.append(s.get("sharpe", 0.0))
            names.append(s["name"])
            max_weights.append(s.get("max_weight", limits.max_single_exposure))

        vols = np.array(vols, dtype=float)
        sharpe = np.array(sharpe, dtype=float)
        max_weights = np.array(max_weights, dtype=float)

        vols = np.clip(vols, 1e-6, None)

        inv_vol = 1.0 / vols
        inv_vol_weights = inv_vol / inv_vol.sum()

        quality = np.clip(sharpe, 0, None)
        if quality.sum() > 1e-12:
            quality_weights = quality / quality.sum()
        else:
            quality_weights = np.ones(n) / n

        blended = 0.5 * inv_vol_weights + 0.5 * quality_weights

        blended = np.clip(blended, 0.01, max_weights)
        total = blended.sum()
        if total > 1e-12:
            blended = blended / total

        rc = self._approximate_risk_contribution(blended, vols)

        max_rc = limits.risk_budget_per_strategy
        if rc.max() > max_rc:
            blended = self._rebalance_risk_budget(blended, vols, max_rc)
            rc = self._approximate_risk_contribution(blended, vols)

        result = {}
        for i, name in enumerate(names):
            result[name] = {
                "risk_budget": float(rc[i]),
                "weight": float(blended[i]),
                "risk_contribution": float(rc[i]),
                "volatility": float(vols[i]),
                "sharpe": float(sharpe[i]),
            }

        return result

    def _approximate_risk_contribution(
        self, weights: np.ndarray, vols: np.ndarray
    ) -> np.ndarray:
        """近似风险贡献"""
        rc = weights * vols
        total = rc.sum()
        if total > 1e-12:
            rc = rc / total
        return rc

    def _rebalance_risk_budget(
        self, weights: np.ndarray, vols: np.ndarray, max_rc: float
    ) -> np.ndarray:
        """重新平衡风险预算，确保不超过上限"""
        n = len(weights)
        rc = self._approximate_risk_contribution(weights, vols)

        for _ in range(20):
            excess = rc - max_rc
            if excess.max() <= 0:
                break

            excess_idx = np.where(excess > 0)[0]
            deficit_idx = np.where(excess <= 0)[0]

            total_excess = excess[excess_idx].sum()
            if total_excess <= 0 or len(deficit_idx) == 0:
                break

            for idx in excess_idx:
                reduction = excess[idx] * 0.5
                weights[idx] *= 1 - reduction

            total_deficit_weight = weights[deficit_idx].sum()
            if total_deficit_weight > 1e-12:
                for idx in deficit_idx:
                    weights[idx] += total_excess * (weights[idx] / total_deficit_weight)

            weights = np.clip(weights, 0.01, None)
            total = weights.sum()
            if total > 1e-12:
                weights = weights / total

            rc = self._approximate_risk_contribution(weights, vols)

        return weights

    def _enforce_single_exposure(
        self, positions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """强制执行单策略暴露限制"""
        adjusted = deepcopy(positions)

        for name, pos in adjusted.items():
            weight = pos.get("weight", 0.0)
            if abs(weight) > self.limits.max_single_exposure:
                sign = 1 if weight > 0 else -1
                adjusted[name]["weight"] = sign * self.limits.max_single_exposure
                adjusted[name]["_capped"] = True

        return adjusted

    def _enforce_strategy_stop_loss(
        self,
        positions: Dict[str, Dict[str, Any]],
        risk_metrics: RiskMetrics,
    ) -> Dict[str, Dict[str, Any]]:
        """强制执行策略止损"""
        adjusted = deepcopy(positions)

        for name, pos in adjusted.items():
            sm = risk_metrics.strategy_metrics.get(name, {})
            pnl = sm.get("pnl_pct", 0.0)

            if pnl < -self.limits.strategy_stop_loss:
                adjusted[name]["weight"] = 0.0
                adjusted[name]["_stopped_out"] = True
                adjusted[name]["_stop_reason"] = (
                    f"pnl={pnl:.2%} < -{self.limits.strategy_stop_loss:.0%}"
                )

        return adjusted

    def _enforce_volatility_filter(
        self,
        positions: Dict[str, Dict[str, Any]],
        risk_metrics: RiskMetrics,
    ) -> Dict[str, Dict[str, Any]]:
        """波动率过滤"""
        adjusted = deepcopy(positions)
        max_vol = self.limits.volatility_filter_threshold * math.sqrt(
            TRADING_DAYS_PER_YEAR
        )

        for name, pos in adjusted.items():
            sm = risk_metrics.strategy_metrics.get(name, {})
            vol = sm.get("vol", 0.0)

            if vol > max_vol:
                reduction = max_vol / vol
                adjusted[name]["weight"] *= reduction
                adjusted[name]["_vol_reduced"] = True

        return adjusted

    def _normalize_weights(
        self, positions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """归一化权重"""
        total = sum(p.get("weight", 0.0) for p in positions.values())

        if abs(total) < 1e-12:
            return positions

        if abs(total - 1.0) > 1e-6:
            for pos in positions.values():
                pos["weight"] /= total

        return positions

    def is_trading_allowed(
        self, current_date: Optional[datetime.date] = None
    ) -> Tuple[bool, str]:
        """
        检查是否允许交易

        Args:
            current_date: 当前日期

        Returns:
            (是否允许, 原因)
        """
        return self.breaker.is_trading_allowed(current_date)

    def get_position_scale(self) -> float:
        """获取当前仓位缩放因子"""
        return self.breaker.get_position_scale()

    def get_risk_report(self, portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成完整风控报告

        Args:
            portfolio_state: 组合状态

        Returns:
            风控报告字典
        """
        metrics = self.check_risk(portfolio_state)
        cb_level, cb_action = self.circuit_breaker_check(metrics)
        trading_allowed, ta_reason = self.is_trading_allowed()

        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "risk_metrics": metrics.to_dict(),
            "circuit_breaker": {
                "level": cb_level.name,
                "action": cb_action,
                "position_scale": self.get_position_scale(),
                "halt_until": self.breaker.halt_until.isoformat()
                if self.breaker.halt_until
                else None,
            },
            "trading_allowed": trading_allowed,
            "trading_reason": ta_reason,
            "layer_violations": metrics.layer_violations,
            "recent_alerts": [a.to_dict() for a in self.monitor.get_alerts()[-10:]],
            "position_scale": self.get_position_scale(),
        }

    def reset(self) -> None:
        """重置风控系统"""
        self.monitor.reset()
        self.breaker.reset()
        self.position_history.clear()
