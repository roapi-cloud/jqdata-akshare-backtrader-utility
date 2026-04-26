"""技术指标计算"""

import pandas as pd
import numpy as np
from typing import Tuple


class TechnicalIndicators:
    """技术指标计算工具类"""

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """简单移动平均

        Args:
            series: 价格序列
            period: 周期

        Returns:
            pd.Series: SMA值
        """
        return series.rolling(period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """指数移动平均

        Args:
            series: 价格序列
            period: 周期

        Returns:
            pd.Series: EMA值
        """
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def macd(
        close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD指标

        Args:
            close: 收盘价序列
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期

        Returns:
            Tuple: (DIF, DEA, MACD柱)
        """
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd_hist = 2 * (dif - dea)
        return dif, dea, macd_hist

    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """RSI指标

        Args:
            close: 收盘价序列
            period: 周期

        Returns:
            pd.Series: RSI值
        """
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = -delta.where(delta < 0, 0).rolling(period).mean()
        rs = gain / (loss + 1e-8)
        return 100 - 100 / (1 + rs)

    @staticmethod
    def boll(
        close: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """布林带

        Args:
            close: 收盘价序列
            period: 周期
            std_dev: 标准差倍数

        Returns:
            Tuple: (上轨, 中轨, 下轨)
        """
        mid = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = mid + std_dev * std
        lower = mid - std_dev * std
        return upper, mid, lower

    @staticmethod
    def atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """ATR指标

        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 周期

        Returns:
            pd.Series: ATR值
        """
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def momentum(close: pd.Series, period: int = 20) -> pd.Series:
        """动量指标

        Args:
            close: 收盘价序列
            period: 周期

        Returns:
            pd.Series: 动量值
        """
        return close.pct_change(period)
