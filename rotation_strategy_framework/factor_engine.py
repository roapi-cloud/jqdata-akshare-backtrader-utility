# -*- coding: utf-8 -*-
"""
因子引擎: 统一因子计算框架，支持批量向量化计算、缓存、状态持久化

核心类:
- BaseFactor: 因子基类 (name, params, compute, validate)
- MomentumFactors: 动量因子族 (simple, regression, log_reg, bias, kalman)
- AllocationFactors: 配置因子族 (top_n, epo, min_corr, stock_bond, grid)
- TimingFactors: 择时因子族 (rsrs, ma_cross, north_boll, volume_emotion, price_filter, drawdown_tier)
- RiskFactors: 风控因子族 (momentum_change, drawdown, stop_loss, volatility, intraday_stop)
- FactorEngine: 统一因子引擎 (注册、计算、缓存因子结果)

关键修复:
- R² 计算: if var_y < 1e-10: return 0
- 卡尔曼: kalman_filter_step(obs, state, P, R, Q) 持久化 P
- RSRS: slope_history 实例级持久化
- EPO: signal 用动量得分替代均值
"""

import os
import pickle
import logging
import datetime
import warnings
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
FACTOR_CACHE_VERSION = "v1.0.0"
DEFAULT_KALMAN_P = np.eye(2) * 1e4
DEFAULT_KALMAN_R = 1e-2
DEFAULT_KALMAN_Q = np.eye(2) * 1e-6


# ---------------------------------------------------------------------------
# 因子类型枚举
# ---------------------------------------------------------------------------
class FactorType(Enum):
    """因子类型"""

    MOMENTUM = "momentum"
    ALLOCATION = "allocation"
    TIMING = "timing"
    RISK = "risk"


class FactorDirection(Enum):
    """因子方向"""

    HIGHER_BETTER = "higher_better"
    LOWER_BETTER = "lower_better"


# ---------------------------------------------------------------------------
# 因子计算结果
# ---------------------------------------------------------------------------
@dataclass
class FactorResult:
    """因子计算结果"""

    factor_name: str
    factor_type: FactorType
    timestamp: pd.Timestamp
    scores: pd.Series
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.scores, pd.Series):
            self.scores = pd.Series(self.scores)


# ---------------------------------------------------------------------------
# BaseFactor: 因子基类
# ---------------------------------------------------------------------------
class BaseFactor(ABC):
    """
    因子基类

    Attributes:
        name: 因子名称
        factor_type: 因子类型
        params: 因子参数字典
        direction: 因子方向 (越高越好 / 越低越好)
    """

    def __init__(
        self,
        name: str,
        factor_type: FactorType,
        params: Optional[Dict[str, Any]] = None,
        direction: FactorDirection = FactorDirection.HIGHER_BETTER,
    ):
        self.name = name
        self.factor_type = factor_type
        self.params = params or {}
        self.direction = direction
        self._cache: OrderedDict[str, FactorResult] = OrderedDict()
        self._max_cache_size = 50

    @abstractmethod
    def compute(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        date: Optional[pd.Timestamp] = None,
        **kwargs,
    ) -> FactorResult:
        """
        计算因子得分

        Args:
            data: 输入数据 (单标的 DataFrame 或多标的 dict)
            date: 计算日期 (None 表示最新日期)
            **kwargs: 额外参数

        Returns:
            FactorResult
        """
        pass

    def validate(self, data: Union[pd.DataFrame, Dict[str, pd.DataFrame]]) -> bool:
        """
        验证输入数据是否满足因子计算要求

        Args:
            data: 输入数据

        Returns:
            是否有效
        """
        if data is None:
            return False
        if isinstance(data, pd.DataFrame):
            return len(data) > 0
        if isinstance(data, dict):
            return len(data) > 0 and any(len(df) > 0 for df in data.values())
        return False

    def _get_param(self, key: str, default: Any = None, kwargs: Dict = None) -> Any:
        """获取参数 (kwargs 优先)"""
        if kwargs and key in kwargs:
            return kwargs[key]
        return self.params.get(key, default)

    def _cache_result(self, key: str, result: FactorResult) -> None:
        """缓存因子结果 (LRU)"""
        if key in self._cache:
            del self._cache[key]
        while len(self._cache) >= self._max_cache_size:
            self._cache.popitem(last=False)
        self._cache[key] = result

    def _get_cached(self, key: str) -> Optional[FactorResult]:
        """获取缓存结果"""
        return self._cache.get(key)

    def clear_cache(self) -> None:
        """清除因子缓存"""
        self._cache.clear()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', params={self.params})"


# ===================================================================
# 工具函数
# ===================================================================


def compute_r2(y: np.ndarray, y_pred: np.ndarray) -> float:
    """
    计算 R² (决定系数)，已修复除零问题

    Args:
        y: 真实值
        y_pred: 预测值

    Returns:
        R² 值，方差过小时返回 0
    """
    var_y = np.var(y)
    if var_y < 1e-10:
        return 0.0
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    if ss_tot < 1e-10:
        return 0.0
    return 1.0 - ss_res / ss_tot


def linear_regression(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """
    简单线性回归: y = slope * x + intercept

    Returns:
        (slope, intercept, r2)
    """
    n = len(x)
    if n < 2:
        return 0.0, 0.0, 0.0

    x_mean = np.mean(x)
    y_mean = np.mean(y)

    ss_xy = np.sum((x - x_mean) * (y - y_mean))
    ss_xx = np.sum((x - x_mean) ** 2)

    if ss_xx < 1e-10:
        return 0.0, y_mean, 0.0

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    y_pred = slope * x + intercept
    r2 = compute_r2(y, y_pred)

    return slope, intercept, r2


def rolling_regression_slope(close: pd.Series, window: int) -> pd.Series:
    """滚动窗口线性回归斜率 (向量化)"""
    if len(close) < window:
        return pd.Series(np.nan, index=close.index)

    x = np.arange(window)
    x_mean = np.mean(x)
    xx_mean = np.mean(x**2)
    denom = xx_mean - x_mean**2

    if abs(denom) < 1e-10:
        return pd.Series(0.0, index=close.index)

    result = pd.Series(np.nan, index=close.index)
    values = close.values.astype(float)

    for i in range(window - 1, len(values)):
        y_window = values[i - window + 1 : i + 1]
        if np.any(np.isnan(y_window)):
            continue
        y_mean = np.mean(y_window)
        xy_mean = np.mean(x * y_window)
        slope = (xy_mean - x_mean * y_mean) / denom
        result.iloc[i] = slope

    return result


def kalman_filter_step(
    obs: float,
    state: np.ndarray,
    P: np.ndarray,
    R: float,
    Q: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    卡尔曼滤波单步更新 (持久化 P 协方差)

    状态空间模型:
        state = [level, trend]^T
        obs = level + noise

    Args:
        obs: 观测值
        state: 当前状态 [level, trend] (2,)
        P: 当前状态协方差 (2, 2)
        R: 观测噪声方差 (标量)
        Q: 过程噪声协方差 (2, 2)

    Returns:
        (new_state, new_P, innovation)
    """
    H = np.array([[1.0, 0.0]])
    I = np.eye(2)

    # 预测
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    state_pred = F @ state
    P_pred = F @ P @ F.T + Q

    # 更新
    y_pred = H @ state_pred
    innovation = obs - y_pred[0]
    S = H @ P_pred @ H.T + R
    K = (P_pred @ H.T / S[0, 0]).flatten()

    state_new = state_pred + K * innovation
    P_new = (I - np.outer(K, H[0])) @ P_pred

    # 对称化 P
    P_new = (P_new + P_new.T) / 2.0

    return state_new, P_new, innovation


def compute_zscore(series: pd.Series, lookback: int) -> pd.Series:
    """滚动 Z-Score (向量化)"""
    mean = series.rolling(window=lookback, min_periods=max(1, lookback // 2)).mean()
    std = series.rolling(window=lookback, min_periods=max(1, lookback // 2)).std()
    std = std.replace(0, np.nan)
    return (series - mean) / std


def compute_moments(close: pd.Series, periods: List[int]) -> pd.DataFrame:
    """批量计算多周期动量 (向量化)"""
    result = pd.DataFrame(index=close.index)
    for p in periods:
        result[f"mom_{p}"] = close.pct_change(periods)
    return result


# ===================================================================
# MomentumFactors: 动量因子族
# ===================================================================


class MomentumFactors:
    """
    动量因子族

    包含 5 种动量因子:
    - simple: 简单动量 (N 日收益率)
    - regression: 回归动量 (斜率)
    - log_reg: 对数回归动量 (对数价格斜率)
    - bias: 偏离度动量 (价格偏离均线程度)
    - kalman: 卡尔曼滤波动量 (状态估计)
    """

    @staticmethod
    def simple(
        close: pd.DataFrame,
        periods: List[int] = None,
        weights: List[float] = None,
    ) -> pd.DataFrame:
        """
        简单动量因子: 多周期收益率加权

        Args:
            close: 收盘价矩阵 (index=日期, columns=标的)
            periods: 动量周期列表，默认 [5, 10, 20, 60]
            weights: 各周期权重，默认等权

        Returns:
            动量得分矩阵
        """
        if periods is None:
            periods = [5, 10, 20, 60]
        if weights is None:
            weights = [1.0 / len(periods)] * len(periods)

        scores = pd.DataFrame(0.0, index=close.index, columns=close.columns)

        for p, w in zip(periods, weights):
            mom = close.pct_change(p)
            scores += w * mom

        return scores

    @staticmethod
    def regression(
        close: pd.DataFrame,
        window: int = 20,
        annualize: bool = True,
    ) -> pd.DataFrame:
        """
        回归动量因子: 滚动线性回归斜率

        Args:
            close: 收盘价矩阵
            window: 回归窗口
            annualize: 是否年化

        Returns:
            回归斜率矩阵
        """
        slopes = pd.DataFrame(np.nan, index=close.index, columns=close.columns)

        for col in close.columns:
            series = close[col].dropna()
            if len(series) < window:
                continue

            x = np.arange(window)
            x_mean = np.mean(x)
            xx_mean = np.mean(x**2)
            denom = xx_mean - x_mean**2

            if abs(denom) < 1e-10:
                continue

            values = series.values.astype(float)
            slope_arr = np.full(len(series), np.nan)

            for i in range(window - 1, len(values)):
                y_window = values[i - window + 1 : i + 1]
                if np.any(np.isnan(y_window)):
                    continue
                y_mean = np.mean(y_window)
                xy_mean = np.mean(x * y_window)
                slope_arr[i] = (xy_mean - x_mean * y_mean) / denom

            slopes[col].update(pd.Series(slope_arr, index=series.index))

        if annualize:
            slopes *= 252

        return slopes

    @staticmethod
    def log_reg(
        close: pd.DataFrame,
        window: int = 20,
        annualize: bool = True,
    ) -> pd.DataFrame:
        """
        对数回归动量因子: 对数价格滚动回归斜率

        Args:
            close: 收盘价矩阵
            window: 回归窗口
            annualize: 是否年化

        Returns:
            对数斜率矩阵
        """
        log_close = np.log(close.replace(0, np.nan).clip(lower=1e-10))
        slopes = MomentumFactors.regression(log_close, window, annualize=False)

        if annualize:
            slopes *= 252

        return slopes

    @staticmethod
    def bias(
        close: pd.DataFrame,
        ma_periods: List[int] = None,
    ) -> pd.DataFrame:
        """
        偏离度动量因子: 价格偏离移动均线的程度

        Args:
            close: 收盘价矩阵
            ma_periods: 均线周期列表，默认 [5, 10, 20]

        Returns:
            偏离度得分矩阵
        """
        if ma_periods is None:
            ma_periods = [5, 10, 20]

        scores = pd.DataFrame(0.0, index=close.index, columns=close.columns)

        for p in ma_periods:
            ma = close.rolling(window=p, min_periods=1).mean()
            bias = (close - ma) / ma.replace(0, np.nan)
            scores += bias

        scores /= len(ma_periods)
        return scores

    @staticmethod
    def kalman(
        close: pd.DataFrame,
        R: float = None,
        Q: np.ndarray = None,
        P_init: np.ndarray = None,
        return_state: bool = False,
    ) -> Union[pd.DataFrame, Tuple[pd.DataFrame, Dict[str, np.ndarray]]]:
        """
        卡尔曼滤波动量因子: 用卡尔曼滤波估计趋势

        Args:
            close: 收盘价矩阵
            R: 观测噪声方差
            Q: 过程噪声协方差
            P_init: 初始协方差
            return_state: 是否返回最终状态 (用于持久化)

        Returns:
            卡尔曼趋势估计矩阵，或 (矩阵, 状态字典)
        """
        if R is None:
            R = DEFAULT_KALMAN_R
        if Q is None:
            Q = DEFAULT_KALMAN_Q.copy()
        if P_init is None:
            P_init = DEFAULT_KALMAN_P.copy()

        scores = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
        final_states = {}

        for col in close.columns:
            series = close[col].dropna()
            if len(series) < 2:
                continue

            state = np.array([series.iloc[0], 0.0])
            P = P_init.copy()
            trend_arr = np.full(len(series), np.nan)

            for i, obs in enumerate(series.values):
                state, P, _ = kalman_filter_step(obs, state, P, R, Q)
                trend_arr[i] = state[1]

            scores[col].update(pd.Series(trend_arr, index=series.index))
            final_states[col] = {"state": state.copy(), "P": P.copy()}

        if return_state:
            return scores, final_states

        return scores


# ===================================================================
# AllocationFactors: 配置因子族
# ===================================================================


class AllocationFactors:
    """
    资产配置因子族

    包含 5 种配置因子:
    - top_n: Top-N 轮动 (动量排名)
    - epo: 等权重动量组合 (EPO, 用动量得分替代均值)
    - min_corr: 最低相关性组合
    - stock_bond: 股债配置因子
    - grid: 网格配置因子
    """

    @staticmethod
    def top_n(
        momentum_scores: pd.DataFrame,
        n: int = 5,
        min_score: float = None,
    ) -> pd.DataFrame:
        """
        Top-N 轮动因子: 按动量得分选前 N 个

        Args:
            momentum_scores: 动量得分矩阵
            n: 选择数量
            min_score: 最低得分阈值

        Returns:
            选择矩阵 (1=选中, 0=未选中)
        """
        selection = pd.DataFrame(
            0, index=momentum_scores.index, columns=momentum_scores.columns
        )

        for date in momentum_scores.index:
            row = momentum_scores.loc[date]
            valid = row.dropna()

            if min_score is not None:
                valid = valid[valid >= min_score]

            if len(valid) == 0:
                continue

            top = valid.nlargest(n)
            selection.loc[date, top.index] = 1

        return selection

    @staticmethod
    def epo(
        close: pd.DataFrame,
        momentum_periods: List[int] = None,
        risk_aversion: float = 1.0,
        window: int = 60,
    ) -> pd.DataFrame:
        """
        等权重动量组合因子 (EPO)

        核心修复: signal 用动量得分替代均值

        Args:
            close: 收盘价矩阵
            momentum_periods: 动量周期
            risk_aversion: 风险厌恶系数
            window: 协方差估计窗口

        Returns:
            权重矩阵
        """
        if momentum_periods is None:
            momentum_periods = [20, 60]

        # 计算复合动量得分
        mom = MomentumFactors.simple(close, momentum_periods)
        mom = mom.dropna()

        weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)

        for i in range(window, len(mom)):
            date = mom.index[i]
            window_data = close.iloc[max(0, i - window) : i]

            if window_data.empty or len(window_data) < 10:
                continue

            # 计算协方差矩阵
            returns = window_data.pct_change().dropna()
            if returns.empty:
                continue

            cov = returns.cov() * 252
            cov = cov.fillna(0)

            # 核心修复: 用动量得分替代均值
            mu = mom.loc[date].fillna(0)

            # EPO 权重: w = (1/risk_aversion) * cov_inv @ mu
            try:
                cov_inv = np.linalg.inv(cov.values + np.eye(len(cov)) * 1e-6)
                w = (1.0 / risk_aversion) * cov_inv @ mu[cov.columns].values
                # 归一化
                w_pos = np.maximum(w, 0)
                w_sum = w_pos.sum()
                if w_sum > 0:
                    w = w_pos / w_sum
                weights.loc[date, cov.columns] = w
            except np.linalg.LinAlgError:
                # 奇异矩阵，等权
                n_assets = len(cov.columns)
                weights.loc[date, cov.columns] = 1.0 / n_assets

        return weights

    @staticmethod
    def min_corr(
        close: pd.DataFrame,
        window: int = 60,
        n_select: int = None,
    ) -> pd.DataFrame:
        """
        最低相关性组合因子: 选择与其他资产相关性最低的资产

        Args:
            close: 收盘价矩阵
            window: 相关性计算窗口
            n_select: 选择数量，默认全部

        Returns:
            权重矩阵
        """
        returns = close.pct_change().dropna()
        weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)

        for i in range(window, len(returns)):
            date = returns.index[i]
            window_ret = returns.iloc[max(0, i - window) : i]

            if len(window_ret) < 10:
                continue

            corr = window_ret.corr().fillna(0)
            n = len(corr.columns)

            if n_select is None:
                n_select = n

            # 计算每个资产的平均相关性 (排除自身)
            avg_corr = pd.Series(0.0, index=corr.columns)
            for col in corr.columns:
                others = corr[col].drop(col)
                avg_corr[col] = others.mean()

            # 选相关性最低的
            selected = avg_corr.nsmallest(n_select).index
            w = 1.0 / len(selected)
            weights.loc[date, selected] = w

        return weights

    @staticmethod
    def stock_bond(
        stock_close: pd.Series,
        bond_close: pd.Series,
        momentum_period: int = 20,
        vol_window: int = 60,
        risk_budget: float = 0.5,
    ) -> pd.DataFrame:
        """
        股债配置因子: 基于动量和波动率的股债配置

        Args:
            stock_close: 股票价格
            bond_close: 债券价格
            momentum_period: 动量周期
            vol_window: 波动率窗口
            risk_budget: 股票风险预算

        Returns:
            权重 DataFrame (columns: stock, bond)
        """
        df = pd.DataFrame(
            {
                "stock": stock_close,
                "bond": bond_close,
            }
        ).dropna()

        stock_mom = df["stock"].pct_change(momentum_period)
        bond_mom = df["bond"].pct_change(momentum_period)

        stock_vol = df["stock"].pct_change().rolling(vol_window).std() * np.sqrt(252)
        bond_vol = df["bond"].pct_change().rolling(vol_window).std() * np.sqrt(252)

        weights = pd.DataFrame(0.0, index=df.index, columns=["stock", "bond"])

        for i in range(max(momentum_period, vol_window), len(df)):
            date = df.index[i]
            s_mom = stock_mom.iloc[i]
            b_mom = bond_mom.iloc[i]
            s_vol = stock_vol.iloc[i]
            b_vol = bond_vol.iloc[i]

            if pd.isna(s_vol) or pd.isna(b_vol) or s_vol + b_vol < 1e-10:
                weights.loc[date] = [0.5, 0.5]
                continue

            # 风险平价 + 动量倾斜
            s_rp = b_vol / (s_vol + b_vol)
            b_rp = s_vol / (s_vol + b_vol)

            # 动量调整
            mom_diff = s_mom - b_mom
            if pd.isna(mom_diff):
                mom_diff = 0

            tilt = np.clip(mom_diff * 2, -0.3, 0.3)

            w_stock = np.clip(s_rp * risk_budget + (1 - risk_budget) * 0.5 + tilt, 0, 1)
            w_bond = 1 - w_stock

            weights.loc[date] = [w_stock, w_bond]

        return weights

    @staticmethod
    def grid(
        close: pd.DataFrame,
        grid_levels: int = 5,
        rebalance_period: int = 20,
        momentum_window: int = 20,
    ) -> pd.DataFrame:
        """
        网格配置因子: 按动量分档网格配置

        Args:
            close: 收盘价矩阵
            grid_levels: 网格档位数
            rebalance_period: 调仓周期
            momentum_window: 动量窗口

        Returns:
            权重矩阵
        """
        mom = MomentumFactors.simple(close, [momentum_window])
        weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)

        for i in range(momentum_window, len(mom), rebalance_period):
            date = mom.index[i]
            scores = mom.loc[date].dropna()

            if len(scores) == 0:
                continue

            # 分档
            quantiles = pd.qcut(
                scores, q=min(grid_levels, len(scores)), labels=False, duplicates="drop"
            )
            quantiles = pd.Series(quantiles, index=scores.index)

            # 权重 = 档位 / 总档位
            total = quantiles.sum()
            if total > 0:
                w = (quantiles + 1) / (quantiles + 1).sum()
            else:
                w = pd.Series(1.0 / len(scores), index=scores.index)

            weights.loc[date, w.index] = w

            # 向前填充直到下次调仓
            next_idx = min(i + rebalance_period, len(mom))
            for j in range(i + 1, next_idx):
                if j < len(mom):
                    weights.loc[mom.index[j], w.index] = w

        # 前向填充
        weights = weights.replace(0, np.nan).ffill().fillna(0)

        return weights


# ===================================================================
# TimingFactors: 择时因子族
# ===================================================================


class TimingFactors:
    """
    择时因子族

    包含 6 种择时因子:
    - rsrs: RSRS 择时 (支撑阻力相对强度)
    - ma_cross: 均线交叉择时
    - north_boll: 北向资金布林带择时
    - volume_emotion: 成交量情绪择时
    - price_filter: 价格过滤器择时
    - drawdown_tier: 回撤分级择时
    """

    def __init__(self):
        """初始化择时因子 (含状态持久化)"""
        self._rsrs_slope_history: Dict[str, List[float]] = {}
        self._kalman_states: Dict[str, Dict] = {}

    def rsrs(
        self,
        high: pd.Series,
        low: pd.Series,
        N: int = 18,
        M: int = 600,
        buy_threshold: float = 0.7,
        sell_threshold: float = -0.7,
    ) -> pd.DataFrame:
        """
        RSRS 择时因子 (实例级持久化 slope_history)

        Args:
            high: 最高价序列
            low: 最低价序列
            N: 回归窗口
            M: Z-Score 参考历史天数
            buy_threshold: 买入阈值
            sell_threshold: 卖出阈值

        Returns:
            DataFrame with columns: score, signal, slope, r2, zscore
        """
        name = f"rsrs_{N}_{M}"
        if name not in self._rsrs_slope_history:
            self._rsrs_slope_history[name] = []

        slope_history = self._rsrs_slope_history[name]
        slope_history.clear()

        slopes = pd.Series(np.nan, index=high.index)
        r2_values = pd.Series(np.nan, index=high.index)

        for i in range(N - 1, len(high)):
            h = high.iloc[max(0, i - N + 1) : i + 1].values
            l = low.iloc[max(0, i - N + 1) : i + 1].values

            if len(h) < N or len(l) < N:
                continue
            if np.any(np.isnan(h)) or np.any(np.isnan(l)):
                continue

            slope, _, r2 = linear_regression(l, h)
            slopes.iloc[i] = slope
            r2_values.iloc[i] = r2
            slope_history.append(slope)

        # Z-Score
        slope_series = pd.Series(slope_history)
        z = compute_zscore(slope_series, M)

        # RSRS 分数 = Z-Score × R²
        rsrs_score = z * r2_values.reindex(slope_series.index).values

        # 信号
        signal = pd.Series(0, index=high.index)
        valid_mask = rsrs_score.notna()
        signal[valid_mask & (rsrs_score > buy_threshold)] = 1
        signal[valid_mask & (rsrs_score < sell_threshold)] = -1

        result = pd.DataFrame(
            {
                "score": rsrs_score.reindex(high.index),
                "signal": signal,
                "slope": slopes,
                "r2": r2_values,
                "zscore": z.reindex(high.index),
            },
            index=high.index,
        )

        return result

    @staticmethod
    def ma_cross(
        close: pd.Series,
        fast_period: int = 5,
        slow_period: int = 20,
        signal_period: int = 5,
    ) -> pd.DataFrame:
        """
        均线交叉择时因子

        Args:
            close: 收盘价序列
            fast_period: 快线周期
            slow_period: 慢线周期
            signal_period: 信号线周期

        Returns:
            DataFrame with columns: fast_ma, slow_ma, signal, score
        """
        fast_ma = close.rolling(fast_period, min_periods=1).mean()
        slow_ma = close.rolling(slow_period, min_periods=1).mean()

        diff = fast_ma - slow_ma
        signal_line = diff.rolling(signal_period, min_periods=1).mean()

        signal = pd.Series(0, index=close.index)
        signal[diff > signal_line] = 1
        signal[diff < signal_line] = -1

        # 分数: 归一化的均线差
        score = diff / slow_ma.replace(0, np.nan)

        return pd.DataFrame(
            {
                "fast_ma": fast_ma,
                "slow_ma": slow_ma,
                "signal": signal,
                "score": score,
            },
            index=close.index,
        )

    @staticmethod
    def north_boll(
        north_net: pd.Series,
        window: int = 90,
        stdev_n: float = 2.0,
        flow_ma: int = 5,
    ) -> pd.DataFrame:
        """
        北向资金布林带择时因子

        Args:
            north_net: 北向资金净流入序列
            window: 布林带窗口
            stdev_n: 标准差倍数
            flow_ma: 资金流均线周期

        Returns:
            DataFrame with columns: flow_ma, boll_upper, boll_lower, boll_mid, signal, score
        """
        flow_ma_series = north_net.rolling(flow_ma, min_periods=1).mean()
        boll_mid = north_net.rolling(window, min_periods=max(1, window // 3)).mean()
        boll_std = north_net.rolling(window, min_periods=max(1, window // 3)).std()
        boll_upper = boll_mid + stdev_n * boll_std
        boll_lower = boll_mid - stdev_n * boll_std

        signal = pd.Series(0, index=north_net.index)
        signal[flow_ma_series > boll_upper] = 1
        signal[flow_ma_series < boll_lower] = -1

        # 分数: 标准化位置
        score = (flow_ma_series - boll_mid) / boll_std.replace(0, np.nan)
        score = score.clip(-3, 3) / 3.0

        return pd.DataFrame(
            {
                "flow_ma": flow_ma_series,
                "boll_upper": boll_upper,
                "boll_lower": boll_lower,
                "boll_mid": boll_mid,
                "signal": signal,
                "score": score,
            },
            index=north_net.index,
        )

    @staticmethod
    def volume_emotion(
        close: pd.Series,
        volume: pd.Series,
        vol_window: int = 20,
        price_window: int = 10,
    ) -> pd.DataFrame:
        """
        成交量情绪择时因子

        Args:
            close: 收盘价
            volume: 成交量
            vol_window: 成交量均线窗口
            price_window: 价格动量窗口

        Returns:
            DataFrame with columns: vol_ratio, price_mom, emotion, signal, score
        """
        vol_ma = volume.rolling(vol_window, min_periods=1).mean()
        vol_ratio = volume / vol_ma.replace(0, np.nan)

        price_mom = close.pct_change(price_window)

        # 情绪指标: 放量上涨为正，放量下跌为负
        emotion = vol_ratio * price_mom

        # 情绪 Z-Score
        emotion_z = compute_zscore(emotion, vol_window * 2)

        signal = pd.Series(0, index=close.index)
        signal[emotion_z > 1.5] = 1
        signal[emotion_z < -1.5] = -1

        score = emotion_z.clip(-3, 3) / 3.0

        return pd.DataFrame(
            {
                "vol_ratio": vol_ratio,
                "price_mom": price_mom,
                "emotion": emotion,
                "emotion_z": emotion_z,
                "signal": signal,
                "score": score,
            },
            index=close.index,
        )

    @staticmethod
    def price_filter(
        close: pd.Series,
        lookback: int = 250,
        upper_pct: float = 0.8,
        lower_pct: float = 0.2,
    ) -> pd.DataFrame:
        """
        价格过滤器择时因子: 当前价格在历史区间中的位置

        Args:
            close: 收盘价
            lookback: 回溯窗口
            upper_pct: 卖出百分位
            lower_pct: 买入百分位

        Returns:
            DataFrame with columns: price_pct, signal, score
        """
        rolling_max = close.rolling(lookback, min_periods=1).max()
        rolling_min = close.rolling(lookback, min_periods=1).min()
        rolling_range = rolling_max - rolling_min

        price_pct = (close - rolling_min) / rolling_range.replace(0, np.nan)
        price_pct = price_pct.clip(0, 1)

        signal = pd.Series(0, index=close.index)
        signal[price_pct < lower_pct] = 1
        signal[price_pct > upper_pct] = -1

        # 分数: 反转信号 (低位为正，高位为负)
        score = 1 - 2 * price_pct

        return pd.DataFrame(
            {
                "rolling_max": rolling_max,
                "rolling_min": rolling_min,
                "price_pct": price_pct,
                "signal": signal,
                "score": score,
            },
            index=close.index,
        )

    @staticmethod
    def drawdown_tier(
        close: pd.Series,
        windows: List[int] = None,
    ) -> pd.DataFrame:
        """
        回撤分级择时因子: 多周期回撤分级

        Args:
            close: 收盘价
            windows: 回撤计算窗口列表

        Returns:
            DataFrame with columns: dd_short, dd_mid, dd_long, tier, signal, score
        """
        if windows is None:
            windows = [20, 60, 250]

        result = pd.DataFrame(index=close.index)
        rolling_max = {}

        for w in windows:
            rm = close.rolling(w, min_periods=1).max()
            rolling_max[w] = rm
            dd = (close - rm) / rm.replace(0, np.nan)
            result[f"dd_{w}"] = dd

        # 分级: 根据最大回撤深度分档
        max_dd = result.min(axis=1)
        tier = pd.Series(0, index=close.index)
        tier[max_dd > -0.05] = 3
        tier[(max_dd <= -0.05) & (max_dd > -0.10)] = 2
        tier[(max_dd <= -0.10) & (max_dd > -0.20)] = 1
        tier[max_dd <= -0.20] = 0

        signal = pd.Series(0, index=close.index)
        signal[tier >= 3] = 1
        signal[tier <= 1] = -1

        score = tier / 3.0

        result["tier"] = tier
        result["signal"] = signal
        result["score"] = score

        return result

    def get_state(self) -> Dict[str, Any]:
        """获取择时因子状态 (用于持久化)"""
        return {
            "rsrs_slope_history": dict(self._rsrs_slope_history),
            "kalman_states": dict(self._kalman_states),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        """恢复择时因子状态"""
        if "rsrs_slope_history" in state:
            self._rsrs_slope_history = state["rsrs_slope_history"]
        if "kalman_states" in state:
            self._kalman_states = state["kalman_states"]


# ===================================================================
# RiskFactors: 风控因子族
# ===================================================================


class RiskFactors:
    """
    风控因子族

    包含 6 种风控因子:
    - momentum_change: 动量变化率风控
    - drawdown: 回撤风控
    - stop_loss: 止损风控
    - volatility: 波动率风控
    - intraday_stop: 日内止损风控
    - correlation_break: 相关性破裂风控
    """

    @staticmethod
    def momentum_change(
        close: pd.DataFrame,
        short_window: int = 5,
        long_window: int = 20,
        threshold: float = 0.05,
    ) -> pd.DataFrame:
        """
        动量变化率风控因子: 短期动量相对长期动量的变化

        Args:
            close: 收盘价矩阵
            short_window: 短期窗口
            long_window: 长期窗口
            threshold: 变化阈值

        Returns:
            DataFrame with columns: mom_change, risk_flag, risk_score
        """
        short_mom = close.pct_change(short_window)
        long_mom = close.pct_change(long_window)

        mom_change = short_mom - long_mom

        risk_flag = pd.DataFrame(0, index=close.index, columns=close.columns)
        risk_flag[mom_change < -threshold] = 1

        # 风险分数: 负值越大风险越高
        risk_score = -mom_change.clip(-0.5, 0.5) / 0.5

        return pd.DataFrame(
            {
                "mom_change": mom_change.stack(),
                "risk_flag": risk_flag.stack(),
                "risk_score": risk_score.stack(),
            }
        )

    @staticmethod
    def drawdown(
        close: pd.DataFrame,
        window: int = 250,
        warning_level: float = 0.10,
        stop_level: float = 0.20,
    ) -> pd.DataFrame:
        """
        回撤风控因子

        Args:
            close: 收盘价矩阵
            window: 回撤计算窗口
            warning_level: 预警回撤水平
            stop_level: 止损回撤水平

        Returns:
            DataFrame with columns: drawdown, risk_level, risk_score
        """
        rolling_max = close.rolling(window, min_periods=1).max()
        dd = (close - rolling_max) / rolling_max.replace(0, np.nan)
        dd = dd.clip(-1, 0)

        risk_level = pd.DataFrame(0, index=close.index, columns=close.columns)
        risk_level[dd < -stop_level] = 2
        risk_level[(dd < -warning_level) & (dd >= -stop_level)] = 1

        risk_score = (-dd).clip(0, 1)

        return pd.DataFrame(
            {
                "drawdown": dd.stack(),
                "risk_level": risk_level.stack(),
                "risk_score": risk_score.stack(),
            }
        )

    @staticmethod
    def stop_loss(
        close: pd.DataFrame,
        entry_price: Optional[pd.DataFrame] = None,
        stop_pct: float = 0.08,
        trailing_pct: float = 0.05,
    ) -> pd.DataFrame:
        """
        止损风控因子: 固定止损 + 移动止损

        Args:
            close: 收盘价矩阵
            entry_price: 入场价格矩阵 (None 则用滚动最高价)
            stop_pct: 固定止损比例
            trailing_pct: 移动止损比例

        Returns:
            DataFrame with columns: stop_price, trailing_stop, triggered, risk_score
        """
        if entry_price is None:
            entry_price = close.rolling(20, min_periods=1).max()

        rolling_max = close.rolling(20, min_periods=1).max()

        stop_price = entry_price * (1 - stop_pct)
        trailing_stop = rolling_max * (1 - trailing_pct)

        triggered = close < stop_price
        trailing_triggered = close < trailing_stop

        risk_score = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        risk_score[trailing_triggered] = 0.5
        risk_score[triggered] = 1.0

        return pd.DataFrame(
            {
                "stop_price": stop_price.stack(),
                "trailing_stop": trailing_stop.stack(),
                "triggered": triggered.stack(),
                "trailing_triggered": trailing_triggered.stack(),
                "risk_score": risk_score.stack(),
            }
        )

    @staticmethod
    def volatility(
        close: pd.DataFrame,
        window: int = 20,
        vol_threshold: float = 0.03,
        vol_spike_threshold: float = 2.0,
    ) -> pd.DataFrame:
        """
        波动率风控因子

        Args:
            close: 收盘价矩阵
            window: 波动率计算窗口
            vol_threshold: 日波动率阈值
            vol_spike_threshold: 波动率突增倍数

        Returns:
            DataFrame with columns: volatility, vol_ratio, risk_flag, risk_score
        """
        returns = close.pct_change()
        vol = returns.rolling(window, min_periods=1).std() * np.sqrt(252)

        vol_ma = vol.rolling(window * 3, min_periods=1).mean()
        vol_ratio = vol / vol_ma.replace(0, np.nan)

        risk_flag = pd.DataFrame(0, index=close.index, columns=close.columns)
        risk_flag[vol > vol_threshold] = 1
        risk_flag[vol_ratio > vol_spike_threshold] = 2

        risk_score = vol.clip(0, 1)

        return pd.DataFrame(
            {
                "volatility": vol.stack(),
                "vol_ratio": vol_ratio.stack(),
                "risk_flag": risk_flag.stack(),
                "risk_score": risk_score.stack(),
            }
        )

    @staticmethod
    def intraday_stop(
        high: pd.DataFrame,
        low: pd.DataFrame,
        close: pd.DataFrame,
        intraday_threshold: float = 0.05,
        close_weak_threshold: float = 0.3,
    ) -> pd.DataFrame:
        """
        日内止损风控因子: 日内大幅波动 + 收盘弱势

        Args:
            high: 最高价矩阵
            low: 最低价矩阵
            close: 收盘价矩阵
            intraday_threshold: 日内波幅阈值
            close_weak_threshold: 收盘位置弱势阈值

        Returns:
            DataFrame with columns: intraday_range, close_position, risk_flag, risk_score
        """
        intraday_range = (high - low) / close.replace(0, np.nan)

        close_position = (close - low) / (high - low).replace(0, np.nan)
        close_position = close_position.clip(0, 1)

        risk_flag = pd.DataFrame(0, index=close.index, columns=close.columns)
        risk_flag[intraday_range > intraday_threshold] = 1
        risk_flag[
            (intraday_range > intraday_threshold * 0.5)
            & (close_position < close_weak_threshold)
        ] = 2

        risk_score = intraday_range * (1 - close_position)
        risk_score = risk_score.clip(0, 1)

        return pd.DataFrame(
            {
                "intraday_range": intraday_range.stack(),
                "close_position": close_position.stack(),
                "risk_flag": risk_flag.stack(),
                "risk_score": risk_score.stack(),
            }
        )

    @staticmethod
    def correlation_break(
        close: pd.DataFrame,
        window_short: int = 20,
        window_long: int = 60,
        break_threshold: float = 0.3,
    ) -> pd.DataFrame:
        """
        相关性破裂风控因子: 短期相关性偏离长期相关性

        Args:
            close: 收盘价矩阵
            window_short: 短期窗口
            window_long: 长期窗口
            break_threshold: 破裂阈值

        Returns:
            DataFrame with columns: corr_diff, risk_flag, risk_score
        """
        returns = close.pct_change().dropna()

        risk_flags = pd.DataFrame(0, index=close.index, columns=close.columns)
        risk_scores = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        corr_diffs = {}

        for i in range(window_long, len(returns)):
            date = returns.index[i]
            short_ret = returns.iloc[max(0, i - window_short) : i]
            long_ret = returns.iloc[max(0, i - window_long) : i]

            if len(short_ret) < window_short // 2 or len(long_ret) < window_long // 2:
                continue

            short_corr = short_ret.corr().fillna(0)
            long_corr = long_ret.corr().fillna(0)

            diff = (short_corr - long_corr).abs()

            for col in close.columns:
                avg_diff = diff[col].drop(col, errors="ignore").mean()
                corr_diffs[(date, col)] = avg_diff

                if avg_diff > break_threshold:
                    risk_flags.loc[date, col] = 1
                    risk_scores.loc[date, col] = min(avg_diff, 1.0)

        corr_diff_series = pd.Series(corr_diffs)

        return pd.DataFrame(
            {
                "corr_diff": corr_diff_series,
                "risk_flag": risk_flags.stack(),
                "risk_score": risk_scores.stack(),
            }
        )


# ===================================================================
# FactorEngine: 统一因子引擎
# ===================================================================


class FactorEngine:
    """
    统一因子引擎

    功能:
    - 注册因子
    - 批量计算因子
    - 缓存因子结果
    - 因子组合得分
    - 状态持久化

    使用示例:
        engine = FactorEngine()
        engine.register_factor("mom_simple", MomentumFactor("mom_simple", ...))
        results = engine.compute_all(data, date="2024-01-01")
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        初始化因子引擎

        Args:
            cache_dir: 因子缓存目录
        """
        self._factors: Dict[str, BaseFactor] = {}
        self._factor_groups: Dict[FactorType, List[str]] = {ft: [] for ft in FactorType}
        self._result_cache: OrderedDict[str, FactorResult] = OrderedDict()
        self._max_result_cache = 200
        self._timing_factors = TimingFactors()
        self._cache_dir = cache_dir

        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def register_factor(self, name: str, factor: BaseFactor) -> None:
        """
        注册因子

        Args:
            name: 因子名称 (唯一标识)
            factor: 因子实例
        """
        self._factors[name] = factor
        self._factor_groups[factor.factor_type].append(name)
        logger.info(f"注册因子: {name} (type={factor.factor_type.value})")

    def register_momentum_factors(
        self,
        periods: List[int] = None,
        regression_window: int = 20,
        ma_periods: List[int] = None,
    ) -> None:
        """批量注册动量因子族"""
        if periods is None:
            periods = [5, 10, 20, 60]

        class _SimpleMom(BaseFactor):
            def __init__(self):
                super().__init__(
                    "mom_simple", FactorType.MOMENTUM, {"periods": periods}
                )

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]] if isinstance(data, pd.DataFrame) else data
                scores = MomentumFactors.simple(close, periods)
                ts = date or scores.index[-1]
                return FactorResult(self.name, self.factor_type, ts, scores.loc[ts])

        class _RegMom(BaseFactor):
            def __init__(self):
                super().__init__(
                    "mom_regression", FactorType.MOMENTUM, {"window": regression_window}
                )

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                scores = MomentumFactors.regression(close, regression_window)
                ts = date or scores.index[-1]
                return FactorResult(self.name, self.factor_type, ts, scores.loc[ts])

        class _LogRegMom(BaseFactor):
            def __init__(self):
                super().__init__(
                    "mom_log_reg", FactorType.MOMENTUM, {"window": regression_window}
                )

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                scores = MomentumFactors.log_reg(close, regression_window)
                ts = date or scores.index[-1]
                return FactorResult(self.name, self.factor_type, ts, scores.loc[ts])

        class _BiasMom(BaseFactor):
            def __init__(self):
                super().__init__(
                    "mom_bias",
                    FactorType.MOMENTUM,
                    {"ma_periods": ma_periods or [5, 10, 20]},
                )

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                mp = ma_periods or [5, 10, 20]
                scores = MomentumFactors.bias(close, mp)
                ts = date or scores.index[-1]
                return FactorResult(self.name, self.factor_type, ts, scores.loc[ts])

        class _KalmanMom(BaseFactor):
            def __init__(self):
                super().__init__("mom_kalman", FactorType.MOMENTUM, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                scores = MomentumFactors.kalman(close)
                ts = date or scores.index[-1]
                return FactorResult(self.name, self.factor_type, ts, scores.loc[ts])

        self.register_factor("mom_simple", _SimpleMom())
        self.register_factor("mom_regression", _RegMom())
        self.register_factor("mom_log_reg", _LogRegMom())
        self.register_factor("mom_bias", _BiasMom())
        self.register_factor("mom_kalman", _KalmanMom())

    def register_allocation_factors(self) -> None:
        """批量注册配置因子族"""

        class _TopN(BaseFactor):
            def __init__(self):
                super().__init__("alloc_top_n", FactorType.ALLOCATION, {"n": 5})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                mom = MomentumFactors.simple(close)
                ts = date or mom.index[-1]
                sel = AllocationFactors.top_n(mom, n=5)
                return FactorResult(self.name, self.factor_type, ts, sel.loc[ts])

        class _EPO(BaseFactor):
            def __init__(self):
                super().__init__("alloc_epo", FactorType.ALLOCATION, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                w = AllocationFactors.epo(close)
                ts = date or w.index[-1]
                return FactorResult(self.name, self.factor_type, ts, w.loc[ts])

        class _MinCorr(BaseFactor):
            def __init__(self):
                super().__init__("alloc_min_corr", FactorType.ALLOCATION, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                w = AllocationFactors.min_corr(close)
                ts = date or w.index[-1]
                return FactorResult(self.name, self.factor_type, ts, w.loc[ts])

        class _StockBond(BaseFactor):
            def __init__(self):
                super().__init__("alloc_stock_bond", FactorType.ALLOCATION, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict) and len(data) >= 2:
                    symbols = list(data.keys())
                    stock_close = data[symbols[0]]["close"]
                    bond_close = data[symbols[1]]["close"]
                else:
                    stock_close = data.iloc[:, 0]
                    bond_close = (
                        data.iloc[:, 1] if len(data.columns) > 1 else data.iloc[:, 0]
                    )
                w = AllocationFactors.stock_bond(stock_close, bond_close)
                ts = date or w.index[-1]
                return FactorResult(self.name, self.factor_type, ts, w.loc[ts])

        class _Grid(BaseFactor):
            def __init__(self):
                super().__init__("alloc_grid", FactorType.ALLOCATION, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                w = AllocationFactors.grid(close)
                ts = date or w.index[-1]
                return FactorResult(self.name, self.factor_type, ts, w.loc[ts])

        self.register_factor("alloc_top_n", _TopN())
        self.register_factor("alloc_epo", _EPO())
        self.register_factor("alloc_min_corr", _MinCorr())
        self.register_factor("alloc_stock_bond", _StockBond())
        self.register_factor("alloc_grid", _Grid())

    def register_timing_factors(self) -> None:
        """批量注册择时因子族"""

        class _RSRS(BaseFactor):
            def __init__(self, engine):
                super().__init__("timing_rsrs", FactorType.TIMING, {"N": 18, "M": 600})
                self._engine = engine

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    first = list(data.values())[0]
                else:
                    first = data
                result = self._engine._timing_factors.rsrs(first["high"], first["low"])
                ts = date or result.index[-1]
                return FactorResult(self.name, self.factor_type, ts, result.loc[ts])

        class _MACross(BaseFactor):
            def __init__(self):
                super().__init__("timing_ma_cross", FactorType.TIMING, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    first = list(data.values())[0]
                else:
                    first = data
                result = TimingFactors.ma_cross(first["close"])
                ts = date or result.index[-1]
                return FactorResult(self.name, self.factor_type, ts, result.loc[ts])

        class _NorthBoll(BaseFactor):
            def __init__(self):
                super().__init__("timing_north_boll", FactorType.TIMING, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    first = list(data.values())[0]
                else:
                    first = data
                if "north_net" in first.columns:
                    result = TimingFactors.north_boll(first["north_net"])
                else:
                    result = pd.DataFrame({"signal": 0, "score": 0}, index=first.index)
                ts = date or result.index[-1]
                return FactorResult(self.name, self.factor_type, ts, result.loc[ts])

        class _VolumeEmotion(BaseFactor):
            def __init__(self):
                super().__init__("timing_volume_emotion", FactorType.TIMING, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    first = list(data.values())[0]
                else:
                    first = data
                result = TimingFactors.volume_emotion(first["close"], first["volume"])
                ts = date or result.index[-1]
                return FactorResult(self.name, self.factor_type, ts, result.loc[ts])

        class _PriceFilter(BaseFactor):
            def __init__(self):
                super().__init__("timing_price_filter", FactorType.TIMING, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    first = list(data.values())[0]
                else:
                    first = data
                result = TimingFactors.price_filter(first["close"])
                ts = date or result.index[-1]
                return FactorResult(self.name, self.factor_type, ts, result.loc[ts])

        class _DrawdownTier(BaseFactor):
            def __init__(self):
                super().__init__("timing_drawdown_tier", FactorType.TIMING, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    first = list(data.values())[0]
                else:
                    first = data
                result = TimingFactors.drawdown_tier(first["close"])
                ts = date or result.index[-1]
                return FactorResult(self.name, self.factor_type, ts, result.loc[ts])

        self.register_factor("timing_rsrs", _RSRS(self))
        self.register_factor("timing_ma_cross", _MACross())
        self.register_factor("timing_north_boll", _NorthBoll())
        self.register_factor("timing_volume_emotion", _VolumeEmotion())
        self.register_factor("timing_price_filter", _PriceFilter())
        self.register_factor("timing_drawdown_tier", _DrawdownTier())

    def register_risk_factors(self) -> None:
        """批量注册风控因子族"""

        class _MomChange(BaseFactor):
            def __init__(self):
                super().__init__("risk_momentum_change", FactorType.RISK, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                result = RiskFactors.momentum_change(close)
                ts = date or close.index[-1]
                scores = (
                    result.xs("risk_score", level=1).loc[ts]
                    if "risk_score" in result.index.get_level_values(1)
                    else pd.Series(0, index=close.columns)
                )
                return FactorResult(self.name, self.factor_type, ts, scores)

        class _DrawdownRisk(BaseFactor):
            def __init__(self):
                super().__init__("risk_drawdown", FactorType.RISK, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                result = RiskFactors.drawdown(close)
                ts = date or close.index[-1]
                scores = (
                    result.xs("risk_score", level=1).loc[ts]
                    if "risk_score" in result.index.get_level_values(1)
                    else pd.Series(0, index=close.columns)
                )
                return FactorResult(self.name, self.factor_type, ts, scores)

        class _StopLoss(BaseFactor):
            def __init__(self):
                super().__init__("risk_stop_loss", FactorType.RISK, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                result = RiskFactors.stop_loss(close)
                ts = date or close.index[-1]
                scores = (
                    result.xs("risk_score", level=1).loc[ts]
                    if "risk_score" in result.index.get_level_values(1)
                    else pd.Series(0, index=close.columns)
                )
                return FactorResult(self.name, self.factor_type, ts, scores)

        class _Volatility(BaseFactor):
            def __init__(self):
                super().__init__("risk_volatility", FactorType.RISK, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                result = RiskFactors.volatility(close)
                ts = date or close.index[-1]
                scores = (
                    result.xs("risk_score", level=1).loc[ts]
                    if "risk_score" in result.index.get_level_values(1)
                    else pd.Series(0, index=close.columns)
                )
                return FactorResult(self.name, self.factor_type, ts, scores)

        class _IntradayStop(BaseFactor):
            def __init__(self):
                super().__init__("risk_intraday_stop", FactorType.RISK, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    high = pd.DataFrame(
                        {k: v["high"] for k, v in data.items() if "high" in v.columns}
                    )
                    low = pd.DataFrame(
                        {k: v["low"] for k, v in data.items() if "low" in v.columns}
                    )
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    high = data[["high"]]
                    low = data[["low"]]
                    close = data[["close"]]
                result = RiskFactors.intraday_stop(high, low, close)
                ts = date or close.index[-1]
                scores = (
                    result.xs("risk_score", level=1).loc[ts]
                    if "risk_score" in result.index.get_level_values(1)
                    else pd.Series(0, index=close.columns)
                )
                return FactorResult(self.name, self.factor_type, ts, scores)

        class _CorrBreak(BaseFactor):
            def __init__(self):
                super().__init__("risk_correlation_break", FactorType.RISK, {})

            def compute(self, data, date=None, **kwargs):
                if isinstance(data, dict):
                    close = pd.DataFrame(
                        {k: v["close"] for k, v in data.items() if "close" in v.columns}
                    )
                else:
                    close = data[["close"]]
                result = RiskFactors.correlation_break(close)
                ts = date or close.index[-1]
                scores = (
                    result.xs("risk_score", level=1).loc[ts]
                    if "risk_score" in result.index.get_level_values(1)
                    else pd.Series(0, index=close.columns)
                )
                return FactorResult(self.name, self.factor_type, ts, scores)

        self.register_factor("risk_momentum_change", _MomChange())
        self.register_factor("risk_drawdown", _DrawdownRisk())
        self.register_factor("risk_stop_loss", _StopLoss())
        self.register_factor("risk_volatility", _Volatility())
        self.register_factor("risk_intraday_stop", _IntradayStop())
        self.register_factor("risk_correlation_break", _CorrBreak())

    def compute_factor(
        self,
        name: str,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        date: Optional[pd.Timestamp] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> FactorResult:
        """
        计算单个因子

        Args:
            name: 因子名称
            data: 输入数据
            date: 计算日期
            use_cache: 是否使用缓存
            **kwargs: 额外参数

        Returns:
            FactorResult
        """
        if name not in self._factors:
            raise ValueError(f"因子 '{name}' 未注册")

        factor = self._factors[name]

        # 缓存键
        cache_key = f"{name}_{date}"

        if use_cache:
            cached = factor._get_cached(cache_key)
            if cached is not None:
                return cached

        # 验证数据
        if not factor.validate(data):
            raise ValueError(f"因子 '{name}' 数据验证失败")

        # 计算
        result = factor.compute(data, date=date, **kwargs)

        # 缓存
        factor._cache_result(cache_key, result)
        self._cache_result(cache_key, result)

        return result

    def compute_all(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        date: Optional[pd.Timestamp] = None,
        factor_names: Optional[List[str]] = None,
        factor_type: Optional[FactorType] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> Dict[str, FactorResult]:
        """
        批量计算因子

        Args:
            data: 输入数据
            date: 计算日期
            factor_names: 指定因子列表 (None 表示全部)
            factor_type: 按类型过滤
            use_cache: 是否使用缓存
            **kwargs: 额外参数

        Returns:
            dict[因子名, FactorResult]
        """
        if factor_names:
            names = factor_names
        elif factor_type:
            names = self._factor_groups.get(factor_type, [])
        else:
            names = list(self._factors.keys())

        results = {}
        for name in names:
            try:
                results[name] = self.compute_factor(
                    name, data, date, use_cache, **kwargs
                )
            except Exception as e:
                logger.warning(f"因子 '{name}' 计算失败: {e}")
                results[name] = None

        return results

    def compute_composite_score(
        self,
        results: Dict[str, FactorResult],
        weights: Optional[Dict[str, float]] = None,
        exclude_risk: bool = True,
    ) -> pd.Series:
        """
        计算复合因子得分

        Args:
            results: 因子计算结果字典
            weights: 因子权重 (None 表示等权)
            exclude_risk: 是否排除风控因子 (风控因子作为惩罚项)

        Returns:
            复合得分 Series
        """
        score_df = pd.DataFrame()

        for name, result in results.items():
            if result is None:
                continue

            factor = self._factors.get(name)
            if factor is None:
                continue

            scores = result.scores.copy()

            # 风控因子取反 (作为惩罚)
            if factor.factor_type == FactorType.RISK:
                scores = -scores

            score_df[name] = scores

        if score_df.empty:
            return pd.Series(dtype=float)

        # 标准化 (z-score)
        score_std = (score_df - score_df.mean()) / score_df.std().replace(0, np.nan)
        score_std = score_std.fillna(0)

        # 加权
        if weights:
            w = pd.Series(weights).reindex(score_std.columns).fillna(0)
            w = w / w.sum() if w.sum() > 0 else pd.Series(1.0 / len(w), index=w.index)
        else:
            w = pd.Series(1.0 / len(score_std.columns), index=score_std.columns)

        composite = score_std @ w

        return composite

    def _cache_result(self, key: str, result: FactorResult) -> None:
        """缓存引擎级结果"""
        if key in self._result_cache:
            del self._result_cache[key]
        while len(self._result_cache) >= self._max_result_cache:
            self._result_cache.popitem(last=False)
        self._result_cache[key] = result

    def save_state(self, path: Optional[str] = None) -> str:
        """
        保存引擎状态 (卡尔曼 P 协方差、RSRS 历史等)

        Args:
            path: 保存路径 (None 则用默认路径)

        Returns:
            保存路径
        """
        if path is None:
            if self._cache_dir:
                path = os.path.join(self._cache_dir, "factor_engine_state.pkl")
            else:
                path = "factor_engine_state.pkl"

        state = {
            "timing_factors": self._timing_factors.get_state(),
            "timestamp": datetime.datetime.now().isoformat(),
            "factor_count": len(self._factors),
        }

        # 保存卡尔曼状态
        kalman_states = {}
        for name, factor in self._factors.items():
            if hasattr(factor, "_kalman_states"):
                kalman_states[name] = factor._kalman_states

        state["kalman_states"] = kalman_states

        with open(path, "wb") as f:
            pickle.dump(state, f)

        logger.info(f"引擎状态已保存: {path}")
        return path

    def load_state(self, path: Optional[str] = None) -> bool:
        """
        加载引擎状态

        Args:
            path: 状态文件路径

        Returns:
            是否成功
        """
        if path is None:
            if self._cache_dir:
                path = os.path.join(self._cache_dir, "factor_engine_state.pkl")
            else:
                path = "factor_engine_state.pkl"

        if not os.path.exists(path):
            logger.warning(f"状态文件不存在: {path}")
            return False

        try:
            with open(path, "rb") as f:
                state = pickle.load(f)

            if "timing_factors" in state:
                self._timing_factors.set_state(state["timing_factors"])

            if "kalman_states" in state:
                for name, k_states in state["kalman_states"].items():
                    factor = self._factors.get(name)
                    if factor and hasattr(factor, "_kalman_states"):
                        factor._kalman_states = k_states

            logger.info(f"引擎状态已加载: {path}")
            return True
        except Exception as e:
            logger.error(f"加载引擎状态失败: {e}")
            return False

    def get_factor_info(self) -> pd.DataFrame:
        """获取所有注册因子信息"""
        info = []
        for name, factor in self._factors.items():
            info.append(
                {
                    "name": name,
                    "type": factor.factor_type.value,
                    "direction": factor.direction.value,
                    "params": factor.params,
                    "cached": len(factor._cache),
                }
            )
        return pd.DataFrame(info)

    def clear_all_cache(self) -> None:
        """清除所有缓存"""
        for factor in self._factors.values():
            factor.clear_cache()
        self._result_cache.clear()

    @property
    def factor_names(self) -> List[str]:
        """所有已注册因子名称"""
        return list(self._factors.keys())

    @property
    def factor_count(self) -> int:
        """已注册因子数量"""
        return len(self._factors)

    def __repr__(self) -> str:
        return f"FactorEngine(factors={self.factor_count}, cache={len(self._result_cache)})"


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


def create_engine(
    cache_dir: Optional[str] = None,
    register_all: bool = True,
) -> FactorEngine:
    """
    创建因子引擎 (工厂函数)

    Args:
        cache_dir: 缓存目录
        register_all: 是否注册全部因子

    Returns:
        FactorEngine 实例
    """
    engine = FactorEngine(cache_dir=cache_dir)

    if register_all:
        engine.register_momentum_factors()
        engine.register_allocation_factors()
        engine.register_timing_factors()
        engine.register_risk_factors()

    return engine


# ---------------------------------------------------------------------------
# 使用示例
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 创建引擎
    engine = create_engine(cache_dir="./factor_cache")
    print(f"引擎: {engine}")
    print(f"因子信息:\n{engine.get_factor_info()}")

    # 生成模拟数据
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=300, freq="B")
    symbols = ["000300", "000905", "000852", "000001"]

    data_dict = {}
    for sym in symbols:
        close = 100 * np.cumprod(1 + np.random.randn(300) * 0.01)
        high = close * (1 + np.abs(np.random.randn(300) * 0.005))
        low = close * (1 - np.abs(np.random.randn(300) * 0.005))
        volume = np.random.randint(1e6, 1e8, 300).astype(float)

        data_dict[sym] = pd.DataFrame(
            {
                "open": close * (1 + np.random.randn(300) * 0.002),
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=dates,
        )

    # 批量计算动量因子
    print("\n" + "=" * 60)
    print("批量计算动量因子")
    print("=" * 60)

    mom_results = engine.compute_all(
        data_dict,
        factor_type=FactorType.MOMENTUM,
        date=dates[-1],
    )

    for name, result in mom_results.items():
        if result is not None:
            print(f"\n{name}:")
            print(result.scores)

    # 计算择时因子
    print("\n" + "=" * 60)
    print("计算择时因子 (RSRS)")
    print("=" * 60)

    timing_results = engine.compute_all(
        data_dict,
        factor_type=FactorType.TIMING,
        date=dates[-1],
    )

    for name, result in timing_results.items():
        if result is not None:
            print(f"\n{name}:")
            print(result.scores)

    # 复合得分
    print("\n" + "=" * 60)
    print("复合因子得分")
    print("=" * 60)

    all_results = engine.compute_all(data_dict, date=dates[-1])
    composite = engine.compute_composite_score(all_results)
    print(f"\n复合得分:\n{composite}")

    # 保存/加载状态
    print("\n" + "=" * 60)
    print("状态持久化")
    print("=" * 60)

    saved_path = engine.save_state()
    print(f"状态已保存: {saved_path}")

    new_engine = create_engine(cache_dir="./factor_cache", register_all=True)
    loaded = new_engine.load_state()
    print(f"状态加载: {loaded}")
