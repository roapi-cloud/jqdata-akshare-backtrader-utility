"""
市场宽度/扩散指数计算

来源：market_sentiment_indicators.py (market_breadth)
      聚宽558/37 微盘股扩散指数双均线择时 (get_ks_index)
"""
from typing import Dict, Optional
import pandas as pd
import numpy as np

from .contract import SubSignal


def calc_market_breadth(
    market_data: pd.DataFrame,
    breadth_data: Optional[pd.DataFrame],
    config: Dict,
    date: str,
) -> Optional[SubSignal]:
    """
    计算市场宽度信号。

    当前为简化版本：若传入 breadth_data（含全市场个股 close），
    则基于配置 window 计算 BIAS>0 比例；否则尝试从 market_data 的
    'breadth' 列直接读取。
    """
    window = config.get("window", 20)
    th_low = config.get("threshold_low", 30.0)
    th_high = config.get("threshold_high", 70.0)

    value = np.nan

    # 情况1：breadth_data 存在且包含个股价格
    if breadth_data is not None:
        # 期望 breadth_data 为宽表：index-date, columns-股票代码
        # 取最近 window 天计算
        try:
            sub = breadth_data.loc[:date].tail(window)
            if len(sub) >= window:
                ma = sub.mean()
                last = sub.iloc[-1]
                bias = (last - ma) / ma * 100
                positive = (bias > 0).sum()
                total = bias.notna().sum()
                value = 100.0 * positive / total if total > 0 else 50.0
        except Exception:
            pass

    # 情况2：market_data 中包含 'breadth' 列
    if np.isnan(value) and "breadth" in market_data.columns:
        try:
            value = float(market_data.loc[date, "breadth"])
        except Exception:
            pass

    if np.isnan(value):
        return None

    # 方向判断
    if value < th_low:
        direction = "extreme"
    elif value < 45:
        direction = "bearish"
    elif value > th_high:
        direction = "extreme"  # 也可理解为 bullish 过头
    elif value > 55:
        direction = "bullish"
    else:
        direction = "neutral"

    return SubSignal(
        name="market_breadth",
        value=round(value, 2),
        direction=direction,
        weight=config.get("weight", 1.0),
        meta={"threshold_low": th_low, "threshold_high": th_high},
    )
