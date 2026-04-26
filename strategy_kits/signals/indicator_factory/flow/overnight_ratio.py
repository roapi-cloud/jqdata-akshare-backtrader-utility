"""
Overnight Ratio Signal

计算隔夜收益率占比，即隔夜收益率绝对值在隔夜与日间收益率绝对值总和中的比例，附带隔夜收益的方向。
隔夜收益高代表机构/信息优势，日间收益高代表散户追涨。
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from ..base import ContinuousSignal
from ..registry import register_signal


@register_signal("overnight_ratio")
class OvernightRatioSignal(ContinuousSignal):
    """隔夜/日间比值信号
    
    overnight_ratio = mean(|overnight|) / (mean(|overnight|) + mean(|intraday|)) * direction
    其中 overnight = open[t] / close[t-1] - 1
         intraday = close[t] / open[t] - 1
         
    需要 kwargs 中传入 `open_df` (OHLC 的 O) 和标准的 `price_df` (C)。
    
    输入:
        price_df: pd.DataFrame
            index: datetime
            columns: asset codes
            values: close prices
        kwargs:
            open_df: pd.DataFrame (与 price_df 形状相同的开盘价)
        config: {
            "window": 20,  # 均值计算窗口
        }
        
    输出:
        {
            "signal_df": pd.DataFrame,   # 连续的因子值
        }
    """

    name = "overnight_ratio"
    category = "flow"

    def _validate_config(self) -> None:
        self.window = self.config.get("window", 20)

    def _compute_impl(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if price_df is None:
            raise ValueError("price_df is required")
            
        open_df = kwargs.get("open_df")
        if open_df is None:
            raise ValueError("open_df is required in kwargs for overnight_ratio signal")

        signals = {}

        for col in price_df.columns:
            if col not in open_df.columns:
                signals[col] = pd.Series(np.nan, index=price_df.index)
                continue
                
            c = price_df[col]
            o = open_df[col]
            
            # overnight = open[t] / close[t-1] - 1
            # 这里 c.shift(1) 取上一个有效日期的收盘价
            overnight = o / c.shift(1) - 1.0
            
            # intraday = close[t] / open[t] - 1
            intraday = c / o - 1.0
            
            abs_overnight = overnight.abs()
            abs_intraday = intraday.abs()
            
            # 避免除以0
            total_abs = abs_overnight + abs_intraday
            # total_abs == 0 时的除法会产生 NaN，后续用 rolling 均值能兼容处理，但也可以先赋 0
            
            # valid ratio: abs_overnight / total_abs
            ratio = abs_overnight / total_abs.replace(0, np.nan)
            
            # 滚动均值
            mean_ratio = ratio.rolling(window=self.window, min_periods=self.window // 2).mean()
            
            # 方向: overnight > 0 的比例
            # 使用 numpy rolling mean
            direction_series = (overnight > 0).astype(float)
            mean_direction = direction_series.rolling(window=self.window, min_periods=self.window // 2).mean()
            
            # 因子的值
            factor = mean_ratio * mean_direction
            
            signals[col] = factor

        signal_df = pd.DataFrame(signals, index=price_df.index)

        return self._wrap_result(signal=signal_df)
