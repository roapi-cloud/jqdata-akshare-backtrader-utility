"""
MACD Signal

基于 MACD 指标的择时信号。
来源: QuantsPlaybook/SignalMaker/alligator_indicator_timing.py
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from ..base import DiscreteSignal
from ..registry import register_signal
from ..utils import ffill_fillna

try:
    from talib import MACD as talib_macd

    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


def _macd_classify(
    dif: np.ndarray, dea: np.ndarray, hist: np.ndarray
) -> np.ndarray:
    """MACD 分类逻辑

    看多条件：
    - DIF 上穿 DEA
    - 能量柱由绿转红 (hist > 0 且前一期 < 0)
    - 零轴上方 (dif >= 0, dea >= 0, hist >= 0)

    看空条件：
    - DIF 下穿 DEA
    - 能量柱由红转绿 (hist < 0 且前一期 > 0)
    - 零轴下方 (dif < 0, dea < 0, hist < 0)
    """
    n = len(dif)
    result = np.zeros(n)

    if n < 2:
        return result

    # 看多条件
    dif_cross_dea = (dif > dea) & (np.roll(dif, 1) < np.roll(dea, 1))
    macd_green_to_red = (hist > 0) & (np.roll(hist, 1) < 0)
    bullish_zero_zone = (dif >= 0) & (dea >= 0) & (hist >= 0)
    bullish = dif_cross_dea & macd_green_to_red & bullish_zero_zone

    # 看空条件
    dea_cross_dif = (dif < dea) & (np.roll(dif, 1) > np.roll(dea, 1))
    macd_red_to_green = (hist < 0) & (np.roll(hist, 1) > 0)
    bearish_zero_zone = (dif < 0) & (dea < 0) & (hist < 0)
    bearish = dea_cross_dif & macd_red_to_green & bearish_zero_zone

    result[bullish] = 1
    result[bearish] = -1

    # 第一个值设为0（因为用到了shift）
    result[0] = 0

    return result


def _calc_macd(
    close: np.ndarray,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> tuple:
    """计算 MACD"""
    if HAS_TALIB:
        return talib_macd(close, fastperiod, slowperiod, signalperiod)
    else:
        # 纯 pandas 实现
        ema_fast = pd.Series(close).ewm(span=fastperiod, adjust=False).mean()
        ema_slow = pd.Series(close).ewm(span=slowperiod, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signalperiod, adjust=False).mean()
        hist = dif - dea
        return dif.values, dea.values, hist.values


@register_signal("macd")
class MACDSignal(DiscreteSignal):
    """MACD信号

    输入:
        price_df: pd.DataFrame
            index: datetime
            columns: asset codes
            values: close prices
        config: {
            "fastperiod": 12,
            "slowperiod": 26,
            "signalperiod": 9,
            "keep_pre_status": True,  # 是否保持前一状态
        }

    输出:
        {
            "signal_df": pd.DataFrame,   # -1(看空), 0, 1(看多)
            "meta": {
                "dif": pd.DataFrame,
                "dea": pd.DataFrame,
                "hist": pd.DataFrame,
            }
        }
    """

    name = "macd"
    category = "trend"

    def _validate_config(self) -> None:
        self.fastperiod = self.config.get("fastperiod", 12)
        self.slowperiod = self.config.get("slowperiod", 26)
        self.signalperiod = self.config.get("signalperiod", 9)
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
        difs = {}
        deas = {}
        hists = {}

        for col in price_df.columns:
            close = price_df[col].dropna().values
            if len(close) < self.slowperiod + self.signalperiod:
                continue

            dif, dea, hist = _calc_macd(
                close, self.fastperiod, self.slowperiod, self.signalperiod
            )
            sig = _macd_classify(dif, dea, hist)

            idx = price_df[col].dropna().index
            signals[col] = pd.Series(sig, index=idx)
            difs[col] = pd.Series(dif, index=idx)
            deas[col] = pd.Series(dea, index=idx)
            hists[col] = pd.Series(hist, index=idx)

        signal_df = pd.DataFrame(signals)

        if self.keep_pre_status:
            signal_df = ffill_fillna(signal_df.replace(0, np.nan))

        return self._wrap_result(
            signal=signal_df,
            extra_meta={
                "dif": pd.DataFrame(difs),
                "dea": pd.DataFrame(deas),
                "hist": pd.DataFrame(hists),
            },
        )
