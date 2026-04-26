"""Market sentiment factors."""

from typing import Any

import numpy as np
import pandas as pd

from .base import Factor, FactorResult


class TurnoverSentimentFactor(Factor):
    """Turnover Rate Sentiment factor.

    Uses turnover rate as a proxy for market sentiment.
    High turnover may indicate overheating; low turnover may indicate apathy.

    Input: DataFrame with `turnover` column (turnover rate in decimal or percent).
    Returns: Series named `turnover_sentiment` (z-score of turnover over lookback).
    """

    @property
    def name(self) -> str:
        return "TURNOVER_SENTIMENT"

    def calculate(
        self,
        data: pd.DataFrame,
        lookback: int = 60,
        **kwargs: Any,
    ) -> FactorResult:
        self.validate_data(data, ["turnover"])

        turnover = data["turnover"].astype(float)
        rolling_mean = turnover.rolling(window=lookback, min_periods=lookback).mean()
        rolling_std = turnover.rolling(window=lookback, min_periods=lookback).std(
            ddof=1
        )

        sentiment = self.safe_div(turnover - rolling_mean, rolling_std)
        sentiment = sentiment.rename("turnover_sentiment")

        return FactorResult(
            name=self.name,
            values=sentiment,
            params={"lookback": lookback},
        )


class VolumeShrinkageFactor(Factor):
    """Volume Shrinkage Ratio factor.

    Measures the ratio of recent volume to longer-term average volume.
    Values < 1 indicate volume shrinkage (potential consolidation);
    values > 1 indicate volume expansion.

    Input: DataFrame with `volume` column.
    Returns: Series named `volume_shrinkage` = MA(short) / MA(long).
    """

    @property
    def name(self) -> str:
        return "VOLUME_SHRINKAGE"

    def calculate(
        self,
        data: pd.DataFrame,
        short_period: int = 5,
        long_period: int = 20,
        **kwargs: Any,
    ) -> FactorResult:
        self.validate_data(data, ["volume"])

        volume = data["volume"].astype(float)
        short_ma = volume.rolling(window=short_period, min_periods=short_period).mean()
        long_ma = volume.rolling(window=long_period, min_periods=long_period).mean()

        ratio = self.safe_div(short_ma, long_ma)
        ratio = ratio.rename("volume_shrinkage")

        return FactorResult(
            name=self.name,
            values=ratio,
            params={"short_period": short_period, "long_period": long_period},
        )


class CrowdRateFactor(Factor):
    """Crowd Rate (Volume Concentration) factor.

    Measures the proportion of total volume contributed by the top N% of
    trading days. A high crowd rate indicates volume concentration,
    suggesting strong consensus or potential climax.

    Input: DataFrame with `volume` column.
    Returns: Series named `crowd_rate` computed over a rolling window.
    """

    @property
    def name(self) -> str:
        return "CROWD_RATE"

    def calculate(
        self,
        data: pd.DataFrame,
        window: int = 60,
        top_pct: float = 0.05,
        **kwargs: Any,
    ) -> FactorResult:
        self.validate_data(data, ["volume"])

        volume = data["volume"].astype(float)
        n_top = max(1, int(window * top_pct))

        def _crowd_rate(series: pd.Series) -> float:
            valid = series.dropna()
            if len(valid) < n_top:
                return np.nan
            top_n = valid.nlargest(n_top).sum()
            total = valid.sum()
            if total == 0:
                return np.nan
            return top_n / total

        crowd_rate = volume.rolling(window=window, min_periods=window).apply(
            _crowd_rate, raw=False
        )
        crowd_rate = crowd_rate.rename("crowd_rate")

        return FactorResult(
            name=self.name,
            values=crowd_rate,
            params={"window": window, "top_pct": top_pct},
        )


class GSISIFactor(Factor):
    """Guosen Sentiment Index (simplified) factor.

    A composite sentiment indicator based on:
    1. Price momentum (rate of change over short/long periods)
    2. Volume trend (volume ratio)
    3. Turnover rate change

    The index is a weighted combination normalized to [-1, 1] range.
    Positive values indicate bullish sentiment; negative indicates bearish.

    Input: DataFrame with `close`, `volume`, `turnover` columns.
    Returns: Series named `gsi_senti` in range [-1, 1].
    """

    @property
    def name(self) -> str:
        return "GSI_SENTIMENT"

    def calculate(
        self,
        data: pd.DataFrame,
        short_period: int = 5,
        long_period: int = 20,
        vol_lookback: int = 20,
        weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
        **kwargs: Any,
    ) -> FactorResult:
        self.validate_data(data, ["close", "volume", "turnover"])

        close = data["close"].astype(float)
        volume = data["volume"].astype(float)
        turnover = data["turnover"].astype(float)

        short_roc = close.pct_change(short_period)
        long_roc = close.pct_change(long_period)
        momentum = short_roc - long_roc

        vol_ma = volume.rolling(window=vol_lookback, min_periods=vol_lookback).mean()
        vol_ratio = self.safe_div(volume, vol_ma) - 1.0

        turnover_ma = turnover.rolling(
            window=vol_lookback, min_periods=vol_lookback
        ).mean()
        turnover_change = self.safe_div(turnover - turnover_ma, turnover_ma)

        w_mom, w_vol, w_to = weights

        raw_index = w_mom * momentum + w_vol * vol_ratio + w_to * turnover_change

        rolling_mean = raw_index.rolling(
            window=vol_lookback, min_periods=vol_lookback
        ).mean()
        rolling_std = raw_index.rolling(
            window=vol_lookback, min_periods=vol_lookback
        ).std(ddof=1)

        gsi = self.safe_div(raw_index - rolling_mean, rolling_std)

        gsi = gsi.clip(-3, 3) / 3.0
        gsi = gsi.rename("gsi_senti")

        return FactorResult(
            name=self.name,
            values=gsi,
            params={
                "short_period": short_period,
                "long_period": long_period,
                "vol_lookback": vol_lookback,
                "weights": weights,
            },
        )
