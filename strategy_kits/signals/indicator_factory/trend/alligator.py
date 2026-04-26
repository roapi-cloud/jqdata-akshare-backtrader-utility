"""
Alligator Signal

基于鳄鱼线指标的择时信号。
来源: QuantsPlaybook/SignalMaker/alligator_indicator_timing.py

鳄鱼线由三条均线组成:
- 下颚线 (Jaw): 13周期 SMA，滞后 8 根
- 牙齿线 (Teeth): 8周期 SMA，滞后 5 根
- 上唇线 (Lips): 5周期 SMA，滞后 3 根
"""

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from ..base import DiscreteSignal
from ..registry import register_signal
from ..utils import alignment_signal, ffill_fillna, trigger_signal

try:
    from talib import SMA as talib_sma

    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


def _sma(close: np.ndarray, period: int) -> np.ndarray:
    """计算 SMA"""
    if HAS_TALIB:
        return talib_sma(close, period)
    else:
        return pd.Series(close).rolling(period).mean().values


def _get_shift(arr: np.ndarray, n: int) -> np.ndarray:
    """数组向后移位，前面填充 nan"""
    result = np.empty_like(arr)
    result[:] = np.nan
    if n < len(arr):
        result[n:] = arr[:-n]
    return result


def calculate_alligator_indicator(
    close_arr: np.ndarray,
    periods: Tuple[int, int, int] = (13, 8, 5),
    lag: Tuple[int, int, int] = (8, 5, 3),
) -> np.ndarray:
    """计算鳄鱼线指标

    参数:
        close_arr: 收盘价序列
        periods: 三条线的周期 (下颚线, 牙齿线, 上唇线)
        lag: 滞后周期

    返回:
        np.ndarray: 形状为 (n, 3)，列分别为 [下颚线, 牙齿线, 上唇线]
    """
    if len(close_arr) < max(periods) + max(lag):
        # 返回全nan数组
        return np.full((len(close_arr), 3), np.nan)

    # 计算三条 SMA 并移位
    lines = []
    for p, l in zip(periods, lag):
        sma = _sma(close_arr, p)
        shifted = _get_shift(sma, l)
        lines.append(shifted)

    return np.column_stack(lines)


def alligator_classify_rows(alligator_arr: np.ndarray) -> np.ndarray:
    """根据鳄鱼线指标对行进行分类

    参数:
        alligator_arr: 鳄鱼线指标数组，形状为 (n, 3)

    返回:
        np.ndarray: 分类结果，1(多头排列), -1(空头排列), 0(其他)
    """
    n = alligator_arr.shape[0]
    result = np.full(n, 0, dtype=float)

    # 检测排列
    bullish = alignment_signal(alligator_arr, "bullish")
    bearish = alignment_signal(alligator_arr, "bearish")

    # 触发信号（今天形成排列且昨天不是）
    bullish_trigger = trigger_signal(bullish)
    bearish_trigger = trigger_signal(bearish)

    result[bullish_trigger] = 1
    result[bearish_trigger] = -1

    return result


@register_signal("alligator")
class AlligatorSignal(DiscreteSignal):
    """鳄鱼线信号

    多头排列：下颚线 < 牙齿线 < 上唇线 (短期 > 中期 > 长期)
    空头排列：下颚线 > 牙齿线 > 上唇线

    输入:
        price_df: pd.DataFrame
            index: datetime
            columns: asset codes
            values: close prices
        config: {
            "periods": (13, 8, 5),       # 下颚线、牙齿线、上唇线周期
            "lag": (8, 5, 3),             # 滞后周期
            "keep_pre_status": True,      # 是否保持前一状态
        }

    输出:
        {
            "signal_df": pd.DataFrame,   # -1(空头排列), 0(无信号/沉睡), 1(多头排列)
            "meta": {
                "jaw": pd.DataFrame,      # 下颚线
                "teeth": pd.DataFrame,    # 牙齿线
                "lips": pd.DataFrame,     # 上唇线
            }
        }
    """

    name = "alligator"
    category = "trend"

    def _validate_config(self) -> None:
        self.periods = self.config.get("periods", (13, 8, 5))
        self.lag = self.config.get("lag", (8, 5, 3))
        self.keep_pre_status = self.config.get("keep_pre_status", True)

    def _compute_impl(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if price_df is None:
            raise ValueError("price_df is required")

        signals = {}
        jaws = {}
        teeths = {}
        lips = {}

        for col in price_df.columns:
            close = price_df[col].dropna().values
            if len(close) < max(self.periods) + max(self.lag):
                continue

            alligator = calculate_alligator_indicator(
                close, self.periods, self.lag
            )
            sig = alligator_classify_rows(alligator)

            idx = price_df[col].dropna().index
            signals[col] = pd.Series(sig, index=idx)
            jaws[col] = pd.Series(alligator[:, 0], index=idx)
            teeths[col] = pd.Series(alligator[:, 1], index=idx)
            lips[col] = pd.Series(alligator[:, 2], index=idx)

        signal_df = pd.DataFrame(signals)

        if self.keep_pre_status:
            signal_df = ffill_fillna(signal_df.replace(0, np.nan))

        return self._wrap_result(
            signal=signal_df,
            extra_meta={
                "jaw": pd.DataFrame(jaws),
                "teeth": pd.DataFrame(teeths),
                "lips": pd.DataFrame(lips),
            },
        )
