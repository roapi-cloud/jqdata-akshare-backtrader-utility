# -*- coding: utf-8 -*-
"""
组合优化器: 多策略组合优化、权重分配、动态再平衡、交易成本优化

核心类:
- PortfolioConfig: 组合配置 (optimization_method, rebalance_period, max_single_strategy_weight, turnover_penalty)
- PortfolioWeights: 组合权重 (weights, last_rebalance, turnover, expected_return, expected_risk)
- PortfolioOptimizer: 组合优化器 (equal_weight, risk_parity, mean_variance, black_litterman, hierarchical_risk_parity)
- RebalanceEngine: 再平衡引擎 (periodic, threshold, drift)

优化方法:
1. equal_weight: 等权分配
2. risk_parity: 风险平价 (每个策略贡献相同风险)
3. mean_variance: 均值方差优化 (带换手率惩罚)
4. black_litterman: Black-Litterman (先验+观点)
5. hierarchical_risk_parity: 分层风险平价 (基于策略相关性聚类)

组合优化 (非单策略内资产配置):
- 输入: 多个策略的历史收益序列、协方差矩阵、预期收益
- 输出: 各策略的最优权重分配
- 约束: 单策略权重上下限、总权重=1、相关性约束、换手率惩罚
"""

import logging
import datetime
import math
from typing import Optional, Dict, List, Tuple, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from copy import deepcopy

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage, fcluster

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# 优化方法枚举
# ---------------------------------------------------------------------------
class OptimizationMethod(Enum):
    """组合优化方法"""

    EQUAL_WEIGHT = "equal_weight"  # 等权
    RISK_PARITY = "risk_parity"  # 风险平价
    MEAN_VARIANCE = "mean_variance"  # 均值方差
    BLACK_LITTERMAN = "black_litterman"  # Black-Litterman
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"  # 分层风险平价


class RebalanceTrigger(Enum):
    """再平衡触发类型"""

    PERIODIC = "periodic"  # 定期
    THRESHOLD = "threshold"  # 阈值触发
    DRIFT = "drift"  # 偏离度触发


# ---------------------------------------------------------------------------
# PortfolioConfig: 组合配置
# ---------------------------------------------------------------------------
@dataclass
class PortfolioConfig:
    """
    组合优化配置

    Attributes:
        optimization_method: 优化方法
        rebalance_period: 再平衡周期 (交易日)
        rebalance_threshold: 再平衡阈值 (权重偏离超过此值触发再平衡)
        max_single_strategy_weight: 单策略最大权重
        min_single_strategy_weight: 单策略最小权重
        max_strategies: 最大策略数量 (0 表示不限制)
        turnover_penalty: 换手率惩罚系数 (越大越抑制换手)
        risk_aversion: 风险厌恶系数 (均值方差用)
        target_volatility: 目标组合波动率 (0 表示不限制)
        correlation_constraint: 相关性约束 (策略间最大允许相关性, 0 表示不限制)
        cash_reserve: 现金保留比例
        bl_tau: Black-Litterman 不确定性参数
        bl_risk_aversion: Black-Litterman 风险厌恶系数
        hrp_linkage_method: HRP 聚类方法 ('single', 'complete', 'average', 'ward')
        hrp_variance_method: HRP 方差计算方法 ('equal', 'var', 'risk')
    """

    optimization_method: OptimizationMethod = OptimizationMethod.EQUAL_WEIGHT
    rebalance_period: int = 20
    rebalance_threshold: float = 0.05
    max_single_strategy_weight: float = 0.40
    min_single_strategy_weight: float = 0.05
    max_strategies: int = 0
    turnover_penalty: float = 0.0
    risk_aversion: float = 1.0
    target_volatility: float = 0.0
    correlation_constraint: float = 0.0
    cash_reserve: float = 0.0
    bl_tau: float = 0.05
    bl_risk_aversion: float = 2.5
    hrp_linkage_method: str = "ward"
    hrp_variance_method: str = "var"

    def __post_init__(self):
        if self.max_single_strategy_weight < self.min_single_strategy_weight:
            raise ValueError(
                "max_single_strategy_weight 不能小于 min_single_strategy_weight"
            )
        if self.cash_reserve < 0 or self.cash_reserve > 1:
            raise ValueError("cash_reserve 必须在 [0, 1] 范围内")
        if self.rebalance_period < 1:
            raise ValueError("rebalance_period 必须 >= 1")
        if self.rebalance_threshold < 0:
            raise ValueError("rebalance_threshold 不能为负")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["optimization_method"] = self.optimization_method.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioConfig":
        d = d.copy()
        if "optimization_method" in d and isinstance(d["optimization_method"], str):
            d["optimization_method"] = OptimizationMethod(d["optimization_method"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return (
            f"PortfolioConfig(method={self.optimization_method.value}, "
            f"rebalance_period={self.rebalance_period}, "
            f"max_weight={self.max_single_strategy_weight}, "
            f"turnover_penalty={self.turnover_penalty})"
        )


# ---------------------------------------------------------------------------
# PortfolioWeights: 组合权重
# ---------------------------------------------------------------------------
@dataclass
class PortfolioWeights:
    """
    组合权重结果

    Attributes:
        weights: 策略权重字典 {strategy_name: weight}
        last_rebalance: 上次再平衡日期
        turnover: 换手率 (相对于上次权重)
        expected_return: 预期年化收益率
        expected_risk: 预期年化波动率
        sharpe_ratio: 预期夏普比率
        method: 使用的优化方法
        constraints_applied: 是否应用了约束
        optimization_details: 优化过程详细信息
    """

    weights: Dict[str, float] = field(default_factory=dict)
    last_rebalance: Optional[datetime.date] = None
    turnover: float = 0.0
    expected_return: float = 0.0
    expected_risk: float = 0.0
    sharpe_ratio: float = 0.0
    method: str = ""
    constraints_applied: bool = False
    optimization_details: Dict[str, Any] = field(default_factory=dict)

    def total_weight(self) -> float:
        return sum(self.weights.values())

    def normalize(self) -> "PortfolioWeights":
        total = self.total_weight()
        if total > 1e-12:
            self.weights = {k: v / total for k, v in self.weights.items()}
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": {k: round(v, 6) for k, v in self.weights.items()},
            "last_rebalance": self.last_rebalance.isoformat()
            if self.last_rebalance
            else None,
            "turnover": round(self.turnover, 6),
            "expected_return": round(self.expected_return, 6),
            "expected_risk": round(self.expected_risk, 6),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "method": self.method,
            "constraints_applied": self.constraints_applied,
        }

    def __repr__(self) -> str:
        n = len(self.weights)
        return (
            f"PortfolioWeights(n={n}, return={self.expected_return:.2%}, "
            f"risk={self.expected_risk:.2%}, sharpe={self.sharpe_ratio:.3f})"
        )


# ---------------------------------------------------------------------------
# _portfolio_stats: 组合统计计算
# ---------------------------------------------------------------------------
def _portfolio_return(weights: np.ndarray, expected_returns: np.ndarray) -> float:
    return float(np.dot(weights, expected_returns))


def _portfolio_volatility(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    return float(np.sqrt(np.dot(weights, np.dot(cov_matrix, weights))))


def _portfolio_sharpe(
    weights: np.ndarray,
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free: float = 0.0,
) -> float:
    ret = _portfolio_return(weights, expected_returns)
    vol = _portfolio_volatility(weights, cov_matrix)
    if vol < 1e-12:
        return 0.0
    return (ret - risk_free) / vol


def _annualize(daily_value: float, periods: int = TRADING_DAYS_PER_YEAR) -> float:
    return daily_value * math.sqrt(periods)


def _risk_contribution(weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
    marginal_risk = np.dot(cov_matrix, weights)
    return weights * marginal_risk


def _normalize_weights(weights: np.ndarray) -> np.ndarray:
    total = weights.sum()
    if total > 1e-12:
        return weights / total
    return weights


def _clip_weights(weights: np.ndarray, min_w: float, max_w: float) -> np.ndarray:
    clipped = np.clip(weights, min_w, max_w)
    total = clipped.sum()
    if total > 1e-12:
        clipped = clipped / total
    else:
        clipped = np.ones_like(weights) / len(weights)
    return clipped


# ---------------------------------------------------------------------------
# PortfolioOptimizer: 组合优化器
# ---------------------------------------------------------------------------
class PortfolioOptimizer:
    """
    多策略组合优化器

    支持多种优化方法:
    1. equal_weight: 等权分配
    2. risk_parity: 风险平价
    3. mean_variance: 均值方差优化 (带换手率惩罚)
    4. black_litterman: Black-Litterman
    5. hierarchical_risk_parity: 分层风险平价

    所有方法都支持:
    - 权重约束 (min/max)
    - 策略相关性约束
    - 换手率惩罚
    - 现金保留
    """

    def __init__(self, config: Optional[PortfolioConfig] = None):
        self.config = config or PortfolioConfig()

    def optimize(
        self,
        weights_history: Optional[Dict[str, float]] = None,
        returns_matrix: Optional[pd.DataFrame] = None,
        expected_returns: Optional[Dict[str, float]] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
        method: Optional[OptimizationMethod] = None,
        bl_views: Optional[Dict[str, Any]] = None,
        correlation_matrix: Optional[pd.DataFrame] = None,
        risk_free_rate: float = 0.0,
    ) -> PortfolioWeights:
        """
        执行组合优化

        Args:
            weights_history: 历史权重 {strategy_name: weight} (用于计算换手率)
            returns_matrix: 策略收益矩阵 (columns=strategy names, index=dates)
            expected_returns: 预期收益率 {strategy_name: annual_return}
            cov_matrix: 协方差矩阵 (DataFrame, index/columns=strategy names)
            method: 优化方法 (覆盖 config 中的设置)
            bl_views: Black-Litterman 观点 {views: list, Q: array, P: array, omega: array}
            correlation_matrix: 策略相关性矩阵 (用于相关性约束)
            risk_free_rate: 无风险利率

        Returns:
            PortfolioWeights
        """
        opt_method = method or self.config.optimization_method

        strategy_names = self._extract_names(
            returns_matrix, cov_matrix, expected_returns, weights_history
        )

        if len(strategy_names) == 0:
            raise ValueError("没有可用的策略")

        if len(strategy_names) == 1:
            return PortfolioWeights(
                weights={strategy_names[0]: 1.0 - self.config.cash_reserve},
                method=opt_method.value,
                last_rebalance=datetime.date.today(),
            )

        exp_ret, cov = self._prepare_inputs(
            strategy_names, returns_matrix, expected_returns, cov_matrix
        )

        if opt_method == OptimizationMethod.EQUAL_WEIGHT:
            result = self._equal_weight(strategy_names)
        elif opt_method == OptimizationMethod.RISK_PARITY:
            result = self._risk_parity(strategy_names, cov, exp_ret)
        elif opt_method == OptimizationMethod.MEAN_VARIANCE:
            result = self._mean_variance(
                strategy_names, cov, exp_ret, weights_history, risk_free_rate
            )
        elif opt_method == OptimizationMethod.BLACK_LITTERMAN:
            result = self._black_litterman(
                strategy_names, cov, exp_ret, bl_views, risk_free_rate
            )
        elif opt_method == OptimizationMethod.HIERARCHICAL_RISK_PARITY:
            result = self.hierarchical_risk_parity(
                strategy_names,
                returns_matrix,
                pd.DataFrame(cov, columns=strategy_names, index=strategy_names),
            )
        else:
            raise ValueError(f"不支持的优化方法: {opt_method}")

        result = self._apply_correlation_constraint(
            result, strategy_names, correlation_matrix, cov
        )
        result = self._apply_cash_reserve(result)
        result = self._calculate_metrics(result, exp_ret, cov)

        if weights_history:
            result.turnover = self.calculate_turnover(weights_history, result.weights)

        result.last_rebalance = datetime.date.today()
        result.method = opt_method.value

        return result

    def _extract_names(self, *sources) -> List[str]:
        names = []
        for src in sources:
            if src is None:
                continue
            if isinstance(src, pd.DataFrame):
                names.extend(list(src.columns))
            elif isinstance(src, dict):
                names.extend(list(src.keys()))
            break
        for src in sources:
            if src is not None:
                if isinstance(src, pd.DataFrame):
                    names = list(src.columns)
                elif isinstance(src, dict):
                    names = list(src.keys())
                break
        return list(dict.fromkeys(names))

    def _prepare_inputs(
        self,
        strategy_names: List[str],
        returns_matrix: Optional[pd.DataFrame],
        expected_returns: Optional[Dict[str, float]],
        cov_matrix: Optional[pd.DataFrame],
    ) -> Tuple[np.ndarray, np.ndarray]:
        n = len(strategy_names)

        if expected_returns is not None:
            exp_ret = np.array([expected_returns.get(s, 0.0) for s in strategy_names])
        elif returns_matrix is not None:
            exp_ret = np.array(
                [
                    returns_matrix[s].mean() * TRADING_DAYS_PER_YEAR
                    for s in strategy_names
                ]
            )
        else:
            exp_ret = np.zeros(n)

        if cov_matrix is not None:
            cov = np.array(
                [[cov_matrix.loc[i, j] for j in strategy_names] for i in strategy_names]
            )
        elif returns_matrix is not None:
            cov = returns_matrix[strategy_names].cov().values * TRADING_DAYS_PER_YEAR
        else:
            cov = np.eye(n) * 0.02

        cov = (cov + cov.T) / 2
        min_eig = np.min(np.linalg.eigvalsh(cov))
        if min_eig < 0:
            cov += (-min_eig + 1e-8) * np.eye(n)

        return exp_ret, cov

    def equal_weight(
        self, strategy_names: List[str], cash_reserve: Optional[float] = None
    ) -> PortfolioWeights:
        return self._equal_weight(strategy_names, cash_reserve)

    def _equal_weight(
        self, strategy_names: List[str], cash_reserve: Optional[float] = None
    ) -> PortfolioWeights:
        cash = cash_reserve if cash_reserve is not None else self.config.cash_reserve
        investable = 1.0 - cash
        w = investable / len(strategy_names)
        weights = {s: w for s in strategy_names}
        return PortfolioWeights(weights=weights, method="equal_weight")

    def risk_parity(
        self,
        strategy_names: List[str],
        cov_matrix: pd.DataFrame,
        expected_returns: Optional[Dict[str, float]] = None,
    ) -> PortfolioWeights:
        n = len(strategy_names)
        cov = np.array(
            [[cov_matrix.loc[i, j] for j in strategy_names] for i in strategy_names]
        )
        exp_ret = np.zeros(n)
        if expected_returns:
            exp_ret = np.array([expected_returns.get(s, 0.0) for s in strategy_names])
        return self._risk_parity(strategy_names, cov, exp_ret)

    def _risk_parity(
        self, strategy_names: List[str], cov: np.ndarray, exp_ret: np.ndarray
    ) -> PortfolioWeights:
        n = len(strategy_names)

        def risk_parity_objective(w):
            w = np.abs(w)
            port_vol = np.sqrt(np.dot(w, np.dot(cov, w)))
            if port_vol < 1e-12:
                return 1e10
            rc = _risk_contribution(w, cov)
            rc_target = port_vol / n
            return np.sum((rc - rc_target) ** 2)

        x0 = np.ones(n) / n
        bounds = [
            (
                self.config.min_single_strategy_weight,
                self.config.max_single_strategy_weight,
            )
        ] * n
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        result = minimize(
            risk_parity_objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-12},
        )

        weights = result.x
        weights = _clip_weights(
            weights,
            self.config.min_single_strategy_weight,
            self.config.max_single_strategy_weight,
        )

        pw = PortfolioWeights(
            weights={s: float(weights[i]) for i, s in enumerate(strategy_names)},
            method="risk_parity",
            optimization_details={"success": result.success, "iterations": result.nit},
        )
        pw.constraints_applied = True
        return pw

    def mean_variance(
        self,
        strategy_names: List[str],
        cov_matrix: pd.DataFrame,
        expected_returns: Dict[str, float],
        weights_history: Optional[Dict[str, float]] = None,
        risk_free_rate: float = 0.0,
    ) -> PortfolioWeights:
        n = len(strategy_names)
        cov = np.array(
            [[cov_matrix.loc[i, j] for j in strategy_names] for i in strategy_names]
        )
        exp_ret = np.array([expected_returns.get(s, 0.0) for s in strategy_names])
        return self._mean_variance(
            strategy_names, cov, exp_ret, weights_history, risk_free_rate
        )

    def _mean_variance(
        self,
        strategy_names: List[str],
        cov: np.ndarray,
        exp_ret: np.ndarray,
        weights_history: Optional[Dict[str, float]] = None,
        risk_free_rate: float = 0.0,
    ) -> PortfolioWeights:
        n = len(strategy_names)
        gamma = self.config.risk_aversion
        turnover_penalty = self.config.turnover_penalty

        hist_weights = None
        if weights_history:
            hist_weights = np.array(
                [weights_history.get(s, 0.0) for s in strategy_names]
            )

        def objective(w):
            port_var = np.dot(w, np.dot(cov, w))
            port_ret = np.dot(w, exp_ret)
            utility = -port_ret + gamma * port_var

            if turnover_penalty > 0 and hist_weights is not None:
                turnover = np.sum(np.abs(w - hist_weights))
                utility += turnover_penalty * turnover

            return utility

        x0 = np.ones(n) / n
        bounds = [
            (
                self.config.min_single_strategy_weight,
                self.config.max_single_strategy_weight,
            )
        ] * n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        if self.config.target_volatility > 0:
            target_var = (
                self.config.target_volatility / math.sqrt(TRADING_DAYS_PER_YEAR)
            ) ** 2
            constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda w: target_var - np.dot(w, np.dot(cov, w)),
                }
            )

        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 2000, "ftol": 1e-14},
        )

        weights = result.x
        weights = _clip_weights(
            weights,
            self.config.min_single_strategy_weight,
            self.config.max_single_strategy_weight,
        )

        pw = PortfolioWeights(
            weights={s: float(weights[i]) for i, s in enumerate(strategy_names)},
            method="mean_variance",
            optimization_details={
                "success": result.success,
                "iterations": result.nit,
                "risk_aversion": gamma,
                "turnover_penalty": turnover_penalty,
            },
        )
        pw.constraints_applied = True
        return pw

    def black_litterman(
        self,
        strategy_names: List[str],
        cov_matrix: pd.DataFrame,
        expected_returns: Optional[Dict[str, float]] = None,
        views: Optional[Dict[str, Any]] = None,
        risk_free_rate: float = 0.0,
    ) -> PortfolioWeights:
        n = len(strategy_names)
        cov = np.array(
            [[cov_matrix.loc[i, j] for j in strategy_names] for i in strategy_names]
        )

        if expected_returns:
            exp_ret = np.array([expected_returns.get(s, 0.0) for s in strategy_names])
        else:
            exp_ret = np.zeros(n)

        return self._black_litterman(
            strategy_names, cov, exp_ret, views, risk_free_rate
        )

    def _black_litterman(
        self,
        strategy_names: List[str],
        cov: np.ndarray,
        market_returns: np.ndarray,
        views: Optional[Dict[str, Any]] = None,
        risk_free_rate: float = 0.0,
    ) -> PortfolioWeights:
        n = len(strategy_names)
        tau = self.config.bl_tau
        delta = self.config.bl_risk_aversion

        pi = market_returns.copy()
        if np.allclose(pi, 0):
            port_var = np.trace(cov) / n
            pi = delta * np.dot(cov, np.ones(n) / n)

        if views is None:
            bl_returns = pi
        else:
            P = np.array(views.get("P", []))
            Q = np.array(views.get("Q", []))
            omega = views.get("omega", None)

            if len(P.shape) == 1:
                P = P.reshape(1, -1)
            if len(Q.shape) == 0:
                Q = Q.reshape(1)

            if omega is None:
                omega = np.diag(np.diag(tau * P @ cov @ P.T))

            omega = np.array(omega)
            if omega.ndim == 0:
                omega = np.eye(P.shape[0]) * float(omega)
            elif omega.ndim == 1:
                omega = np.diag(omega)

            tau_cov = tau * cov
            P_t = P.T

            M1 = np.linalg.inv(P_t @ np.linalg.inv(tau_cov) @ P + np.linalg.inv(omega))
            M2 = P_t @ np.linalg.inv(tau_cov) @ pi + np.linalg.inv(omega) @ Q

            bl_returns = tau_cov @ M1 @ M2

        bl_cov = cov + tau * cov
        bl_cov = (bl_cov + bl_cov.T) / 2

        def objective(w):
            port_var = np.dot(w, np.dot(bl_cov, w))
            port_ret = np.dot(w, bl_returns)
            return -port_ret + delta * port_var

        x0 = np.ones(n) / n
        bounds = [
            (
                self.config.min_single_strategy_weight,
                self.config.max_single_strategy_weight,
            )
        ] * n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 2000, "ftol": 1e-14},
        )

        weights = result.x
        weights = _clip_weights(
            weights,
            self.config.min_single_strategy_weight,
            self.config.max_single_strategy_weight,
        )

        pw = PortfolioWeights(
            weights={s: float(weights[i]) for i, s in enumerate(strategy_names)},
            method="black_litterman",
            optimization_details={
                "success": result.success,
                "tau": tau,
                "risk_aversion": delta,
                "has_views": views is not None,
            },
        )
        pw.constraints_applied = True
        return pw

    def hierarchical_risk_parity(
        self,
        strategy_names: List[str],
        returns_matrix: pd.DataFrame,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> PortfolioWeights:
        if returns_matrix is None or len(returns_matrix) < 20:
            return self._equal_weight(strategy_names)

        rets = returns_matrix[strategy_names].dropna()
        corr = rets.corr()
        dist = 0.5 * (1 - corr.values)
        dist = np.clip(dist, 0, 1)

        linkage_matrix = linkage(
            dist[np.triu_indices_from(dist, k=1)],
            method=self.config.hrp_linkage_method,
        )

        sort_ix = self._quasi_diagonal(linkage_matrix)
        sorted_names = [strategy_names[i] for i in sort_ix]

        if cov_matrix is not None:
            cov = np.array(
                [[cov_matrix.loc[i, j] for j in strategy_names] for i in strategy_names]
            )
        else:
            cov = rets.cov().values * TRADING_DAYS_PER_YEAR

        weights_array = self._recursive_bisection(cov, sort_ix)
        weights_array = _clip_weights(
            weights_array,
            self.config.min_single_strategy_weight,
            self.config.max_single_strategy_weight,
        )

        pw = PortfolioWeights(
            weights={s: float(weights_array[i]) for i, s in enumerate(strategy_names)},
            method="hierarchical_risk_parity",
            optimization_details={
                "linkage_method": self.config.hrp_linkage_method,
                "sorted_order": sorted_names,
            },
        )
        pw.constraints_applied = True
        return pw

    def _quasi_diagonal(self, link_mat: np.ndarray) -> List[int]:
        n = link_mat.shape[0] + 1

        def _cluster_sort(lm, node_id):
            if node_id < lm.shape[0] + 1:
                return [node_id - 1]
            left = int(lm[node_id - lm.shape[0] - 1, 0])
            right = int(lm[node_id - lm.shape[0] - 1, 1])
            left_items = (
                [left - 1] if left < lm.shape[0] + 1 else _cluster_sort(lm, left)
            )
            right_items = (
                [right - 1] if right < lm.shape[0] + 1 else _cluster_sort(lm, right)
            )
            return left_items + right_items

        return _cluster_sort(link_mat, 2 * link_mat.shape[0])

    def _recursive_bisection(self, cov: np.ndarray, sort_ix: List[int]) -> np.ndarray:
        n = len(sort_ix)
        weights = np.ones(n)

        def _bisect(cov, indices):
            if len(indices) == 1:
                return {indices[0]: 1.0}

            mid = len(indices) // 2
            left_idx = indices[:mid]
            right_idx = indices[mid:]

            var_left = self._cluster_variance(cov, left_idx)
            var_right = self._cluster_variance(cov, right_idx)

            alpha = (
                1 - var_left / (var_left + var_right)
                if (var_left + var_right) > 1e-12
                else 0.5
            )

            left_weights = _bisect(cov, left_idx)
            right_weights = _bisect(cov, right_idx)

            result = {}
            for k, v in left_weights.items():
                result[k] = v * alpha
            for k, v in right_weights.items():
                result[k] = v * (1 - alpha)

            return result

        raw = _bisect(cov, sort_ix)
        weights = np.array([raw.get(i, 0.0) for i in range(n)])
        total = weights.sum()
        if total > 1e-12:
            weights /= total
        return weights

    def _cluster_variance(self, cov: np.ndarray, indices: List[int]) -> float:
        if not indices:
            return 0.0
        sub_cov = cov[np.ix_(indices, indices)]
        n = len(indices)
        w = np.ones(n) / n
        return float(np.dot(w, np.dot(sub_cov, w)))

    def _apply_correlation_constraint(
        self,
        pw: PortfolioWeights,
        strategy_names: List[str],
        correlation_matrix: Optional[pd.DataFrame],
        cov: np.ndarray,
    ) -> PortfolioWeights:
        if self.config.correlation_constraint <= 0 or correlation_matrix is None:
            return pw

        max_corr = self.config.correlation_constraint
        weights = pw.weights.copy()
        penalized = {}

        for name, w in weights.items():
            penalty = 1.0
            for other_name, other_w in weights.items():
                if other_name == name:
                    continue
                try:
                    corr = abs(correlation_matrix.loc[name, other_name])
                    if corr > max_corr:
                        penalty *= 1 - (corr - max_corr)
                except (KeyError, TypeError):
                    pass
            penalized[name] = w * max(penalty, 0.1)

        total = sum(penalized.values())
        if total > 1e-12:
            pw.weights = {k: v / total for k, v in penalized.items()}

        pw.constraints_applied = True
        return pw

    def _apply_cash_reserve(self, pw: PortfolioWeights) -> PortfolioWeights:
        if self.config.cash_reserve <= 0:
            return pw

        investable = 1.0 - self.config.cash_reserve
        pw.weights = {k: v * investable for k, v in pw.weights.items()}
        pw.weights["_cash"] = self.config.cash_reserve
        return pw

    def _calculate_metrics(
        self, pw: PortfolioWeights, exp_ret: np.ndarray, cov: np.ndarray
    ) -> PortfolioWeights:
        strategy_names = [k for k in pw.weights.keys() if k != "_cash"]
        if not strategy_names:
            return pw

        w = np.array([pw.weights.get(s, 0.0) for s in strategy_names])
        e = np.array(
            [exp_ret[i] for i, s in enumerate(strategy_names) if s in pw.weights]
        )
        c_indices = [i for i, s in enumerate(strategy_names) if s in pw.weights]

        if len(c_indices) == 0:
            return pw

        c = cov[np.ix_(c_indices, c_indices)]

        pw.expected_return = _portfolio_return(w, e)
        pw.expected_risk = _portfolio_volatility(w, c)
        pw.sharpe_ratio = _portfolio_sharpe(w, e, c)
        return pw

    def calculate_turnover(
        self, old_weights: Dict[str, float], new_weights: Dict[str, float]
    ) -> float:
        all_keys = set(old_weights.keys()) | set(new_weights.keys())
        turnover = 0.0
        for k in all_keys:
            turnover += abs(new_weights.get(k, 0.0) - old_weights.get(k, 0.0))
        return turnover / 2.0

    def apply_constraints(
        self,
        weights: Dict[str, float],
        max_weight: Optional[float] = None,
        min_weight: Optional[float] = None,
    ) -> Dict[str, float]:
        max_w = (
            max_weight
            if max_weight is not None
            else self.config.max_single_strategy_weight
        )
        min_w = (
            min_weight
            if min_weight is not None
            else self.config.min_single_strategy_weight
        )

        constrained = {}
        for k, v in weights.items():
            if k == "_cash":
                constrained[k] = v
                continue
            constrained[k] = max(min_w, min(max_w, v))

        non_cash = {k: v for k, v in constrained.items() if k != "_cash"}
        total = sum(non_cash.values())
        if total > 1e-12:
            cash = constrained.get("_cash", 0.0)
            investable = 1.0 - cash
            for k in non_cash:
                constrained[k] = non_cash[k] / total * investable

        return constrained

    def efficient_frontier(
        self,
        strategy_names: List[str],
        cov_matrix: pd.DataFrame,
        expected_returns: Dict[str, float],
        n_points: int = 20,
    ) -> List[Dict[str, Any]]:
        n = len(strategy_names)
        cov = np.array(
            [[cov_matrix.loc[i, j] for j in strategy_names] for i in strategy_names]
        )
        exp_ret = np.array([expected_returns.get(s, 0.0) for s in strategy_names])

        min_ret = exp_ret.min()
        max_ret = exp_ret.max()
        target_rets = np.linspace(min_ret, max_ret, n_points)

        frontier = []
        for target in target_rets:

            def objective(w):
                return np.dot(w, np.dot(cov, w))

            x0 = np.ones(n) / n
            bounds = [
                (
                    self.config.min_single_strategy_weight,
                    self.config.max_single_strategy_weight,
                )
            ] * n
            constraints = [
                {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
                {"type": "eq", "fun": lambda w, t=target: np.dot(w, exp_ret) - t},
            ]

            result = minimize(
                objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 1000},
            )

            if result.success:
                w = result.x
                ret = np.dot(w, exp_ret)
                vol = np.sqrt(np.dot(w, np.dot(cov, w)))
                frontier.append(
                    {
                        "target_return": target,
                        "actual_return": ret,
                        "volatility": vol,
                        "sharpe": ret / vol if vol > 1e-12 else 0.0,
                        "weights": {
                            s: float(w[i]) for i, s in enumerate(strategy_names)
                        },
                    }
                )

        return frontier

    def max_sharpe_portfolio(
        self,
        strategy_names: List[str],
        cov_matrix: pd.DataFrame,
        expected_returns: Dict[str, float],
        risk_free_rate: float = 0.0,
    ) -> PortfolioWeights:
        n = len(strategy_names)
        cov = np.array(
            [[cov_matrix.loc[i, j] for j in strategy_names] for i in strategy_names]
        )
        exp_ret = np.array([expected_returns.get(s, 0.0) for s in strategy_names])

        def neg_sharpe(w):
            ret = np.dot(w, exp_ret)
            vol = np.sqrt(np.dot(w, np.dot(cov, w)))
            if vol < 1e-12:
                return 1e10
            return -(ret - risk_free_rate) / vol

        x0 = np.ones(n) / n
        bounds = [
            (
                self.config.min_single_strategy_weight,
                self.config.max_single_strategy_weight,
            )
        ] * n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        result = minimize(
            neg_sharpe,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 2000, "ftol": 1e-14},
        )

        weights = _clip_weights(
            result.x,
            self.config.min_single_strategy_weight,
            self.config.max_single_strategy_weight,
        )

        pw = PortfolioWeights(
            weights={s: float(weights[i]) for i, s in enumerate(strategy_names)},
            method="max_sharpe",
            optimization_details={"success": result.success, "iterations": result.nit},
        )
        pw.constraints_applied = True
        return pw

    def minimum_variance_portfolio(
        self,
        strategy_names: List[str],
        cov_matrix: pd.DataFrame,
    ) -> PortfolioWeights:
        n = len(strategy_names)
        cov = np.array(
            [[cov_matrix.loc[i, j] for j in strategy_names] for i in strategy_names]
        )

        def port_var(w):
            return np.dot(w, np.dot(cov, w))

        x0 = np.ones(n) / n
        bounds = [
            (
                self.config.min_single_strategy_weight,
                self.config.max_single_strategy_weight,
            )
        ] * n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        result = minimize(
            port_var,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 2000, "ftol": 1e-14},
        )

        weights = _clip_weights(
            result.x,
            self.config.min_single_strategy_weight,
            self.config.max_single_strategy_weight,
        )

        pw = PortfolioWeights(
            weights={s: float(weights[i]) for i, s in enumerate(strategy_names)},
            method="minimum_variance",
            optimization_details={"success": result.success, "iterations": result.nit},
        )
        pw.constraints_applied = True
        return pw


# ---------------------------------------------------------------------------
# Trade: 交易记录
# ---------------------------------------------------------------------------
@dataclass
class Trade:
    """
    再平衡交易记录

    Attributes:
        strategy_name: 策略名称
        action: 操作 (buy/sell/hold)
        current_weight: 当前权重
        target_weight: 目标权重
        weight_change: 权重变化
        notional_value: 名义金额 (如果提供了总资金)
        reason: 交易原因
    """

    strategy_name: str = ""
    action: str = "hold"
    current_weight: float = 0.0
    target_weight: float = 0.0
    weight_change: float = 0.0
    notional_value: float = 0.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "action": self.action,
            "current_weight": round(self.current_weight, 6),
            "target_weight": round(self.target_weight, 6),
            "weight_change": round(self.weight_change, 6),
            "notional_value": round(self.notional_value, 2),
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"Trade({self.strategy_name}, {self.action}, "
            f"{self.current_weight:.2%} -> {self.target_weight:.2%})"
        )


# ---------------------------------------------------------------------------
# RebalanceEngine: 再平衡引擎
# ---------------------------------------------------------------------------
class RebalanceEngine:
    """
    动态再平衡引擎

    支持三种再平衡触发方式:
    1. periodic: 定期再平衡 (按交易日)
    2. threshold: 阈值触发 (权重偏离超过阈值)
    3. drift: 偏离度触发 (相对目标权重的偏离比例)

    功能:
    - 计算再平衡交易列表
    - 评估是否需要再平衡
    - 计算再平衡成本
    - 跟踪再平衡历史
    """

    def __init__(
        self,
        config: Optional[PortfolioConfig] = None,
    ):
        self.config = config or PortfolioConfig()
        self.rebalance_history: List[Dict[str, Any]] = []

    def should_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        last_rebalance_date: Optional[datetime.date] = None,
        current_date: Optional[datetime.date] = None,
        trading_days_since_rebalance: int = 0,
    ) -> Tuple[bool, str]:
        """
        判断是否需要再平衡

        Args:
            current_weights: 当前权重
            target_weights: 目标权重
            last_rebalance_date: 上次再平衡日期
            current_date: 当前日期
            trading_days_since_rebalance: 距离上次再平衡的交易日数

        Returns:
            (should_rebalance, reason)
        """
        if current_date is None:
            current_date = datetime.date.today()

        periodic, p_reason = self._check_periodic(
            last_rebalance_date, current_date, trading_days_since_rebalance
        )
        if periodic:
            return True, p_reason

        threshold, t_reason = self._check_threshold(current_weights, target_weights)
        if threshold:
            return True, t_reason

        drift, d_reason = self._check_drift(current_weights, target_weights)
        if drift:
            return True, d_reason

        return False, "no trigger met"

    def _check_periodic(
        self,
        last_rebalance_date: Optional[datetime.date],
        current_date: datetime.date,
        trading_days_since_rebalance: int,
    ) -> Tuple[bool, str]:
        if last_rebalance_date is None:
            return True, "first rebalance"

        if trading_days_since_rebalance >= self.config.rebalance_period:
            return (
                True,
                f"periodic: {trading_days_since_rebalance} >= {self.config.rebalance_period} days",
            )

        return False, ""

    def _check_threshold(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
    ) -> Tuple[bool, str]:
        threshold = self.config.rebalance_threshold
        max_deviation = 0.0
        max_dev_strategy = ""

        all_keys = set(current_weights.keys()) | set(target_weights.keys())
        for key in all_keys:
            curr = current_weights.get(key, 0.0)
            tgt = target_weights.get(key, 0.0)
            deviation = abs(curr - tgt)
            if deviation > max_deviation:
                max_deviation = deviation
                max_dev_strategy = key

        if max_deviation > threshold:
            return (
                True,
                f"threshold: {max_dev_strategy} deviation {max_deviation:.2%} > {threshold:.2%}",
            )

        return False, ""

    def _check_drift(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
    ) -> Tuple[bool, str]:
        max_relative_drift = 0.0
        max_drift_strategy = ""

        for key, tgt in target_weights.items():
            if tgt < 1e-12:
                continue
            curr = current_weights.get(key, 0.0)
            relative_drift = abs(curr - tgt) / tgt
            if relative_drift > max_relative_drift:
                max_relative_drift = relative_drift
                max_drift_strategy = key

        drift_threshold = self.config.rebalance_threshold * 2
        if max_relative_drift > drift_threshold:
            return (
                True,
                f"drift: {max_drift_strategy} relative drift {max_relative_drift:.2%} > {drift_threshold:.2%}",
            )

        return False, ""

    def rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        threshold: Optional[float] = None,
        total_capital: float = 0.0,
        reason: str = "",
    ) -> List[Trade]:
        """
        计算再平衡交易列表

        Args:
            current_weights: 当前权重
            target_weights: 目标权重
            threshold: 最小交易阈值 (低于此值的权重变化忽略)
            total_capital: 总资金 (用于计算名义金额)
            reason: 再平衡原因

        Returns:
            list[Trade]
        """
        min_threshold = (
            threshold if threshold is not None else self.config.rebalance_threshold
        )
        trades = []

        all_keys = set(current_weights.keys()) | set(target_weights.keys())
        all_keys.discard("_cash")

        for key in sorted(all_keys):
            curr = current_weights.get(key, 0.0)
            tgt = target_weights.get(key, 0.0)
            change = tgt - curr

            if abs(change) < min_threshold:
                trades.append(
                    Trade(
                        strategy_name=key,
                        action="hold",
                        current_weight=curr,
                        target_weight=tgt,
                        weight_change=change,
                        notional_value=change * total_capital,
                        reason=reason or "within threshold",
                    )
                )
                continue

            action = "buy" if change > 0 else "sell"
            trades.append(
                Trade(
                    strategy_name=key,
                    action=action,
                    current_weight=curr,
                    target_weight=tgt,
                    weight_change=change,
                    notional_value=abs(change) * total_capital,
                    reason=reason or f"{action} to target",
                )
            )

        return trades

    def calculate_rebalance_cost(
        self,
        trades: List[Trade],
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ) -> Dict[str, float]:
        """
        计算再平衡成本

        Args:
            trades: 交易列表
            commission_rate: 佣金率
            slippage_rate: 滑点率

        Returns:
            dict 包含总成本、佣金、滑点
        """
        total_turnover = sum(abs(t.weight_change) for t in trades) / 2.0
        total_commission = total_turnover * commission_rate
        total_slippage = total_turnover * slippage_rate
        total_cost = total_commission + total_slippage

        return {
            "total_turnover": total_turnover,
            "commission": total_commission,
            "slippage": total_slippage,
            "total_cost": total_cost,
            "cost_bps": total_cost * 10000,
            "num_trades": sum(1 for t in trades if t.action != "hold"),
        }

    def execute_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        current_date: Optional[datetime.date] = None,
        total_capital: float = 0.0,
        reason: str = "",
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ) -> Dict[str, Any]:
        """
        执行完整的再平衡流程

        Args:
            current_weights: 当前权重
            target_weights: 目标权重
            current_date: 当前日期
            total_capital: 总资金
            reason: 再平衡原因
            commission_rate: 佣金率
            slippage_rate: 滑点率

        Returns:
            再平衡结果字典
        """
        if current_date is None:
            current_date = datetime.date.today()

        should, trigger_reason = self.should_rebalance(
            current_weights, target_weights, current_date=current_date
        )

        if not should:
            return {
                "rebalanced": False,
                "reason": "no trigger met",
                "trades": [],
                "cost": {},
                "new_weights": current_weights,
            }

        trades = self.rebalance(
            current_weights,
            target_weights,
            total_capital=total_capital,
            reason=reason or trigger_reason,
        )
        cost = self.calculate_rebalance_cost(trades, commission_rate, slippage_rate)

        new_weights = deepcopy(target_weights)

        record = {
            "date": current_date.isoformat(),
            "trigger": trigger_reason,
            "turnover": cost["total_turnover"],
            "cost": cost["total_cost"],
            "num_trades": cost["num_trades"],
        }
        self.rebalance_history.append(record)

        return {
            "rebalanced": True,
            "reason": trigger_reason,
            "trades": [t.to_dict() for t in trades],
            "cost": cost,
            "new_weights": {k: round(v, 6) for k, v in new_weights.items()},
            "history_length": len(self.rebalance_history),
        }

    def get_rebalance_summary(self) -> pd.DataFrame:
        """
        获取再平衡历史汇总

        Returns:
            DataFrame 包含再平衡历史记录
        """
        if not self.rebalance_history:
            return pd.DataFrame()

        df = pd.DataFrame(self.rebalance_history)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def optimize_rebalance_frequency(
        self,
        returns_series: pd.Series,
        target_weights: Dict[str, float],
        current_weights_history: pd.DataFrame,
        commission_rate: float = 0.001,
        periods: Optional[List[int]] = None,
    ) -> Dict[int, Dict[str, float]]:
        """
        优化再平衡频率

        测试不同再平衡周期下的净收益, 找到最优周期

        Args:
            returns_series: 组合收益率序列
            target_weights: 目标权重
            current_weights_history: 历史权重序列 (index=date, columns=strategy)
            commission_rate: 佣金率
            periods: 待测试的周期列表

        Returns:
            dict[period, {gross_return, cost, net_return, sharpe}]
        """
        if periods is None:
            periods = [5, 10, 20, 40, 60]

        results = {}
        for period in periods:
            gross_ret, total_cost, sharpe = self._simulate_rebalance(
                returns_series,
                target_weights,
                current_weights_history,
                period,
                commission_rate,
            )
            results[period] = {
                "gross_return": gross_ret,
                "total_cost": total_cost,
                "net_return": gross_ret - total_cost,
                "sharpe": sharpe,
            }

        return results

    def _simulate_rebalance(
        self,
        returns_series: pd.Series,
        target_weights: Dict[str, float],
        current_weights_history: pd.DataFrame,
        period: int,
        commission_rate: float,
    ) -> Tuple[float, float, float]:
        if len(returns_series) < period:
            return 0.0, 0.0, 0.0

        total_cost = 0.0
        cumulative_return = 1.0
        daily_returns = []
        last_rebalance_idx = 0

        for i in range(len(returns_series)):
            if i - last_rebalance_idx >= period:
                if i < len(current_weights_history):
                    current_w = current_weights_history.iloc[i].to_dict()
                    turnover = (
                        sum(
                            abs(current_w.get(k, 0.0) - v)
                            for k, v in target_weights.items()
                        )
                        / 2.0
                    )
                    total_cost += turnover * commission_rate
                last_rebalance_idx = i

            ret = returns_series.iloc[i]
            daily_returns.append(ret)
            cumulative_return *= 1 + ret

        gross_return = cumulative_return - 1.0

        if len(daily_returns) > 1:
            ret_arr = np.array(daily_returns)
            mean_ret = ret_arr.mean()
            std_ret = ret_arr.std()
            sharpe = (
                (mean_ret / std_ret * math.sqrt(TRADING_DAYS_PER_YEAR))
                if std_ret > 1e-12
                else 0.0
            )
        else:
            sharpe = 0.0

        return gross_return, total_cost, sharpe


# ---------------------------------------------------------------------------
# PortfolioManager: 组合管理器 (统一入口)
# ---------------------------------------------------------------------------
class PortfolioManager:
    """
    多策略组合管理器

    整合优化器和再平衡引擎, 提供一站式组合管理

    使用示例:
        config = PortfolioConfig(
            optimization_method=OptimizationMethod.RISK_PARITY,
            rebalance_period=20,
            max_single_strategy_weight=0.35,
            turnover_penalty=0.01,
        )
        manager = PortfolioManager(config)

        weights = manager.optimize(returns_matrix=rets_df, expected_returns=exp_ret)
        trades = manager.rebalance(current_weights, weights.weights)
        report = manager.full_report(returns_matrix=rets_df)
    """

    def __init__(self, config: Optional[PortfolioConfig] = None):
        self.config = config or PortfolioConfig()
        self.optimizer = PortfolioOptimizer(self.config)
        self.rebalance_engine = RebalanceEngine(self.config)
        self.current_weights: Dict[str, float] = {}
        self.target_weights: Dict[str, float] = {}
        self.last_rebalance_date: Optional[datetime.date] = None

    def optimize(
        self,
        returns_matrix: Optional[pd.DataFrame] = None,
        expected_returns: Optional[Dict[str, float]] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
        weights_history: Optional[Dict[str, float]] = None,
        method: Optional[OptimizationMethod] = None,
        bl_views: Optional[Dict[str, Any]] = None,
        correlation_matrix: Optional[pd.DataFrame] = None,
    ) -> PortfolioWeights:
        result = self.optimizer.optimize(
            weights_history=weights_history or self.current_weights,
            returns_matrix=returns_matrix,
            expected_returns=expected_returns,
            cov_matrix=cov_matrix,
            method=method,
            bl_views=bl_views,
            correlation_matrix=correlation_matrix,
        )
        self.target_weights = result.weights.copy()
        return result

    def rebalance(
        self,
        current_weights: Optional[Dict[str, float]] = None,
        target_weights: Optional[Dict[str, float]] = None,
        total_capital: float = 0.0,
        reason: str = "",
    ) -> Dict[str, Any]:
        curr = current_weights or self.current_weights
        tgt = target_weights or self.target_weights

        result = self.rebalance_engine.execute_rebalance(
            curr, tgt, total_capital=total_capital, reason=reason
        )

        if result["rebalanced"]:
            self.current_weights = result["new_weights"].copy()
            self.last_rebalance_date = datetime.date.today()

        return result

    def check_rebalance(
        self,
        current_weights: Optional[Dict[str, float]] = None,
        target_weights: Optional[Dict[str, float]] = None,
        trading_days_since_rebalance: int = 0,
    ) -> Tuple[bool, str]:
        curr = current_weights or self.current_weights
        tgt = target_weights or self.target_weights
        return self.rebalance_engine.should_rebalance(
            curr,
            tgt,
            last_rebalance_date=self.last_rebalance_date,
            trading_days_since_rebalance=trading_days_since_rebalance,
        )

    def calculate_turnover(
        self,
        old_weights: Optional[Dict[str, float]] = None,
        new_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        old = old_weights or self.current_weights
        new = new_weights or self.target_weights
        return self.optimizer.calculate_turnover(old, new)

    def apply_constraints(
        self,
        weights: Dict[str, float],
        max_weight: Optional[float] = None,
        min_weight: Optional[float] = None,
    ) -> Dict[str, float]:
        return self.optimizer.apply_constraints(weights, max_weight, min_weight)

    def full_report(
        self,
        returns_matrix: pd.DataFrame,
        expected_returns: Optional[Dict[str, float]] = None,
        current_weights: Optional[Dict[str, float]] = None,
        method: Optional[OptimizationMethod] = None,
    ) -> Dict[str, Any]:
        weights_result = self.optimize(
            returns_matrix=returns_matrix,
            expected_returns=expected_returns,
            method=method,
        )

        strategy_names = list(returns_matrix.columns)
        cov = returns_matrix[strategy_names].cov().values * TRADING_DAYS_PER_YEAR
        if expected_returns:
            exp_ret = np.array([expected_returns.get(s, 0.0) for s in strategy_names])
        else:
            exp_ret = np.array(
                [
                    returns_matrix[s].mean() * TRADING_DAYS_PER_YEAR
                    for s in strategy_names
                ]
            )

        frontier = self.optimizer.efficient_frontier(
            strategy_names,
            pd.DataFrame(
                returns_matrix[strategy_names].cov().values,
                columns=strategy_names,
                index=strategy_names,
            ),
            expected_returns or {s: exp_ret[i] for i, s in enumerate(strategy_names)},
        )

        rebalance_info = {}
        if current_weights:
            should, reason = self.check_rebalance(
                current_weights, weights_result.weights
            )
            trades = self.rebalance(current_weights, weights_result.weights)
            rebalance_info = {
                "should_rebalance": should,
                "reason": reason,
                "trades": trades,
            }

        return {
            "optimized_weights": weights_result.to_dict(),
            "expected_return": weights_result.expected_return,
            "expected_risk": weights_result.expected_risk,
            "sharpe_ratio": weights_result.sharpe_ratio,
            "turnover": weights_result.turnover,
            "efficient_frontier": frontier,
            "rebalance": rebalance_info,
        }
