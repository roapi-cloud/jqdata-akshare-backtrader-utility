"""
创新高个股比例计算

来源：market_sentiment_indicators.py (new_high_ratio)
"""
from typing import Dict, Optional
import pandas as pd
import numpy as np

from .contract import SubSignal


def calc_new_high_ratio(
    market_data: pd.DataFrame,
    breadth_data: Optional[pd.DataFrame],
    config: Dict,
    date: str,
) -> Optional[SubSignal]:
    """
    计算最近 check_days 内创 window 日新高的个股比例。

    若 breadth_data 为个股价格宽表，则直接计算；
    否则尝试从 market_data 的 'new_high_ratio' 列读取。
    """
    window = config.get("window", 252)
    check_days = config.get("check_days", 15)
    gap = config.get("gap", 60)
    th_low = config.get("threshold_low", 1.0)
    th_high = config.get("threshold_high", 5.0)

    value = np.nan

    if breadth_data is not None:
        try:
            prices = breadth_data.loc[:date].tail(window + check_days)
            if len(prices) >= window + 1:
                new_high_count = 0
                total = len(prices.columns)
                for i in range(-check_days, 0):
                    price = prices.iloc[i - window : i]
                    is_new_high = price.apply(
                        lambda x: np.argmax(x.values) == (len(x) - 1)
                        and np.argmax(x.values[:-1]) < (len(x) - 1 - gap)
                    )
                    new_high_count += is_new_high.sum()
                value = 100.0 * new_high_count / (total * check_days)
        except Exception:
            pass

    if np.isnan(value) and "new_high_ratio" in market_data.columns:
        try:
            value = float(market_data.loc[date, "new_high_ratio"])
        except Exception:
            pass

    if np.isnan(value):
        return None

    if value > th_high:
        direction = "bullish"
    elif value < th_low:
        direction = "bearish"
    else:
        direction = "neutral"

    return SubSignal(
        name="new_high_ratio",
        value=round(value, 2),
        direction=direction,
        weight=config.get("weight", 0.8),
        meta={"window": window, "check_days": check_days},
    )
