"""Market breadth factors.

These factors operate on cross-sectional market data, typically requiring
a panel of stocks. Input data should have a MultiIndex (date, code) or
be pre-aggregated per-date statistics.

When data is a single-stock DataFrame, breadth factors return NaN or
degenerate values since breadth requires market-wide data.
"""

from typing import Any

import numpy as np
import pandas as pd

from .base import Factor, FactorResult


class NewHighRatioFactor(Factor):
    """New High Ratio factor.

    Computes the proportion of stocks that made a new N-day high on each date.

    Input: MultiIndex DataFrame (date, code) with at least `high` and `close`.
    Returns: Series named `new_high_ratio`.
    """

    @property
    def name(self) -> str:
        return "NEW_HIGH_RATIO"

    def calculate(
        self, data: pd.DataFrame, period: int = 60, **kwargs: Any
    ) -> FactorResult:
        self.validate_data(data, ["high"])

        if not isinstance(data.index, pd.MultiIndex):
            return FactorResult(
                name=self.name,
                values=pd.Series(dtype=float, name="new_high_ratio"),
                params={"period": period},
                metadata={
                    "warning": "MultiIndex (date, code) required for breadth factors"
                },
            )

        dates = data.index.get_level_values(0).unique()
        ratios: list[float] = []

        for date in dates:
            day_data = data.loc[date]
            if day_data.empty:
                ratios.append(np.nan)
                continue

            rolling_high = (
                data.groupby(level=1)["high"]
                .rolling(window=period, min_periods=period)
                .max()
            )

            date_slice = rolling_high.loc[date]
            if date_slice.empty:
                ratios.append(np.nan)
                continue

            current_high = day_data["high"]
            prev_high = date_slice.shift(1)

            new_highs = (current_high >= prev_high).sum()
            total = len(current_high.dropna())
            ratios.append(new_highs / total if total > 0 else np.nan)

        values = pd.Series(ratios, index=dates, name="new_high_ratio")
        return FactorResult(
            name=self.name,
            values=values,
            params={"period": period},
        )


class AboveMARatioFactor(Factor):
    """Above MA Ratio factor.

    Computes the proportion of stocks trading above their N-day moving average.

    Input: MultiIndex DataFrame (date, code) with at least `close`.
    Returns: Series named `above_ma_ratio`.
    """

    @property
    def name(self) -> str:
        return "ABOVE_MA_RATIO"

    def calculate(
        self, data: pd.DataFrame, period: int = 20, **kwargs: Any
    ) -> FactorResult:
        self.validate_data(data, ["close"])

        if not isinstance(data.index, pd.MultiIndex):
            return FactorResult(
                name=self.name,
                values=pd.Series(dtype=float, name="above_ma_ratio"),
                params={"period": period},
                metadata={
                    "warning": "MultiIndex (date, code) required for breadth factors"
                },
            )

        ma = (
            data.groupby(level=1)["close"]
            .rolling(window=period, min_periods=period)
            .mean()
            .reset_index(level=0, drop=True)
        )

        above = data["close"] > ma
        dates = data.index.get_level_values(0).unique()

        ratios = []
        for date in dates:
            day_above = above.loc[date]
            valid = day_above.dropna()
            if valid.empty:
                ratios.append(np.nan)
            else:
                ratios.append(valid.mean())

        values = pd.Series(ratios, index=dates, name="above_ma_ratio")
        return FactorResult(
            name=self.name,
            values=values,
            params={"period": period},
        )


class AdvanceDeclineFactor(Factor):
    """Advance/Decline ratio factor.

    Computes the ratio of advancing to declining stocks per date.
    A stock is advancing if close > prev_close, declining if close < prev_close.

    Input: MultiIndex DataFrame (date, code) with at least `close`.
    Returns: DataFrame with columns: advances, declines, ad_ratio, ad_line (cumulative).
    """

    @property
    def name(self) -> str:
        return "ADVANCE_DECLINE"

    def calculate(self, data: pd.DataFrame, **kwargs: Any) -> FactorResult:
        self.validate_data(data, ["close"])

        if not isinstance(data.index, pd.MultiIndex):
            return FactorResult(
                name=self.name,
                values=pd.DataFrame(),
                params={},
                metadata={
                    "warning": "MultiIndex (date, code) required for breadth factors"
                },
            )

        prev_close = data.groupby(level=1)["close"].shift(1)
        diff = data["close"] - prev_close

        advances = (diff > 0).astype(int)
        declines = (diff < 0).astype(int)

        dates = data.index.get_level_values(0).unique()
        adv_counts = advances.groupby(level=0).sum()
        dec_counts = declines.groupby(level=0).sum()

        ad_ratio = self.safe_div(adv_counts, dec_counts)
        ad_line = (adv_counts - dec_counts).cumsum()

        values = pd.DataFrame(
            {
                "advances": adv_counts,
                "declines": dec_counts,
                "ad_ratio": ad_ratio,
                "ad_line": ad_line,
            },
            index=dates,
        )
        return FactorResult(
            name=self.name,
            values=values,
            params={},
        )


class LimitUpDownFactor(Factor):
    """Limit Up/Down count factor.

    Counts stocks hitting daily price limits.
    For A-shares: limit up = +10% (or +20% for ChiNext/STAR), limit down = -10%.

    Input: MultiIndex DataFrame (date, code) with `close` and `pre_close`
           (or `close` alone, using prev close as reference).
    Returns: DataFrame with columns: limit_up, limit_down, limit_up_ratio, limit_down_ratio.
    """

    @property
    def name(self) -> str:
        return "LIMIT_UP_DOWN"

    def calculate(
        self,
        data: pd.DataFrame,
        limit_up_pct: float = 0.098,
        limit_down_pct: float = -0.098,
        **kwargs: Any,
    ) -> FactorResult:
        self.validate_data(data, ["close"])

        if not isinstance(data.index, pd.MultiIndex):
            return FactorResult(
                name=self.name,
                values=pd.DataFrame(),
                params={},
                metadata={
                    "warning": "MultiIndex (date, code) required for breadth factors"
                },
            )

        if "pre_close" in data.columns:
            prev = data["pre_close"]
        else:
            prev = data.groupby(level=1)["close"].shift(1)

        pct_change = (data["close"] - prev) / prev.replace(0, np.nan)

        limit_up = pct_change >= limit_up_pct
        limit_down = pct_change <= limit_down_pct

        dates = data.index.get_level_values(0).unique()
        lu_counts = limit_up.groupby(level=0).sum()
        ld_counts = limit_down.groupby(level=0).sum()

        total_per_date = data.groupby(level=0)["close"].count()
        lu_ratio = self.safe_div(lu_counts, total_per_date)
        ld_ratio = self.safe_div(ld_counts, total_per_date)

        values = pd.DataFrame(
            {
                "limit_up": lu_counts,
                "limit_down": ld_counts,
                "limit_up_ratio": lu_ratio,
                "limit_down_ratio": ld_ratio,
            },
            index=dates,
        )
        return FactorResult(
            name=self.name,
            values=values,
            params={"limit_up_pct": limit_up_pct, "limit_down_pct": limit_down_pct},
        )
