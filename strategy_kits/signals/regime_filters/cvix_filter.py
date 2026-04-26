"""
C-VIX 恐慌检测信号

计算基于 Parkinson 波动率和已实现波动率的 C-VIX，
并结合期限结构（短期/长期波动率的比值）判断极端的恐慌/平静状态。
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional

from .contract import SubSignal

def calc_cvix_regime(
    market_data: pd.DataFrame,
    config: Dict,
    date: str,
) -> Optional[SubSignal]:
    """
    计算 CVIX 状态。
    需 market_data 包含: close, high, low
    """
    period = config.get("period", 20)
    threshold_panic = config.get("threshold_panic", 0.8)
    threshold_calm = config.get("threshold_calm", 0.3)
    term_structure_threshold = config.get("term_structure_threshold", 1.2)
    weight = config.get("weight", 1.5)

    try:
        # 获取截至当前日期的数据
        df = market_data.loc[:date]
        if len(df) < period + 60:
            return None

        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        # Parkinson波动率
        hl_ratio = np.log(highs / lows)
        parkinson_vol = np.sqrt(np.mean(hl_ratio[-period:] ** 2) / (4 * np.log(2))) * np.sqrt(252)

        # 已实现波动率
        returns = np.diff(closes) / closes[:-1]
        realized_vol = np.std(returns[-period:]) * np.sqrt(252)

        # 综合波动率 CVIX
        cvix = (parkinson_vol + realized_vol) / 2

        # 历史 CVIX 序列计算，用于分位数
        cvix_history = []
        for i in range(period, len(returns)):
            r = returns[i-period:i]
            rv = np.std(r) * np.sqrt(252)
            hl = np.log(highs[i-period:i+1] / lows[i-period:i+1])[1:] # align length
            if len(hl) == period:
                pv = np.sqrt(np.mean(hl ** 2) / (4 * np.log(2))) * np.sqrt(252)
                cvix_history.append((rv + pv) / 2)
            
        cvix_percentile = np.mean(cvix > np.array(cvix_history)) if cvix_history else 0.5

        # 期限结构
        short_vol = np.std(returns[-5:]) * np.sqrt(252)
        long_vol = np.std(returns[-60:]) * np.sqrt(252)
        term_structure = short_vol / long_vol if long_vol > 0 else 1.0

        if cvix_percentile > threshold_panic and term_structure > term_structure_threshold:
            direction = "extreme"
        elif cvix_percentile < threshold_calm:
            direction = "bullish"
        else:
            direction = "neutral"

        return SubSignal(
            name="cvix_regime",
            value=round(float(cvix_percentile), 4),
            direction=direction,
            weight=weight,
            meta={
                "cvix": round(float(cvix), 4),
                "term_structure": round(float(term_structure), 4),
                "threshold_panic": threshold_panic,
            }
        )
    except Exception:
        return None
