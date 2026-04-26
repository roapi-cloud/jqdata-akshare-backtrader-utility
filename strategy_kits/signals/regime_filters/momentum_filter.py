"""
趋势状态计算

来源：
- ICU均线 / src/icu_ma.py（稳健回归均线）
- 聚宽558/37 微盘股扩散指数双均线择时（EMA6/EMA28）
- 聚宽558/02 ETF动量轮动RSRS择时（RSRS）
- 聚宽558/01 7年40倍（简单均线牛熊判断）
"""
from typing import Dict, Optional
import pandas as pd
import numpy as np

from .contract import SubSignal


def calc_momentum_trend(
    market_data: pd.DataFrame,
    config: Dict,
    date: str,
) -> Optional[SubSignal]:
    """
    计算趋势状态。

    method 可选：
    - 'dual_ema'：快慢 EMA 交叉判断（如 EMA6 / EMA28）
    - 'icu_ma'：稳健回归 ICU 均线交叉
    - 'simple_ma'：简单双均线
    - 'rsrs'：RSRS 简化接口（需外部传入 'rsrs_score' 列）
    """
    method = config.get("method", "icu_ma")
    fast_window = config.get("fast_window", 6)
    slow_window = config.get("slow_window", 28)
    benchmark = config.get("benchmark", "000300.XSHG")

    close = market_data["close"].loc[:date]
    value = np.nan
    meta = {"method": method, "benchmark": benchmark}

    if method == "rsrs":
        if "rsrs_score" in market_data.columns:
            try:
                value = float(market_data.loc[date, "rsrs_score"])
            except Exception:
                pass
        meta["interpretation"] = "rsrs_score > threshold -> bullish"

    elif method == "dual_ema":
        try:
            ema_fast = close.ewm(span=fast_window, adjust=False).mean().iloc[-1]
            ema_slow = close.ewm(span=slow_window, adjust=False).mean().iloc[-1]
            value = 1.0 if ema_fast > ema_slow else 0.0
            meta["ema_fast"] = round(ema_fast, 4)
            meta["ema_slow"] = round(ema_slow, 4)
        except Exception:
            pass

    elif method == "simple_ma":
        try:
            ma_fast = close.rolling(fast_window).mean().iloc[-1]
            ma_slow = close.rolling(slow_window).mean().iloc[-1]
            value = 1.0 if ma_fast > ma_slow else 0.0
            meta["ma_fast"] = round(ma_fast, 4)
            meta["ma_slow"] = round(ma_slow, 4)
        except Exception:
            pass

    elif method == "icu_ma":
        try:
            icu_fast = _siegelslopes_ma(close.tail(fast_window).values)
            icu_slow = _siegelslopes_ma(close.tail(slow_window).values)
            value = 1.0 if icu_fast > icu_slow else 0.0
            meta["icu_fast"] = round(icu_fast, 4)
            meta["icu_slow"] = round(icu_slow, 4)
        except Exception:
            pass

    if np.isnan(value):
        return None

    # 统一映射到方向
    if method == "rsrs":
        # 此时 value 为连续值，默认>0为多头
        direction = "bullish" if value > 0 else "bearish" if value < 0 else "neutral"
    else:
        direction = "bullish" if value == 1.0 else "bearish"

    return SubSignal(
        name="momentum_trend",
        value=round(float(value), 4),
        direction=direction,
        weight=config.get("weight", 1.0),
        meta=meta,
    )


def _siegelslopes_ma(prices: np.ndarray) -> float:
    """简化 ICU 稳健回归（Siegel slopes）"""
    from scipy import stats
    n = len(prices)
    res = stats.siegelslopes(prices, np.arange(n), method="hierarchical")
    return float(res.intercept + res.slope * (n - 1))
