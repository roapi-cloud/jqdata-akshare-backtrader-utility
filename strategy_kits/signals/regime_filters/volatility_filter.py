"""
波动率状态计算

来源：
- C-VIX 中国版编制手册（简化实现，无期权数据时退化为历史波动率/ATR）
- 聚宽558/27 中证500指增+CTA（ATR 波动率信号）
"""
from typing import Dict, Optional
import pandas as pd
import numpy as np

from .contract import SubSignal


def calc_volatility_regime(
    market_data: pd.DataFrame,
    config: Dict,
    date: str,
) -> Optional[SubSignal]:
    """
    计算波动率状态。

    当前为简化版本（method='atr_approx'）：
    使用 short_window ATR / long_window ATR 作为波动率放大倍数。
    若市场数据中存在 'vix' 或 'volatility' 列，可直接读取。
    """
    method = config.get("method", "atr_approx")
    short_window = config.get("short_window", 20)
    long_window = config.get("long_window", 60)
    threshold_high = config.get("threshold_high", 1.5)

    value = np.nan

    # 直接读取列
    for col in ("vix", "volatility", "cvix"):
        if col in market_data.columns:
            try:
                value = float(market_data.loc[date, col])
                break
            except Exception:
                pass

    # ATR 近似计算
    if np.isnan(value) and method == "atr_approx":
        try:
            close = market_data["close"]
            high = market_data.get("high", close)
            low = market_data.get("low", close)
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_short = tr.rolling(short_window).mean().loc[:date].iloc[-1]
            atr_long = tr.rolling(long_window).mean().loc[:date].iloc[-1]
            value = atr_short / atr_long if atr_long != 0 else 1.0
        except Exception:
            pass

    # 历史波动率近似
    if np.isnan(value) and method == "hist_vol":
        try:
            ret = market_data["close"].pct_change()
            vol_short = ret.rolling(short_window).std().loc[:date].iloc[-1]
            vol_long = ret.rolling(long_window).std().loc[:date].iloc[-1]
            value = vol_short / vol_long if vol_long != 0 else 1.0
        except Exception:
            pass

    if np.isnan(value):
        return None

    if value > threshold_high:
        direction = "extreme"
    elif value > 1.2:
        direction = "bearish"
    elif value < 0.8:
        direction = "bullish"  # 低波动环境通常利于多头
    else:
        direction = "neutral"

    return SubSignal(
        name="volatility_regime",
        value=round(float(value), 4),
        direction=direction,
        weight=config.get("weight", 1.2),
        meta={"method": method, "threshold_high": threshold_high},
    )
