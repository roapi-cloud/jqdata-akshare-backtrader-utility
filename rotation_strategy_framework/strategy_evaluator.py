# -*- coding: utf-8 -*-
"""
策略评估器: 多维度策略评分、排名、稳定性评估、容量评估、相关性分析、动态权重分配

核心类:
- EvaluationMetrics: 评估指标 (sharpe, sortino, calmar, max_dd, win_rate, profit_factor, avg_trade, consistency)
- StrategyScore: 策略评分 (overall, return_score, risk_score, stability_score, capacity_score)
- StrategyRanker: 策略排名器 (综合评分、多维度排名、帕累托前沿)
- DynamicWeightAllocator: 动态权重分配 (近期表现加权、衰减因子)

评分公式:
- overall = w1*return_score + w2*risk_score + w3*stability_score + w4*capacity_score
- return_score = normalize(sharpe) * 0.4 + normalize(calmar) * 0.3 + normalize(total_return) * 0.3
- risk_score = (1 - normalize(max_dd)) * 0.5 + normalize(sortino) * 0.5
- stability_score = consistency_score (Walk-Forward 胜率)
- capacity_score = min(1, log(capital) / log(max_capacity))
"""

import logging
import math
from typing import Optional, Dict, List, Tuple, Any, Union
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest_engine import BacktestResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
TRADING_DAYS_PER_YEAR = 252
DEFAULT_SCORE_WEIGHTS = {
    "return": 0.35,
    "risk": 0.25,
    "stability": 0.25,
    "capacity": 0.15,
}
DEFAULT_RETURN_SUB_WEIGHTS = {
    "sharpe": 0.4,
    "calmar": 0.3,
    "total_return": 0.3,
}
DEFAULT_RISK_SUB_WEIGHTS = {
    "max_dd": 0.5,
    "sortino": 0.5,
}
DEFAULT_DECAY_FACTOR = 0.9
DEFAULT_HALF_LIFE = 60


# ---------------------------------------------------------------------------
# EvaluationMetrics: 评估指标
# ---------------------------------------------------------------------------
@dataclass
class EvaluationMetrics:
    """
    策略评估指标集合

    Attributes:
        sharpe: 夏普比率
        sortino: 索提诺比率
        calmar: 卡玛比率
        max_dd: 最大回撤 (正数表示回撤幅度)
        win_rate: 胜率
        profit_factor: 盈亏比
        avg_trade: 平均交易收益
        total_return: 总收益率
        annual_return: 年化收益率
        annual_volatility: 年化波动率
        consistency: Walk-Forward 一致性得分 (0~1)
        total_trades: 总交易次数
        avg_holding_period: 平均持仓天数
        tail_risk: 尾部风险 (CVaR 95%)
        skewness: 收益率偏度
        kurtosis: 收益率峰度
        recovery_factor: 恢复因子 (total_return / max_dd)
    """

    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    max_dd: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    annual_volatility: float = 0.0
    consistency: float = 0.0
    total_trades: int = 0
    avg_holding_period: float = 0.0
    tail_risk: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    recovery_factor: float = 0.0

    @classmethod
    def from_backtest_result(cls, result: BacktestResult) -> "EvaluationMetrics":
        """
        从 BacktestResult 构建评估指标

        Args:
            result: 回测结果

        Returns:
            EvaluationMetrics
        """
        total_return = result.total_return
        max_dd = abs(result.max_drawdown) if result.max_drawdown else 0.0

        sharpe = result.sharpe_ratio if result.sharpe_ratio else 0.0
        sortino = result.sortino_ratio if result.sortino_ratio else 0.0
        calmar = result.calmar_ratio if result.calmar_ratio else 0.0
        win_rate = result.win_rate if result.win_rate else 0.0
        profit_factor = result.profit_loss_ratio if result.profit_loss_ratio else 0.0
        avg_trade = result.avg_trade_return if result.avg_trade_return else 0.0

        recovery = total_return / max_dd if max_dd > 1e-10 else 0.0

        tail_risk = 0.0
        skewness = 0.0
        kurtosis = 0.0
        if result.returns is not None and len(result.returns) > 0:
            rets = result.returns.dropna()
            if len(rets) > 2:
                tail_risk = -rets.quantile(0.05)
                skewness = rets.skew()
                kurtosis = rets.kurtosis()

        avg_holding = 0.0
        if result.trades and len(result.trades) > 0:
            durations = []
            for t in result.trades:
                if "bar_open" in t and "bar_close" in t:
                    durations.append(t["bar_close"] - t["bar_open"])
            if durations:
                avg_holding = float(np.mean(durations))

        return cls(
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            max_dd=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade=avg_trade,
            total_return=total_return,
            annual_return=result.annual_return,
            annual_volatility=result.annual_volatility,
            consistency=0.0,
            total_trades=result.total_trades,
            avg_holding_period=avg_holding,
            tail_risk=tail_risk,
            skewness=skewness,
            kurtosis=kurtosis,
            recovery_factor=recovery,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sharpe": round(self.sharpe, 4),
            "sortino": round(self.sortino, 4),
            "calmar": round(self.calmar, 4),
            "max_dd": round(self.max_dd, 6),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "avg_trade": round(self.avg_trade, 6),
            "total_return": round(self.total_return, 6),
            "annual_return": round(self.annual_return, 6),
            "annual_volatility": round(self.annual_volatility, 6),
            "consistency": round(self.consistency, 4),
            "total_trades": self.total_trades,
            "avg_holding_period": round(self.avg_holding_period, 2),
            "tail_risk": round(self.tail_risk, 6),
            "skewness": round(self.skewness, 4),
            "kurtosis": round(self.kurtosis, 4),
            "recovery_factor": round(self.recovery_factor, 4),
        }

    def __repr__(self) -> str:
        return (
            f"EvaluationMetrics(sharpe={self.sharpe:.3f}, calmar={self.calmar:.3f}, "
            f"max_dd={self.max_dd:.2%}, win_rate={self.win_rate:.2%})"
        )


# ---------------------------------------------------------------------------
# StrategyScore: 策略评分
# ---------------------------------------------------------------------------
@dataclass
class StrategyScore:
    """
    策略多维度评分

    Attributes:
        strategy_name: 策略名称
        overall: 综合评分 (0~1)
        return_score: 收益维度评分 (0~1)
        risk_score: 风险维度评分 (0~1)
        stability_score: 稳定性评分 (0~1)
        capacity_score: 容量评分 (0~1)
        rank: 综合排名
        metrics: 底层评估指标
        details: 评分明细 (各子维度得分)
    """

    strategy_name: str = ""
    overall: float = 0.0
    return_score: float = 0.0
    risk_score: float = 0.0
    stability_score: float = 0.0
    capacity_score: float = 0.0
    rank: int = 0
    metrics: Optional[EvaluationMetrics] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "strategy_name": self.strategy_name,
            "overall": round(self.overall, 4),
            "return_score": round(self.return_score, 4),
            "risk_score": round(self.risk_score, 4),
            "stability_score": round(self.stability_score, 4),
            "capacity_score": round(self.capacity_score, 4),
            "rank": self.rank,
        }
        if self.metrics:
            d["metrics"] = self.metrics.to_dict()
        if self.details:
            d["details"] = self.details
        return d

    def __repr__(self) -> str:
        return (
            f"StrategyScore(name='{self.strategy_name}', overall={self.overall:.3f}, "
            f"rank={self.rank})"
        )


# ---------------------------------------------------------------------------
# _normalizer: 归一化工具
# ---------------------------------------------------------------------------
def _min_max_normalize(
    values: List[float],
    lower_is_better: bool = False,
    clip: bool = True,
) -> List[float]:
    """
    Min-Max 归一化到 [0, 1]

    Args:
        values: 原始值列表
        lower_is_better: True 表示值越小越好 (如 max_dd)
        clip: 是否裁剪到 [0, 1]

    Returns:
        归一化后的值列表
    """
    if not values:
        return []
    if len(values) == 1:
        return [1.0]

    arr = np.array(values, dtype=float)
    vmin, vmax = arr.min(), arr.max()
    span = vmax - vmin

    if span < 1e-12:
        return [1.0] * len(values)

    normalized = (arr - vmin) / span

    if lower_is_better:
        normalized = 1.0 - normalized

    if clip:
        normalized = np.clip(normalized, 0.0, 1.0)

    return normalized.tolist()


def _rank_normalize(values: List[float], lower_is_better: bool = False) -> List[float]:
    """
    排名归一化: 将值转换为排名百分位

    Args:
        values: 原始值列表
        lower_is_better: True 表示值越小排名越高

    Returns:
        排名百分位列表 (0~1)
    """
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [1.0]

    arr = np.array(values, dtype=float)
    if lower_is_better:
        ranks = arr.argsort().argsort()[::-1]
    else:
        ranks = arr.argsort().argsort()[::-1]

    return ((ranks + 1) / n).tolist()


# ---------------------------------------------------------------------------
# StrategyScorer: 策略评分器
# ---------------------------------------------------------------------------
class StrategyScorer:
    """
    策略评分器

    根据多维度指标计算策略综合评分

    评分公式:
    - overall = w1*return_score + w2*risk_score + w3*stability_score + w4*capacity_score
    - return_score = normalize(sharpe)*0.4 + normalize(calmar)*0.3 + normalize(total_return)*0.3
    - risk_score = (1-normalize(max_dd))*0.5 + normalize(sortino)*0.5
    - stability_score = consistency_score
    - capacity_score = min(1, log(capital)/log(max_capacity))
    """

    def __init__(
        self,
        score_weights: Optional[Dict[str, float]] = None,
        return_sub_weights: Optional[Dict[str, float]] = None,
        risk_sub_weights: Optional[Dict[str, float]] = None,
    ):
        """
        Args:
            score_weights: 四大维度权重 {return, risk, stability, capacity}
            return_sub_weights: 收益子维度权重 {sharpe, calmar, total_return}
            risk_sub_weights: 风险子维度权重 {max_dd, sortino}
        """
        self.score_weights = score_weights or DEFAULT_SCORE_WEIGHTS
        self.return_sub_weights = return_sub_weights or DEFAULT_RETURN_SUB_WEIGHTS
        self.risk_sub_weights = risk_sub_weights or DEFAULT_RISK_SUB_WEIGHTS

        self._normalize_weights()

    def _normalize_weights(self):
        total = sum(self.score_weights.values())
        if total > 0:
            self.score_weights = {k: v / total for k, v in self.score_weights.items()}

        total_ret = sum(self.return_sub_weights.values())
        if total_ret > 0:
            self.return_sub_weights = {
                k: v / total_ret for k, v in self.return_sub_weights.items()
            }

        total_risk = sum(self.risk_sub_weights.values())
        if total_risk > 0:
            self.risk_sub_weights = {
                k: v / total_risk for k, v in self.risk_sub_weights.items()
            }

    def evaluate_strategy(
        self,
        result: BacktestResult,
        walk_forward_results: Optional[List[BacktestResult]] = None,
        capital: float = 1_000_000.0,
        max_capacity: float = 100_000_000.0,
    ) -> StrategyScore:
        """
        评估单个策略

        Args:
            result: 回测结果
            walk_forward_results: Walk-Forward 验证结果列表 (用于稳定性评估)
            capital: 当前资金规模
            max_capacity: 策略最大容量

        Returns:
            StrategyScore
        """
        metrics = EvaluationMetrics.from_backtest_result(result)

        if walk_forward_results and len(walk_forward_results) > 0:
            metrics.consistency = self._compute_consistency(walk_forward_results)

        return_score = self._compute_return_score(metrics)
        risk_score = self._compute_risk_score(metrics)
        stability_score = self._compute_stability_score(metrics)
        capacity_score = self._compute_capacity_score(capital, max_capacity)

        overall = (
            self.score_weights["return"] * return_score
            + self.score_weights["risk"] * risk_score
            + self.score_weights["stability"] * stability_score
            + self.score_weights["capacity"] * capacity_score
        )

        details = {
            "return_sub_scores": {
                "sharpe_norm": self._safe_norm(metrics.sharpe),
                "calmar_norm": self._safe_norm(metrics.calmar),
                "total_return_norm": self._safe_norm(metrics.total_return),
            },
            "risk_sub_scores": {
                "max_dd_norm": 1.0 - self._safe_norm(metrics.max_dd),
                "sortino_norm": self._safe_norm(metrics.sortino),
            },
        }

        return StrategyScore(
            strategy_name=result.strategy_name,
            overall=overall,
            return_score=return_score,
            risk_score=risk_score,
            stability_score=stability_score,
            capacity_score=capacity_score,
            metrics=metrics,
            details=details,
        )

    def evaluate_batch(
        self,
        results: Dict[str, BacktestResult],
        walk_forward_map: Optional[Dict[str, List[BacktestResult]]] = None,
        capital_map: Optional[Dict[str, float]] = None,
        max_capacity_map: Optional[Dict[str, float]] = None,
    ) -> Dict[str, StrategyScore]:
        """
        批量评估策略

        Args:
            results: dict[name, BacktestResult]
            walk_forward_map: dict[name, list[BacktestResult]]
            capital_map: dict[name, capital]
            max_capacity_map: dict[name, max_capacity]

        Returns:
            dict[name, StrategyScore]
        """
        wf_map = walk_forward_map or {}
        cap_map = capital_map or {}
        max_cap_map = max_capacity_map or {}

        all_metrics = []
        for name, result in results.items():
            metrics = EvaluationMetrics.from_backtest_result(result)
            wf_results = wf_map.get(name, [])
            if wf_results:
                metrics.consistency = self._compute_consistency(wf_results)
            all_metrics.append(metrics)

        sharpe_vals = [m.sharpe for m in all_metrics]
        calmar_vals = [m.calmar for m in all_metrics]
        total_ret_vals = [m.total_return for m in all_metrics]
        max_dd_vals = [m.max_dd for m in all_metrics]
        sortino_vals = [m.sortino for m in all_metrics]

        sharpe_norm = _min_max_normalize(sharpe_vals, lower_is_better=False)
        calmar_norm = _min_max_normalize(calmar_vals, lower_is_better=False)
        total_ret_norm = _min_max_normalize(total_ret_vals, lower_is_better=False)
        max_dd_norm = _min_max_normalize(max_dd_vals, lower_is_better=True)
        sortino_norm = _min_max_normalize(sortino_vals, lower_is_better=False)

        scores = {}
        for i, (name, result) in enumerate(results.items()):
            metrics = all_metrics[i]

            rs = (
                self.return_sub_weights["sharpe"] * sharpe_norm[i]
                + self.return_sub_weights["calmar"] * calmar_norm[i]
                + self.return_sub_weights["total_return"] * total_ret_norm[i]
            )

            risk_s = (
                self.risk_sub_weights["max_dd"] * max_dd_norm[i]
                + self.risk_sub_weights["sortino"] * sortino_norm[i]
            )

            stab_s = self._compute_stability_score(metrics)

            capital = cap_map.get(name, 1_000_000.0)
            max_cap = max_cap_map.get(name, 100_000_000.0)
            cap_s = self._compute_capacity_score(capital, max_cap)

            overall = (
                self.score_weights["return"] * rs
                + self.score_weights["risk"] * risk_s
                + self.score_weights["stability"] * stab_s
                + self.score_weights["capacity"] * cap_s
            )

            scores[name] = StrategyScore(
                strategy_name=name,
                overall=overall,
                return_score=rs,
                risk_score=risk_s,
                stability_score=stab_s,
                capacity_score=cap_s,
                metrics=metrics,
                details={
                    "return_sub_scores": {
                        "sharpe_norm": sharpe_norm[i],
                        "calmar_norm": calmar_norm[i],
                        "total_return_norm": total_ret_norm[i],
                    },
                    "risk_sub_scores": {
                        "max_dd_norm": max_dd_norm[i],
                        "sortino_norm": sortino_norm[i],
                    },
                },
            )

        return scores

    @staticmethod
    def _compute_consistency(wf_results: List[BacktestResult]) -> float:
        """
        计算 Walk-Forward 一致性得分

        一致性 = 盈利窗口比例 * 收益稳定性

        Args:
            wf_results: Walk-Forward 各窗口结果

        Returns:
            一致性得分 (0~1)
        """
        if not wf_results:
            return 0.0

        valid = [r for r in wf_results if "error" not in r.metadata]
        if len(valid) < 2:
            return 0.5 if (valid and valid[0].total_return > 0) else 0.0

        returns = [r.total_return for r in valid]
        win_count = sum(1 for r in returns if r > 0)
        win_ratio = win_count / len(returns)

        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        stability = max(0, 1.0 - std_ret / (abs(mean_ret) + 1e-10))

        return 0.6 * win_ratio + 0.4 * stability

    @staticmethod
    def _compute_return_score(metrics: EvaluationMetrics) -> float:
        """计算收益维度评分 (单策略, 已归一化近似)"""
        s_sharpe = 1.0 / (1.0 + math.exp(-metrics.sharpe))
        s_calmar = 1.0 / (1.0 + math.exp(-metrics.calmar * 0.5))
        s_ret = 1.0 / (1.0 + math.exp(-metrics.total_return * 2))

        return (
            DEFAULT_RETURN_SUB_WEIGHTS["sharpe"] * s_sharpe
            + DEFAULT_RETURN_SUB_WEIGHTS["calmar"] * s_calmar
            + DEFAULT_RETURN_SUB_WEIGHTS["total_return"] * s_ret
        )

    @staticmethod
    def _compute_risk_score(metrics: EvaluationMetrics) -> float:
        """计算风险维度评分"""
        s_max_dd = 1.0 - min(1.0, metrics.max_dd * 2)
        s_sortino = 1.0 / (1.0 + math.exp(-metrics.sortino * 0.5))

        return (
            DEFAULT_RISK_SUB_WEIGHTS["max_dd"] * s_max_dd
            + DEFAULT_RISK_SUB_WEIGHTS["sortino"] * s_sortino
        )

    @staticmethod
    def _compute_stability_score(metrics: EvaluationMetrics) -> float:
        """计算稳定性评分"""
        if metrics.consistency > 0:
            return metrics.consistency

        win_rate_score = metrics.win_rate
        trade_count_score = min(1.0, metrics.total_trades / 50.0)
        vol_penalty = min(1.0, metrics.annual_volatility * 2)

        return (
            0.5 * win_rate_score + 0.3 * trade_count_score + 0.2 * (1.0 - vol_penalty)
        )

    @staticmethod
    def _compute_capacity_score(capital: float, max_capacity: float) -> float:
        """
        计算容量评分

        capacity_score = min(1, log(capital) / log(max_capacity))

        Args:
            capital: 当前资金规模
            max_capacity: 策略最大容量

        Returns:
            容量评分 (0~1)
        """
        if max_capacity <= 1 or capital <= 0:
            return 0.0
        if capital >= max_capacity:
            return 1.0
        return min(1.0, math.log(capital) / math.log(max_capacity))

    @staticmethod
    def _safe_norm(value: float) -> float:
        """Sigmoid 归一化单值"""
        return 1.0 / (1.0 + math.exp(-value))


# ---------------------------------------------------------------------------
# StrategyRanker: 策略排名器
# ---------------------------------------------------------------------------
class StrategyRanker:
    """
    策略排名器

    功能:
    - 综合评分排名
    - 多维度排名 (收益/风险/稳定性/容量)
    - 帕累托前沿识别
    """

    def rank_strategies(
        self,
        scores: Dict[str, StrategyScore],
        sort_by: str = "overall",
        ascending: bool = False,
    ) -> List[Tuple[str, StrategyScore]]:
        """
        对策略进行综合排名

        Args:
            scores: dict[name, StrategyScore]
            sort_by: 排序依据 (overall, return_score, risk_score, stability_score, capacity_score)
            ascending: 是否升序

        Returns:
            list[(name, StrategyScore)] 按排名排列
        """
        ranked = sorted(
            scores.items(),
            key=lambda x: getattr(x[1], sort_by, 0),
            reverse=not ascending,
        )

        for i, (name, score) in enumerate(ranked):
            score.rank = i + 1

        return ranked

    def rank_by_dimension(
        self,
        scores: Dict[str, StrategyScore],
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        按各维度分别排名

        Args:
            scores: dict[name, StrategyScore]

        Returns:
            dict[dimension, list[(name, score)]]
        """
        dimensions = ["return_score", "risk_score", "stability_score", "capacity_score"]
        result = {}

        for dim in dimensions:
            ranked = sorted(
                scores.items(),
                key=lambda x: getattr(x[1], dim, 0),
                reverse=True,
            )
            result[dim] = [(name, getattr(score, dim)) for name, score in ranked]

        return result

    def pareto_frontier(
        self,
        scores: Dict[str, StrategyScore],
        objectives: Optional[List[str]] = None,
    ) -> List[str]:
        """
        识别帕累托前沿策略

        帕累托最优: 不存在其他策略在所有目标维度上都优于它

        Args:
            scores: dict[name, StrategyScore]
            objectives: 目标维度列表 (默认: return_score, risk_score, stability_score)

        Returns:
            帕累托前沿策略名称列表
        """
        if objectives is None:
            objectives = ["return_score", "risk_score", "stability_score"]

        names = list(scores.keys())
        pareto = []

        for i, name_i in enumerate(names):
            score_i = scores[name_i]
            is_dominated = False

            for j, name_j in enumerate(names):
                if i == j:
                    continue
                score_j = scores[name_j]

                all_better_or_equal = True
                at_least_one_better = False

                for obj in objectives:
                    val_i = getattr(score_i, obj, 0)
                    val_j = getattr(score_j, obj, 0)
                    if val_j < val_i - 1e-10:
                        all_better_or_equal = False
                        break
                    if val_j > val_i + 1e-10:
                        at_least_one_better = True

                if all_better_or_equal and at_least_one_better:
                    is_dominated = True
                    break

            if not is_dominated:
                pareto.append(name_i)

        logger.info(f"帕累托前沿: {len(pareto)}/{len(names)} 个策略")
        return pareto

    def select_best(
        self,
        scores: Dict[str, StrategyScore],
        top_k: int = 3,
        min_score: float = 0.0,
        exclude_correlated: bool = False,
        correlation_matrix: Optional[pd.DataFrame] = None,
        corr_threshold: float = 0.7,
    ) -> List[str]:
        """
        选择最优策略

        Args:
            scores: dict[name, StrategyScore]
            top_k: 选择数量
            min_score: 最低综合评分门槛
            exclude_correlated: 是否排除高相关策略
            correlation_matrix: 策略收益相关性矩阵
            corr_threshold: 相关性阈值

        Returns:
            最优策略名称列表
        """
        ranked = self.rank_strategies(scores, sort_by="overall")

        filtered = [
            (name, score) for name, score in ranked if score.overall >= min_score
        ]

        if not filtered:
            return []

        if not exclude_correlated or correlation_matrix is None:
            return [name for name, _ in filtered[:top_k]]

        selected = []
        for name, score in filtered:
            if len(selected) >= top_k:
                break

            is_too_correlated = False
            for sel_name in selected:
                try:
                    corr = abs(correlation_matrix.loc[name, sel_name])
                    if corr > corr_threshold:
                        is_too_correlated = True
                        break
                except (KeyError, TypeError):
                    pass

            if not is_too_correlated:
                selected.append(name)

        return selected

    def summary_table(
        self,
        scores: Dict[str, StrategyScore],
    ) -> pd.DataFrame:
        """
        生成排名汇总表

        Args:
            scores: dict[name, StrategyScore]

        Returns:
            DataFrame 包含各策略评分和排名
        """
        ranked = self.rank_strategies(scores, sort_by="overall")

        rows = []
        for name, score in ranked:
            row = {
                "rank": score.rank,
                "strategy": name,
                "overall": round(score.overall, 4),
                "return_score": round(score.return_score, 4),
                "risk_score": round(score.risk_score, 4),
                "stability_score": round(score.stability_score, 4),
                "capacity_score": round(score.capacity_score, 4),
            }
            if score.metrics:
                row.update(
                    {
                        "sharpe": round(score.metrics.sharpe, 4),
                        "sortino": round(score.metrics.sortino, 4),
                        "calmar": round(score.metrics.calmar, 4),
                        "max_dd": round(score.metrics.max_dd, 4),
                        "win_rate": round(score.metrics.win_rate, 4),
                        "total_return": round(score.metrics.total_return, 4),
                    }
                )
            rows.append(row)

        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# CorrelationAnalyzer: 策略相关性分析器
# ---------------------------------------------------------------------------
class CorrelationAnalyzer:
    """
    策略相关性分析器

    功能:
    - 计算策略收益相关性矩阵
    - 识别同质化策略簇
    - 计算策略与基准的相关性
    """

    @staticmethod
    def analyze_correlation(
        results: Dict[str, BacktestResult],
        method: str = "pearson",
        min_overlap: int = 30,
    ) -> pd.DataFrame:
        """
        分析策略收益相关性

        Args:
            results: dict[name, BacktestResult]
            method: 相关性方法 (pearson, spearman, kendall)
            min_overlap: 最小重叠天数

        Returns:
            DataFrame 相关性矩阵
        """
        returns_dict = {}
        for name, result in results.items():
            if result.returns is not None and len(result.returns) > 0:
                returns_dict[name] = result.returns.dropna()

        if len(returns_dict) < 2:
            return pd.DataFrame()

        returns_df = pd.DataFrame(returns_dict)
        returns_df = returns_df.dropna(how="all")

        if len(returns_df) < min_overlap:
            logger.warning(f"重叠数据不足: {len(returns_df)} < {min_overlap}")
            return pd.DataFrame()

        corr_matrix = returns_df.corr(method=method)
        return corr_matrix

    @staticmethod
    def find_clusters(
        correlation_matrix: pd.DataFrame,
        threshold: float = 0.7,
    ) -> List[List[str]]:
        """
        识别高相关策略簇 (同质化策略)

        Args:
            correlation_matrix: 相关性矩阵
            threshold: 相关性阈值

        Returns:
            list[list[strategy_names]] 策略簇列表
        """
        if correlation_matrix.empty:
            return []

        names = list(correlation_matrix.columns)
        visited = set()
        clusters = []

        for name in names:
            if name in visited:
                continue

            cluster = [name]
            visited.add(name)

            for other in names:
                if other in visited or other == name:
                    continue
                try:
                    corr = abs(correlation_matrix.loc[name, other])
                    if corr > threshold:
                        cluster.append(other)
                        visited.add(other)
                except (KeyError, TypeError):
                    pass

            if len(cluster) > 1:
                clusters.append(cluster)

        logger.info(f"发现 {len(clusters)} 个高相关策略簇 (threshold={threshold})")
        return clusters

    @staticmethod
    def diversity_score(correlation_matrix: pd.DataFrame) -> float:
        """
        计算策略组合的多样化得分

        多样化得分 = 1 - 平均相关性 (越高越好)

        Args:
            correlation_matrix: 相关性矩阵

        Returns:
            多样化得分 (0~1)
        """
        if correlation_matrix.empty or len(correlation_matrix) < 2:
            return 1.0

        n = len(correlation_matrix)
        corr_vals = []
        for i in range(n):
            for j in range(i + 1, n):
                try:
                    corr_vals.append(abs(correlation_matrix.iloc[i, j]))
                except (KeyError, TypeError):
                    pass

        if not corr_vals:
            return 1.0

        avg_corr = np.mean(corr_vals)
        return max(0.0, 1.0 - avg_corr)

    @staticmethod
    def benchmark_correlation(
        results: Dict[str, BacktestResult],
        benchmark_returns: Optional[pd.Series] = None,
    ) -> Dict[str, float]:
        """
        计算各策略与基准的相关性

        Args:
            results: dict[name, BacktestResult]
            benchmark_returns: 基准收益率序列

        Returns:
            dict[name, correlation]
        """
        if benchmark_returns is None:
            for name, result in results.items():
                if result.beta != 0:
                    return {
                        name: min(1.0, abs(result.beta))
                        for name, result in results.items()
                    }
            return {name: 0.0 for name in results}

        correlations = {}
        for name, result in results.items():
            if result.returns is not None and len(result.returns) > 0:
                aligned = pd.concat(
                    [result.returns, benchmark_returns], axis=1
                ).dropna()
                if len(aligned) > 10:
                    corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
                    correlations[name] = corr if not pd.isna(corr) else 0.0
                else:
                    correlations[name] = 0.0
            else:
                correlations[name] = 0.0

        return correlations


# ---------------------------------------------------------------------------
# DynamicWeightAllocator: 动态权重分配器
# ---------------------------------------------------------------------------
class DynamicWeightAllocator:
    """
    动态权重分配器

    根据策略近期表现动态分配权重

    功能:
    - 近期表现加权 (时间衰减)
    - 指数衰减加权
    - 风险平价加权
    - 综合多因子加权
    """

    def __init__(
        self,
        decay_factor: float = DEFAULT_DECAY_FACTOR,
        half_life: int = DEFAULT_HALF_LIFE,
        min_weight: float = 0.05,
        max_weight: float = 0.50,
    ):
        """
        Args:
            decay_factor: 衰减因子 (0~1, 越大越重视近期)
            half_life: 半衰期 (交易日数)
            min_weight: 最小权重
            max_weight: 最大权重
        """
        self.decay_factor = max(0.0, min(1.0, decay_factor))
        self.half_life = max(1, half_life)
        self.min_weight = min_weight
        self.max_weight = max_weight

    def allocate_weights(
        self,
        scores: Dict[str, StrategyScore],
        recent_returns: Optional[Dict[str, List[float]]] = None,
        method: str = "score_decay",
    ) -> Dict[str, float]:
        """
        分配策略权重

        Args:
            scores: dict[name, StrategyScore]
            recent_returns: dict[name, list[recent_returns]] 近期收益率序列
            method: 分配方法
                - score_decay: 综合评分 + 时间衰减
                - recent_performance: 近期表现加权
                - risk_parity: 风险平价
                - equal: 等权重

        Returns:
            dict[name, weight]
        """
        if not scores:
            return {}

        if method == "equal":
            return self._equal_weights(scores)
        elif method == "recent_performance":
            return self._recent_performance_weights(scores, recent_returns)
        elif method == "risk_parity":
            return self._risk_parity_weights(scores)
        else:
            return self._score_decay_weights(scores, recent_returns)

    def _equal_weights(self, scores: Dict[str, StrategyScore]) -> Dict[str, float]:
        n = len(scores)
        w = 1.0 / n
        return {name: w for name in scores}

    def _score_decay_weights(
        self,
        scores: Dict[str, StrategyScore],
        recent_returns: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, float]:
        """
        综合评分 + 近期表现衰减加权

        weight_i = score_i * decay_factor^(days_ago) * recent_performance_bonus
        """
        raw_scores = {}
        for name, score in scores.items():
            base = score.overall

            if recent_returns and name in recent_returns:
                rets = recent_returns[name]
                if rets:
                    recent_perf = (
                        np.mean(rets[-20:]) if len(rets) >= 20 else np.mean(rets)
                    )
                    perf_bonus = 1.0 / (1.0 + math.exp(-recent_perf * 5))
                    base = base * (0.7 + 0.3 * perf_bonus)

            raw_scores[name] = base

        total = sum(raw_scores.values())
        if total < 1e-12:
            return self._equal_weights(scores)

        weights = {name: s / total for name, s in raw_scores.items()}
        return self._clip_and_normalize(weights)

    def _recent_performance_weights(
        self,
        scores: Dict[str, StrategyScore],
        recent_returns: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, float]:
        """
        近期表现加权

        使用指数衰减对近期收益率加权, 近期表现越好权重越高
        """
        if not recent_returns:
            return self._equal_weights(scores)

        weighted_scores = {}
        for name, rets in recent_returns.items():
            if not rets:
                weighted_scores[name] = 0.0
                continue

            n = len(rets)
            decayed = 0.0
            weight_sum = 0.0
            for i, r in enumerate(rets):
                age = n - 1 - i
                w = self.decay_factor**age
                decayed += r * w
                weight_sum += w

            avg_decayed = decayed / weight_sum if weight_sum > 0 else 0.0
            weighted_scores[name] = max(0, avg_decayed)

        total = sum(weighted_scores.values())
        if total < 1e-12:
            return self._equal_weights(scores)

        weights = {name: s / total for name, s in weighted_scores.items()}
        return self._clip_and_normalize(weights)

    def _risk_parity_weights(
        self,
        scores: Dict[str, StrategyScore],
    ) -> Dict[str, float]:
        """
        风险平价加权

        权重与风险 (波动率倒数) 成正比, 同时考虑评分
        """
        inv_vol = {}
        for name, score in scores.items():
            vol = 1.0
            if score.metrics and score.metrics.annual_volatility > 0:
                vol = score.metrics.annual_volatility

            inv_vol[name] = (1.0 / vol) * score.overall

        total = sum(inv_vol.values())
        if total < 1e-12:
            return self._equal_weights(scores)

        weights = {name: s / total for name, s in inv_vol.items()}
        return self._clip_and_normalize(weights)

    def _clip_and_normalize(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        裁剪权重到 [min_weight, max_weight] 并重新归一化
        """
        clipped = {}
        for name, w in weights.items():
            clipped[name] = max(self.min_weight, min(self.max_weight, w))

        total = sum(clipped.values())
        if total < 1e-12:
            return self._equal_weights({name: 1.0 for name in weights})

        return {name: w / total for name, w in clipped.items()}

    def compute_decay_weights(
        self,
        n_periods: int,
        decay_type: str = "exponential",
    ) -> np.ndarray:
        """
        计算时间衰减权重序列

        Args:
            n_periods: 期数
            decay_type: 衰减类型 (exponential, linear, half_life)

        Returns:
            衰减权重数组 (最近一期权重最大)
        """
        if decay_type == "linear":
            weights = np.arange(1, n_periods + 1, dtype=float)
        elif decay_type == "half_life":
            half_life = self.half_life
            weights = np.array(
                [0.5 ** ((n_periods - 1 - i) / half_life) for i in range(n_periods)]
            )
        else:
            weights = np.array(
                [self.decay_factor ** (n_periods - 1 - i) for i in range(n_periods)]
            )

        total = weights.sum()
        if total > 0:
            weights /= total

        return weights


# ---------------------------------------------------------------------------
# StrategyEvaluator: 统一策略评估入口
# ---------------------------------------------------------------------------
class StrategyEvaluator:
    """
    统一策略评估器

    整合评分、排名、相关性分析、权重分配

    使用示例:
        evaluator = StrategyEvaluator()
        scores = evaluator.evaluate(results, walk_forward_map=wf_map)
        ranked = evaluator.rank(scores)
        best = evaluator.select_best(scores, top_k=3)
        weights = evaluator.allocate_weights(scores)
        corr = evaluator.analyze_correlation(results)
    """

    def __init__(
        self,
        score_weights: Optional[Dict[str, float]] = None,
        decay_factor: float = DEFAULT_DECAY_FACTOR,
        min_weight: float = 0.05,
        max_weight: float = 0.50,
    ):
        self.scorer = StrategyScorer(score_weights=score_weights)
        self.ranker = StrategyRanker()
        self.correlation_analyzer = CorrelationAnalyzer()
        self.weight_allocator = DynamicWeightAllocator(
            decay_factor=decay_factor,
            min_weight=min_weight,
            max_weight=max_weight,
        )

    def evaluate(
        self,
        results: Dict[str, BacktestResult],
        walk_forward_map: Optional[Dict[str, List[BacktestResult]]] = None,
        capital_map: Optional[Dict[str, float]] = None,
        max_capacity_map: Optional[Dict[str, float]] = None,
    ) -> Dict[str, StrategyScore]:
        """
        评估所有策略

        Args:
            results: dict[name, BacktestResult]
            walk_forward_map: dict[name, list[BacktestResult]]
            capital_map: dict[name, capital]
            max_capacity_map: dict[name, max_capacity]

        Returns:
            dict[name, StrategyScore]
        """
        return self.scorer.evaluate_batch(
            results,
            walk_forward_map=walk_forward_map,
            capital_map=capital_map,
            max_capacity_map=max_capacity_map,
        )

    def rank(
        self,
        scores: Dict[str, StrategyScore],
        sort_by: str = "overall",
    ) -> List[Tuple[str, StrategyScore]]:
        """
        排名策略

        Args:
            scores: dict[name, StrategyScore]
            sort_by: 排序依据

        Returns:
            list[(name, StrategyScore)]
        """
        return self.ranker.rank_strategies(scores, sort_by=sort_by)

    def select_best(
        self,
        scores: Dict[str, StrategyScore],
        top_k: int = 3,
        min_score: float = 0.0,
        exclude_correlated: bool = True,
        results: Optional[Dict[str, BacktestResult]] = None,
        corr_threshold: float = 0.7,
    ) -> List[str]:
        """
        选择最优策略

        Args:
            scores: dict[name, StrategyScore]
            top_k: 选择数量
            min_score: 最低评分门槛
            exclude_correlated: 是否排除高相关策略
            results: 回测结果 (用于计算相关性)
            corr_threshold: 相关性阈值

        Returns:
            最优策略名称列表
        """
        corr_matrix = None
        if exclude_correlated and results:
            corr_matrix = self.correlation_analyzer.analyze_correlation(results)

        return self.ranker.select_best(
            scores,
            top_k=top_k,
            min_score=min_score,
            exclude_correlated=exclude_correlated,
            correlation_matrix=corr_matrix,
            corr_threshold=corr_threshold,
        )

    def allocate_weights(
        self,
        scores: Dict[str, StrategyScore],
        recent_returns: Optional[Dict[str, List[float]]] = None,
        method: str = "score_decay",
    ) -> Dict[str, float]:
        """
        动态分配权重

        Args:
            scores: dict[name, StrategyScore]
            recent_returns: dict[name, list[returns]]
            method: 分配方法

        Returns:
            dict[name, weight]
        """
        return self.weight_allocator.allocate_weights(
            scores, recent_returns=recent_returns, method=method
        )

    def analyze_correlation(
        self,
        results: Dict[str, BacktestResult],
        method: str = "pearson",
    ) -> pd.DataFrame:
        """
        分析策略相关性

        Args:
            results: dict[name, BacktestResult]
            method: 相关性方法

        Returns:
            DataFrame 相关性矩阵
        """
        return self.correlation_analyzer.analyze_correlation(results, method=method)

    def find_clusters(
        self,
        correlation_matrix: pd.DataFrame,
        threshold: float = 0.7,
    ) -> List[List[str]]:
        """
        识别同质化策略簇

        Args:
            correlation_matrix: 相关性矩阵
            threshold: 相关性阈值

        Returns:
            list[list[strategy_names]]
        """
        return self.correlation_analyzer.find_clusters(correlation_matrix, threshold)

    def pareto_frontier(
        self,
        scores: Dict[str, StrategyScore],
        objectives: Optional[List[str]] = None,
    ) -> List[str]:
        """
        识别帕累托前沿策略

        Args:
            scores: dict[name, StrategyScore]
            objectives: 目标维度

        Returns:
            帕累托前沿策略名称列表
        """
        return self.ranker.pareto_frontier(scores, objectives=objectives)

    def summary(
        self,
        scores: Dict[str, StrategyScore],
    ) -> pd.DataFrame:
        """
        生成评估汇总表

        Args:
            scores: dict[name, StrategyScore]

        Returns:
            DataFrame 汇总表
        """
        return self.ranker.summary_table(scores)

    def full_report(
        self,
        results: Dict[str, BacktestResult],
        walk_forward_map: Optional[Dict[str, List[BacktestResult]]] = None,
        capital_map: Optional[Dict[str, float]] = None,
        max_capacity_map: Optional[Dict[str, float]] = None,
        top_k: int = 3,
        weight_method: str = "score_decay",
        recent_returns: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, Any]:
        """
        生成完整评估报告

        Args:
            results: dict[name, BacktestResult]
            walk_forward_map: Walk-Forward 结果
            capital_map: 资金规模
            max_capacity_map: 最大容量
            top_k: 选择最优策略数量
            weight_method: 权重分配方法
            recent_returns: 近期收益率

        Returns:
            完整报告字典
        """
        scores = self.evaluate(
            results,
            walk_forward_map=walk_forward_map,
            capital_map=capital_map,
            max_capacity_map=max_capacity_map,
        )

        ranked = self.rank(scores)
        best = self.select_best(scores, top_k=top_k, results=results)
        weights = self.allocate_weights(
            scores, recent_returns=recent_returns, method=weight_method
        )
        corr_matrix = self.analyze_correlation(results)
        clusters = self.find_clusters(corr_matrix) if not corr_matrix.empty else []
        pareto = self.pareto_frontier(scores)
        diversity = (
            self.correlation_analyzer.diversity_score(corr_matrix)
            if not corr_matrix.empty
            else 1.0
        )
        summary_df = self.summary(scores)

        return {
            "scores": scores,
            "ranked": ranked,
            "best_strategies": best,
            "weights": weights,
            "correlation_matrix": corr_matrix,
            "clusters": clusters,
            "pareto_frontier": pareto,
            "diversity_score": diversity,
            "summary_table": summary_df,
        }
