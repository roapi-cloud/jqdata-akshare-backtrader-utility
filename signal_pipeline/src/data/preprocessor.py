"""Data preprocessing: cleaning, suspension detection, alignment, feature engineering."""

from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd

from ..core.models import MarketData


class DataPreprocessor:
    """Clean, detect suspensions, align timeframes, and engineer features.

    All methods accept and return plain ``pd.DataFrame`` objects; the
    ``pipeline`` convenience method wraps the full chain into a
    :class:`MarketData` instance.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def clean(df: pd.DataFrame) -> pd.DataFrame:
        """Handle NaNs and outliers.

        Steps:
          1. Forward-fill NaNs, then drop any rows that remain NaN.
          2. Replace 3-sigma outliers in numeric OHLCV columns with
             the column median.

        Args:
            df: Raw market data DataFrame.

        Returns:
            Cleaned DataFrame.
        """
        if df.empty:
            return df

        df = df.copy()

        # --- NaN handling: ffill then drop remaining ---
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].ffill()
        df = df.dropna(subset=numeric_cols)

        # --- 3-sigma outlier replacement ---
        for col in numeric_cols:
            series = df[col]
            mean = series.mean()
            std = series.std()
            if std == 0 or np.isnan(std):
                continue
            median = series.median()
            mask = (series - mean).abs() > 3 * std
            if mask.any():
                n_outliers = mask.sum()
                warnings.warn(
                    f"Replacing {n_outliers} outlier(s) in column '{col}' "
                    f"with median={median:.4f}"
                )
                df.loc[mask, col] = median

        return df

    @staticmethod
    def detect_suspension(df: pd.DataFrame) -> pd.DataFrame:
        """Add ``is_suspended`` boolean column.

        A bar is considered suspended when volume is zero *and* the
        closing price is unchanged from the previous bar.

        Args:
            df: DataFrame with at least ``volume`` and ``close`` columns.

        Returns:
            DataFrame with an additional ``is_suspended`` column.
        """
        if df.empty:
            df = df.copy()
            df["is_suspended"] = False
            return df

        df = df.copy()
        close = df["close"]
        vol = df["volume"]

        prev_close = close.shift(1)
        vol_zero = vol == 0
        price_unchanged = close == prev_close

        # First row has no previous close; treat as not suspended
        df["is_suspended"] = vol_zero & price_unchanged
        df.iloc[0, df.columns.get_loc("is_suspended")] = False

        return df

    @staticmethod
    def align_timeframes(
        daily_df: pd.DataFrame,
        minute_df: Optional[pd.DataFrame] = None,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Align daily and (optional) minute-level data.

        If ``minute_df`` is provided, it is resampled to daily OHLCV
        using standard aggregation rules.  Both DataFrames are returned
        sorted by datetime.

        Args:
            daily_df: Daily-frequency DataFrame.
            minute_df: Minute-frequency DataFrame (or ``None``).

        Returns:
            Tuple of ``(aligned_daily, resampled_minute_daily)``.
            The second element is ``None`` when ``minute_df`` is not
            provided or empty.
        """
        if not daily_df.empty and "datetime" in daily_df.columns:
            daily_df = daily_df.sort_values("datetime").reset_index(drop=True)

        if minute_df is None or minute_df.empty:
            return daily_df, None

        minute_df = minute_df.copy()
        if "datetime" not in minute_df.columns:
            return daily_df, None

        minute_df["datetime"] = pd.to_datetime(minute_df["datetime"])
        minute_df = minute_df.set_index("datetime")

        agg_rules = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "money": "sum",
        }

        # Only aggregate columns that exist
        available = {k: v for k, v in agg_rules.items() if k in minute_df.columns}
        resampled = minute_df.resample("D").agg(available).dropna(how="all")
        resampled = resampled.reset_index().rename(columns={"datetime": "datetime"})

        if "is_suspended" in minute_df.columns:
            resampled["is_suspended"] = resampled["volume"] == 0

        return daily_df, resampled

    @staticmethod
    def add_features(df: pd.DataFrame) -> pd.DataFrame:
        """Engineer common trading features.

        Adds:
          - ``pre_close``: previous day's close.
          - ``ret``: simple return ``(close - pre_close) / pre_close``.
          - ``limit_up``: boolean flag for +10% daily limit (ST: +5%).
          - ``limit_down``: boolean flag for -10% daily limit (ST: -5%).

        Args:
            df: DataFrame with at least ``close`` column.

        Returns:
            DataFrame with additional feature columns.
        """
        if df.empty:
            df = df.copy()
            for col in ("pre_close", "ret", "limit_up", "limit_down"):
                if col not in df.columns:
                    df[col] = np.nan if col == "ret" else False
            return df

        df = df.copy()

        # --- pre_close & return ---
        df["pre_close"] = df["close"].shift(1)
        df["ret"] = (df["close"] - df["pre_close"]) / df["pre_close"]

        # --- limit up / down detection ---
        # Standard A-share: +/-10%; ST stocks: +/-5%
        # We use a threshold of 9.8% / 4.8% to account for rounding
        pct = df["ret"].abs()
        df["limit_up"] = (df["ret"] >= 0.098) | ((df["ret"] >= 0.048) & (df["ret"] > 0))
        df["limit_down"] = (df["ret"] <= -0.098) | (
            (df["ret"] <= -0.048) & (df["ret"] < 0)
        )

        # First row has no pre_close
        df.iloc[0, df.columns.get_loc("pre_close")] = np.nan
        df.iloc[0, df.columns.get_loc("ret")] = np.nan

        return df

    # ------------------------------------------------------------------
    # Convenience: full pipeline
    # ------------------------------------------------------------------

    def pipeline(
        self,
        df: pd.DataFrame,
        minute_df: Optional[pd.DataFrame] = None,
    ) -> MarketData:
        """Run the full preprocessing chain and return a :class:`MarketData`.

        Order: clean -> detect_suspension -> align_timeframes -> add_features.

        Args:
            df: Raw daily DataFrame.
            minute_df: Optional minute-level DataFrame.

        Returns:
            A ``MarketData`` object wrapping the processed DataFrame.
        """
        df = self.clean(df)
        df = self.detect_suspension(df)

        if minute_df is not None and not minute_df.empty:
            df, _ = self.align_timeframes(df, minute_df)

        df = self.add_features(df)

        # Ensure datetime is the index for MarketData.from_df
        if "datetime" in df.columns:
            df = df.sort_values("datetime").reset_index(drop=True)

        return MarketData.from_df(df)
