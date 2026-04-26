"""
拥挤率计算

来源：market_sentiment_indicators.py (crowding_rate)
"""
from typing import Dict, Optional
import pandas as pd
import numpy as np

from .contract import SubSignal


def calc_crowding_rate(
    market_data: pd.DataFrame,
    breadth_data: Optional[pd.DataFrame],
    config: Dict,
    date: str,
) -> Optional[SubSignal]:
    """
    计算资金拥挤率。

    若 breadth_data 包含 'money' 列（个股成交额），
    则计算当日成交额前 top_pct 个股的成交金额占比。
    否则尝试从 market_data 的 'crowding_rate' 列直接读取。
    """
    top_pct = config.get("top_pct", 0.05)
    th_low = config.get("threshold_low", 40.0)
    th_high = config.get("threshold_high", 60.0)

    value = np.nan

    if breadth_data is not None and "money" in breadth_data.columns:
        try:
            day_df = breadth_data.loc[date]
            if isinstance(day_df, pd.DataFrame):
                # 如果 breadth_data 是长表（含多日期），取 date 切片
                day_df = day_df.squeeze()
            day_df = day_df.dropna().sort_values(ascending=False)
            n_top = max(1, int(len(day_df) * top_pct))
            value = day_df.iloc[:n_top].sum() / day_df.sum() * 100
        except Exception:
            pass

    if np.isnan(value) and "crowding_rate" in market_data.columns:
        try:
            value = float(market_data.loc[date, "crowding_rate"])
        except Exception:
            pass

    if np.isnan(value):
        return None

    if value > th_high:
        direction = "extreme"
    elif value > 55:
        direction = "bearish"
    elif value < th_low:
        direction = "bullish"  # 分散意味着后续轮动机会
    else:
        direction = "neutral"

    return SubSignal(
        name="crowding_rate",
        value=round(value, 2),
        direction=direction,
        weight=config.get("weight", 0.8),
        meta={"top_pct": top_pct},
    )
