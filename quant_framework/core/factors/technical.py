"""Technical indicator factors."""

from typing import Any

import numpy as np
import pandas as pd

from .base import Factor, FactorResult


class MAFactor(Factor):
    """Moving Average factor.

    Computes simple moving averages over configurable windows.
    Default windows: [5, 10, 20, 60, 200].

    Returns a DataFrame with one column per window, named `ma_{window}`.
    """

    @property
    def name(self) -> str:
        return "MA"

    def calculate(
        self, data: pd.DataFrame, windows: list[int] | None = None, **kwargs: Any
    ) -> FactorResult:
        self.validate_data(data, ["close"])

        windows = windows or [5, 10, 20, 60, 200]
        result_dict: dict[str, pd.Series] = {}

        for w in windows:
            result_dict[f"ma_{w}"] = (
                data["close"].rolling(window=w, min_periods=w).mean()
            )

        values = pd.DataFrame(result_dict, index=data.index)
        return FactorResult(
            name=self.name,
            values=values,
            params={"windows": windows},
        )


class MACDFactor(Factor):
    """MACD (Moving Average Convergence Divergence) factor.

    Computes MACD line, signal line, and histogram.
    Default parameters: fast=12, slow=26, signal=9.

    Returns a DataFrame with columns: macd, signal, histogram.
    """

    @property
    def name(self) -> str:
        return "MACD"

    def calculate(
        self,
        data: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal_period: int = 9,
        **kwargs: Any,
    ) -> FactorResult:
        self.validate_data(data, ["close"])

        close = data["close"]
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        values = pd.DataFrame(
            {"macd": macd_line, "signal": signal_line, "histogram": histogram},
            index=data.index,
        )
        return FactorResult(
            name=self.name,
            values=values,
            params={"fast": fast, "slow": slow, "signal_period": signal_period},
        )


class RSIFactor(Factor):
    """Relative Strength Index factor.

    Computes RSI over a configurable period. Default: 14.

    Returns a Series named `rsi`.
    """

    @property
    def name(self) -> str:
        return "RSI"

    def calculate(
        self, data: pd.DataFrame, period: int = 14, **kwargs: Any
    ) -> FactorResult:
        self.validate_data(data, ["close"])

        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = self.safe_div(avg_gain, avg_loss)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        rsi = rsi.rename("rsi")
        return FactorResult(
            name=self.name,
            values=rsi,
            params={"period": period},
        )


class BollingerFactor(Factor):
    """Bollinger Bands factor.

    Computes upper band, middle band (MA), and lower band.
    Default: period=20, std_dev=2.0.

    Returns a DataFrame with columns: upper, middle, lower, bandwidth, pct_b.
    """

    @property
    def name(self) -> str:
        return "BOLL"

    def calculate(
        self,
        data: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
        **kwargs: Any,
    ) -> FactorResult:
        self.validate_data(data, ["close"])

        close = data["close"]
        middle = close.rolling(window=period, min_periods=period).mean()
        rolling_std = close.rolling(window=period, min_periods=period).std(ddof=0)

        upper = middle + std_dev * rolling_std
        lower = middle - std_dev * rolling_std

        bandwidth = self.safe_div(upper - lower, middle)
        pct_b = self.safe_div(close - lower, upper - lower)

        values = pd.DataFrame(
            {
                "upper": upper,
                "middle": middle,
                "lower": lower,
                "bandwidth": bandwidth,
                "pct_b": pct_b,
            },
            index=data.index,
        )
        return FactorResult(
            name=self.name,
            values=values,
            params={"period": period, "std_dev": std_dev},
        )


class ATRFactor(Factor):
    """Average True Range factor.

    Computes ATR over a configurable period. Default: 14.

    Returns a Series named `atr`.
    """

    @property
    def name(self) -> str:
        return "ATR"

    def calculate(
        self, data: pd.DataFrame, period: int = 14, **kwargs: Any
    ) -> FactorResult:
        self.validate_data(data, ["high", "low", "close"])

        high = data["high"]
        low = data["low"]
        close = data["close"]
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(
            alpha=1.0 / period, min_periods=period, adjust=False
        ).mean()

        atr = atr.rename("atr")
        return FactorResult(
            name=self.name,
            values=atr,
            params={"period": period},
        )
