# -*- coding: utf-8 -*-
"""
通用技术指标计算工具
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均"""
    return series.rolling(window=period).mean()


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD 计算

    Returns:
        dif, dea, macd_hist
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    macd_hist = (dif - dea) * 2
    return dif, dea, macd_hist


def boll(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    布林带计算

    Returns:
        upper, mid, lower
    """
    mid = sma(close, period)
    std = close.rolling(window=period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI 计算"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def williams_r(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Williams %R 计算"""
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    wr = -100 * (highest_high - close) / (highest_high - lowest_low)
    return wr


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """ATR 计算"""
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def linear_regression_slope(series: pd.Series, window: int) -> pd.Series:
    """线性回归斜率 (滚动窗口)"""
    x = np.arange(window)

    def _slope(y):
        if len(y) < window:
            return np.nan
        coeffs = np.polyfit(x, y, 1)
        return coeffs[0]

    return series.rolling(window=window).apply(_slope, raw=True)


def rolling_ols_slope(y: pd.Series, x: pd.Series, window: int) -> pd.Series:
    """滚动 OLS 斜率 (y ~ x)"""
    slopes = []
    for i in range(len(y)):
        if i < window - 1:
            slopes.append(np.nan)
            continue
        y_win = y.iloc[i - window + 1 : i + 1].values
        x_win = x.iloc[i - window + 1 : i + 1].values
        coeffs = np.polyfit(x_win, y_win, 1)
        slopes.append(coeffs[0])
    return pd.Series(slopes, index=y.index)


def zscore(series: pd.Series, lookback: int) -> pd.Series:
    """滚动 Z-Score 标准化"""
    mean = series.rolling(window=lookback).mean()
    std = series.rolling(window=lookback).std()
    return (series - mean) / std


def rolling_rank(series: pd.Series, lookback: int, pct: bool = True) -> pd.Series:
    """滚动排名 (百分位)"""

    def _rank(x):
        from scipy.stats import percentileofscore

        return percentileofscore(x, x[-1]) / 100.0

    return series.rolling(window=lookback).apply(_rank, raw=True)


def realized_volatility(
    close: pd.Series, window: int = 20, annualize: bool = True
) -> pd.Series:
    """已实现波动率"""
    log_ret = np.log(close / close.shift(1))
    vol = log_ret.rolling(window=window).std()
    if annualize:
        vol = vol * np.sqrt(252)
    return vol


def turnover_rate(volume: pd.Series, float_shares: pd.Series) -> pd.Series:
    """换手率计算"""
    return volume / float_shares


def momentum(close: pd.Series, period: int = 20) -> pd.Series:
    """动量 (收益率)"""
    return close / close.shift(period) - 1


def correlation_matrix(returns: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """滚动相关系数矩阵"""
    return returns.rolling(window=window).corr()


def diffusion_index(
    returns: pd.DataFrame, weights: Optional[pd.Series] = None
) -> pd.Series:
    """
    扩散指数: ROC > 0 的股票占比 (可加权)

    Args:
        returns: 各股票的收益率 DataFrame (columns=stocks, index=dates)
        weights: 各股票权重 (如流通市值)
    """
    positive = (returns > 0).astype(float)
    if weights is not None:
        positive = positive.multiply(weights, axis=1)
        total_weight = weights.sum()
        return positive.sum(axis=1) / total_weight
    return positive.mean(axis=1)


def winsorize(series: pd.Series, n_std: float = 3.0) -> pd.Series:
    """缩尾处理 (去除极端值)"""
    mean = series.mean()
    std = series.std()
    upper = mean + n_std * std
    lower = mean - n_std * std
    return series.clip(lower=lower, upper=upper)


def slope_r2(
    low: pd.Series, high: pd.Series, window: int = 18
) -> Tuple[pd.Series, pd.Series]:
    """
    计算高低点回归斜率和 R² (RSRS 核心)

    Returns:
        slopes, r2_values
    """
    slopes = []
    r2_values = []

    for i in range(len(low)):
        if i < window - 1:
            slopes.append(np.nan)
            r2_values.append(np.nan)
            continue

        y = high.iloc[i - window + 1 : i + 1].values
        x = low.iloc[i - window + 1 : i + 1].values

        coeffs = np.polyfit(x, y, 1)
        slope = coeffs[0]
        intercept = coeffs[1]

        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = (len(y) - 1) * np.var(y, ddof=1)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        slopes.append(slope)
        r2_values.append(r2)

    return pd.Series(slopes, index=low.index), pd.Series(r2_values, index=low.index)


def weighted_slope_r2(
    low: pd.Series, high: pd.Series, volume: pd.Series, window: int = 18
) -> Tuple[pd.Series, pd.Series]:
    """
    成交量加权的高低点回归斜率和 R² (Vol-RSRS)

    Returns:
        slopes, r2_values
    """
    slopes = []
    r2_values = []

    for i in range(len(low)):
        if i < window - 1:
            slopes.append(np.nan)
            r2_values.append(np.nan)
            continue

        y = high.iloc[i - window + 1 : i + 1].values
        x = low.iloc[i - window + 1 : i + 1].values
        w = volume.iloc[i - window + 1 : i + 1].values
        w = w / w.sum()

        coeffs = np.polyfit(x, y, 1, w=w)
        slope = coeffs[0]
        intercept = coeffs[1]

        y_pred = slope * x + intercept
        ss_res = np.sum(w * (y - y_pred) ** 2)
        ss_tot = (len(y) - 1) * np.var(y, ddof=1)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        slopes.append(slope)
        r2_values.append(r2)

    return pd.Series(slopes, index=low.index), pd.Series(r2_values, index=low.index)
