"""
High Quality Momentum Signal

基于风险调整后的动量因子。
公式：factor = r60 - 3000 * sigma^2
其中 r60 为窗口期累计收益率，sigma 为窗口期日收益率的波动率。
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from ..base import ContinuousSignal
from ..registry import register_signal


def calculate_quality_momentum(
    close_arr: np.ndarray,
    window: int = 60,
    penalty_factor: float = 3000.0,
) -> float:
    """计算单个资产的高质量动量因子
    
    参数:
        close_arr: 收盘价序列
        window: 动量计算窗口
        penalty_factor: 风险惩罚系数
        
    返回:
        float: 因子值。如果数据不足则返回 np.nan
    """
    if len(close_arr) < window + 1:
        return np.nan
        
    # 取窗口内数据
    prices = close_arr[-(window + 1):]
    
    # 避免除以0或无效数据
    if prices[-1] == 0 or prices[0] == 0:
        return np.nan
        
    returns = np.diff(prices) / prices[:-1]
    
    r_total = (prices[-1] / prices[0]) - 1
    sigma = np.std(returns)
    
    momentum_factor = r_total - penalty_factor * (sigma ** 2)
    return momentum_factor


@register_signal("quality_momentum")
class QualityMomentumSignal(ContinuousSignal):
    """高质量动量信号
    
    使用风险调整后的动量因子（r60 - 3000*sigma^2）。
    
    输入:
        price_df: pd.DataFrame
            index: datetime
            columns: asset codes
            values: close prices
        config: {
            "window": 60,               # 动量计算窗口
            "penalty_factor": 3000.0,   # 风险惩罚系数
        }
        
    输出:
        {
            "signal_df": pd.DataFrame,   # 连续的因子值
        }
    """

    name = "quality_momentum"
    category = "trend"

    def _validate_config(self) -> None:
        self.window = self.config.get("window", 60)
        self.penalty_factor = float(self.config.get("penalty_factor", 3000.0))

    def _compute_impl(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if price_df is None:
            raise ValueError("price_df is required")

        signals = {}

        # 逐列计算信号
        # ContinuousSignal 期望每一列返回一个 pd.Series，或者我们直接计算出一个 df
        # 为了与 alligator 保持类似的结构，这里我们为每个时间截面计算，但由于实现要求通常是 rolling 计算
        # 我们可以用 pandas 的 rolling api 或者逐行 apply，考虑到性能，如果是历史数据计算，则...
        # Wait, BaseSignal compute handles historically if rolling is needed. But `calculate_quality_momentum`
        # above returns a scalar for the END of the array. Let's make it return an array using rolling or sliding window.
        
        from ..utils import sliding_window
        
        for col in price_df.columns:
            close = price_df[col].values
            
            # 使用滑动窗口计算
            # 我们需要 window + 1 的数据来计算收益率和总体收益
            if len(close) < self.window + 1:
                signals[col] = pd.Series(np.nan, index=price_df.index)
                continue
                
            # 我们利用 pd.Series.rolling 结合自定义 function 也可以，或者纯 numpy 滑动窗
            # 这里为简单起见，使用 pandas 的 rolling
            # p_last / p_first - 1
            s = price_df[col]
            pct_chg = s.pct_change()
            
            # 计算总收益 (当前价 / N天前价 - 1)
            # 例如 window=60, s / s.shift(60) - 1
            r_total = s / s.shift(self.window) - 1.0
            
            # 由于 pct_change 本身就是收益率，滚动按 window 的标准差计算
            sigma = pct_chg.rolling(window=self.window).std()
            
            factor_series = r_total - self.penalty_factor * (sigma ** 2)
            signals[col] = factor_series

        signal_df = pd.DataFrame(signals, index=price_df.index)

        return self._wrap_result(signal=signal_df)
