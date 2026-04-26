"""Market timing signal generators.

Timing signals determine *when* to enter or exit the market based on
broad market indicators, rather than selecting *which* stocks to trade.
"""

from typing import Any, Optional

import numpy as np
import pandas as pd

from .base import Signal, SignalResult, SignalType


class MATimingSignal(Signal):
    """Market timing signal based on moving average crossovers.

    Generates BUY signals when a short-term MA crosses above a long-term MA
    (golden cross) and SELL signals on the opposite (death cross).

    Default parameters:
        short_window: 5 trading days
        long_window: 20 trading days
        buy_threshold: 0.0 (any positive crossover triggers BUY)
        sell_threshold: 0.0 (any negative crossover triggers SELL)
        strength_scale: 0.05 (strength increases 5% per 1% crossover gap)
    """

    @property
    def name(self) -> str:
        return "MA_TIMING"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate MA crossover timing signal.

        Args:
            factor_values: Must contain a 'close' Series or DataFrame with
                           market index close prices. May also contain
                           pre-computed MA factors.
            params: Optional overrides for short_window, long_window, etc.

        Returns:
            SignalResult with BUY/SELL/HOLD based on MA crossover state.
        """
        defaults = {
            "short_window": 5,
            "long_window": 20,
            "buy_threshold": 0.0,
            "sell_threshold": 0.0,
            "strength_scale": 0.05,
            "max_strength": 1.0,
        }
        cfg = self._merge_params(defaults, params)

        close = self._extract_close(factor_values)
        if close is None or close.empty:
            return self._empty_result("No close data available")

        short_ma = close.rolling(
            window=cfg["short_window"], min_periods=cfg["short_window"]
        ).mean()
        long_ma = close.rolling(
            window=cfg["long_window"], min_periods=cfg["long_window"]
        ).mean()

        if short_ma.iloc[-2:].isna().any() or long_ma.iloc[-2:].isna().any():
            return self._empty_result("Insufficient data for MA calculation")

        short_current = short_ma.iloc[-1]
        long_current = long_ma.iloc[-1]
        short_prev = short_ma.iloc[-2]
        long_prev = long_ma.iloc[-2]

        crossover = (short_current - long_current) / long_current
        prev_crossover = (short_prev - long_prev) / long_prev

        if crossover > cfg["buy_threshold"] and prev_crossover <= cfg["buy_threshold"]:
            strength = min(cfg["max_strength"], abs(crossover) / cfg["strength_scale"])
            return SignalResult(
                date=close.index[-1],
                signal_type=SignalType.BUY,
                strength=self._normalize_strength(strength),
                metadata={
                    "crossover": crossover,
                    "short_ma": short_current,
                    "long_ma": long_current,
                },
            )

        if (
            crossover < cfg["sell_threshold"]
            and prev_crossover >= cfg["sell_threshold"]
        ):
            strength = min(cfg["max_strength"], abs(crossover) / cfg["strength_scale"])
            return SignalResult(
                date=close.index[-1],
                signal_type=SignalType.SELL,
                strength=self._normalize_strength(strength),
                metadata={
                    "crossover": crossover,
                    "short_ma": short_current,
                    "long_ma": long_current,
                },
            )

        if crossover > cfg["buy_threshold"]:
            strength = min(cfg["max_strength"], crossover / cfg["strength_scale"]) * 0.5
            return SignalResult(
                date=close.index[-1],
                signal_type=SignalType.HOLD,
                strength=self._normalize_strength(strength),
                metadata={"crossover": crossover, "note": "Above MA, no crossover"},
            )

        return SignalResult(
            date=close.index[-1],
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"crossover": crossover, "note": "Below MA, no crossover"},
        )

    def _extract_close(
        self, factor_values: dict[str, pd.DataFrame | pd.Series]
    ) -> Optional[pd.Series]:
        """Extract close price series from factor values."""
        if "close" in factor_values:
            data = factor_values["close"]
            if isinstance(data, pd.DataFrame):
                return data.iloc[:, -1]
            return data
        if "MA" in factor_values:
            ma_data = factor_values["MA"]
            if isinstance(ma_data, pd.DataFrame) and "close" in ma_data.columns:
                return ma_data["close"]
        return None

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral HOLD result when signal cannot be computed."""
        import datetime

        return SignalResult(
            date=pd.Timestamp(datetime.date.today()),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )


class RSRSTimingSignal(Signal):
    """RSRS (Resistance Support Relative Strength) timing signal.

    RSRS uses the slope of a linear regression between high and low prices
    over a lookback window to gauge market timing. A rising slope indicates
    strengthening support relative to resistance (bullish), while a falling
    slope indicates weakening support (bearish).

    The passive version applies a right-skew adjustment that weights recent
    observations more heavily.

    Default parameters:
        window: 18 trading days for regression window
        lookback: 600 trading days for z-score calculation
        buy_threshold: 0.7 (z-score above this triggers BUY)
        sell_threshold: -0.7 (z-score below this triggers SELL)
        passive: False (set True for right-skew adjusted version)
        beta_weight: 0.5 (weight for right-skew adjustment in passive mode)
    """

    @property
    def name(self) -> str:
        return "RSRS_TIMING"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate RSRS timing signal.

        Args:
            factor_values: Must contain 'high' and 'low' Series or a
                           DataFrame with both columns.
            params: Optional overrides for window, lookback, thresholds, etc.

        Returns:
            SignalResult with BUY/SELL/HOLD based on RSRS z-score.
        """
        defaults = {
            "window": 18,
            "lookback": 600,
            "buy_threshold": 0.7,
            "sell_threshold": -0.7,
            "passive": False,
            "beta_weight": 0.5,
        }
        cfg = self._merge_params(defaults, params)

        high, low = self._extract_high_low(factor_values)
        if high is None or low is None or high.empty:
            return self._empty_result("No high/low data available")

        slope_series = self._compute_slope(high, low, cfg["window"])
        if slope_series.empty or len(slope_series) < cfg["lookback"]:
            return self._empty_result("Insufficient data for RSRS calculation")

        current_slope = slope_series.iloc[-1]
        slope_history = slope_series.iloc[-cfg["lookback"] :]

        mean_slope = slope_history.mean()
        std_slope = slope_history.std()

        if std_slope == 0 or np.isnan(std_slope):
            return self._empty_result("Zero standard deviation in slope history")

        z_score = (current_slope - mean_slope) / std_slope

        if cfg["passive"]:
            z_score = self._apply_right_skew_adjustment(
                z_score, slope_history, cfg["beta_weight"], cfg["lookback"]
            )

        if z_score > cfg["buy_threshold"]:
            strength = self._normalize_strength(
                z_score, cfg["buy_threshold"], cfg["buy_threshold"] * 2
            )
            return SignalResult(
                date=high.index[-1],
                signal_type=SignalType.BUY,
                strength=strength,
                metadata={
                    "z_score": z_score,
                    "slope": current_slope,
                    "passive": cfg["passive"],
                },
            )

        if z_score < cfg["sell_threshold"]:
            strength = self._normalize_strength(
                abs(z_score), abs(cfg["sell_threshold"]), abs(cfg["sell_threshold"]) * 2
            )
            return SignalResult(
                date=high.index[-1],
                signal_type=SignalType.SELL,
                strength=strength,
                metadata={
                    "z_score": z_score,
                    "slope": current_slope,
                    "passive": cfg["passive"],
                },
            )

        strength = self._normalize_strength(
            abs(z_score),
            0.0,
            max(abs(cfg["buy_threshold"]), abs(cfg["sell_threshold"])),
        )
        return SignalResult(
            date=high.index[-1],
            signal_type=SignalType.HOLD,
            strength=strength * 0.3,
            metadata={
                "z_score": z_score,
                "slope": current_slope,
                "passive": cfg["passive"],
            },
        )

    def _extract_high_low(
        self, factor_values: dict[str, pd.DataFrame | pd.Series]
    ) -> tuple[Optional[pd.Series], Optional[pd.Series]]:
        """Extract high and low price series from factor values."""
        if "high" in factor_values and "low" in factor_values:
            high = factor_values["high"]
            low = factor_values["low"]
            if isinstance(high, pd.DataFrame):
                high = high.iloc[:, -1]
            if isinstance(low, pd.DataFrame):
                low = low.iloc[:, -1]
            return high, low
        return None, None

    def _compute_slope(self, high: pd.Series, low: pd.Series, window: int) -> pd.Series:
        """Compute rolling OLS slope of high ~ low regression."""
        slopes = []
        dates = []
        for i in range(window, len(low) + 1):
            y = high.iloc[i - window : i].values
            x = low.iloc[i - window : i].values
            x_mean = x.mean()
            y_mean = y.mean()
            denom = ((x - x_mean) ** 2).sum()
            if denom == 0:
                slopes.append(np.nan)
            else:
                beta = ((x - x_mean) * (y - y_mean)).sum() / denom
                slopes.append(beta)
            dates.append(high.index[i - 1])
        return pd.Series(slopes, index=dates, name="rsrs_slope")

    def _apply_right_skew_adjustment(
        self,
        z_score: float,
        slope_history: pd.Series,
        beta_weight: float,
        lookback: int,
    ) -> float:
        """Apply right-skew weight adjustment for passive RSRS.

        Recent high-slope observations get extra weight, making the signal
        more responsive to sustained uptrends.
        """
        half_window = lookback // 2
        recent = slope_history.iloc[-half_window:]
        older = slope_history.iloc[:-half_window]

        recent_mean = recent.mean()
        older_mean = older.mean()

        if np.isnan(recent_mean) or np.isnan(older_mean):
            return z_score

        skew_factor = 1.0 + beta_weight * max(0.0, (recent_mean - older_mean))
        return z_score * skew_factor

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral HOLD result when signal cannot be computed."""
        import datetime

        return SignalResult(
            date=pd.Timestamp(datetime.date.today()),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )


class BreadthTimingSignal(Signal):
    """Market breadth timing signal.

    Uses the advance-decline ratio (or similar breadth metrics) to gauge
    overall market participation. Broad participation in a move suggests
    a healthier trend.

    Default parameters:
        threshold_up: 0.6 (advance ratio above this is bullish)
        threshold_down: 0.4 (advance ratio below this is bearish)
        smoothing_window: 5 (days to smooth the breadth ratio)
        confirm_days: 3 (consecutive days above/below threshold to trigger)
    """

    @property
    def name(self) -> str:
        return "BREADTH_TIMING"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate market breadth timing signal.

        Args:
            factor_values: Must contain 'advance_count' and 'decline_count'
                           Series, or a 'breadth_ratio' Series directly.
            params: Optional overrides for thresholds and windows.

        Returns:
            SignalResult with BUY/SELL/HOLD based on market breadth.
        """
        defaults = {
            "threshold_up": 0.6,
            "threshold_down": 0.4,
            "smoothing_window": 5,
            "confirm_days": 3,
        }
        cfg = self._merge_params(defaults, params)

        breadth = self._extract_breadth(factor_values)
        if breadth is None or breadth.empty:
            return self._empty_result("No breadth data available")

        smoothed = breadth.rolling(window=cfg["smoothing_window"], min_periods=1).mean()

        if len(smoothed) < cfg["confirm_days"]:
            return self._empty_result("Insufficient data for breadth confirmation")

        recent = smoothed.iloc[-cfg["confirm_days"] :]

        if (recent > cfg["threshold_up"]).all():
            strength = self._normalize_strength(recent.mean(), cfg["threshold_up"], 1.0)
            return SignalResult(
                date=breadth.index[-1],
                signal_type=SignalType.BUY,
                strength=strength,
                metadata={
                    "breadth_ratio": recent.mean(),
                    "confirm_days": cfg["confirm_days"],
                },
            )

        if (recent < cfg["threshold_down"]).all():
            strength = self._normalize_strength(
                1.0 - recent.mean(), 1.0 - cfg["threshold_down"], 1.0
            )
            return SignalResult(
                date=breadth.index[-1],
                signal_type=SignalType.SELL,
                strength=strength,
                metadata={
                    "breadth_ratio": recent.mean(),
                    "confirm_days": cfg["confirm_days"],
                },
            )

        return SignalResult(
            date=breadth.index[-1],
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={
                "breadth_ratio": smoothed.iloc[-1],
                "note": "No confirmed breadth signal",
            },
        )

    def _extract_breadth(
        self, factor_values: dict[str, pd.DataFrame | pd.Series]
    ) -> Optional[pd.Series]:
        """Extract or compute breadth ratio from factor values."""
        if "breadth_ratio" in factor_values:
            data = factor_values["breadth_ratio"]
            if isinstance(data, pd.DataFrame):
                return data.iloc[:, -1]
            return data

        if "advance_count" in factor_values and "decline_count" in factor_values:
            advances = factor_values["advance_count"]
            declines = factor_values["decline_count"]
            if isinstance(advances, pd.DataFrame):
                advances = advances.iloc[:, -1]
            if isinstance(declines, pd.DataFrame):
                declines = declines.iloc[:, -1]
            total = advances + declines
            total = total.replace(0, np.nan)
            return (advances / total).dropna()

        return None

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral HOLD result when signal cannot be computed."""
        import datetime

        return SignalResult(
            date=pd.Timestamp(datetime.date.today()),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )


class SentimentTimingSignal(Signal):
    """Contrarian sentiment-based timing signal.

    Operates on the principle that extreme bullish sentiment is a contrarian
    SELL signal (market is overbought), while extreme bearish sentiment is
    a contrarian BUY signal (market is oversold).

    Default parameters:
        sentiment_upper: 0.8 (sentiment above this is extremely bullish -> SELL)
        sentiment_lower: 0.2 (sentiment below this is extremely bearish -> BUY)
        smoothing_window: 5 (days to smooth sentiment readings)
        contrarian_strength: 0.5 (base strength for contrarian signals)
    """

    @property
    def name(self) -> str:
        return "SENTIMENT_TIMING"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate contrarian sentiment timing signal.

        Args:
            factor_values: Must contain a 'sentiment' Series with values
                           in range [0, 1], where 1 = extremely bullish.
            params: Optional overrides for thresholds and windows.

        Returns:
            SignalResult with BUY/SELL/HOLD based on contrarian sentiment.
        """
        defaults = {
            "sentiment_upper": 0.8,
            "sentiment_lower": 0.2,
            "smoothing_window": 5,
            "contrarian_strength": 0.5,
        }
        cfg = self._merge_params(defaults, params)

        sentiment = self._extract_sentiment(factor_values)
        if sentiment is None or sentiment.empty:
            return self._empty_result("No sentiment data available")

        smoothed = sentiment.rolling(
            window=cfg["smoothing_window"], min_periods=1
        ).mean()
        current = smoothed.iloc[-1]

        if current > cfg["sentiment_upper"]:
            strength = self._normalize_strength(current, cfg["sentiment_upper"], 1.0)
            strength = max(cfg["contrarian_strength"], strength)
            return SignalResult(
                date=sentiment.index[-1],
                signal_type=SignalType.SELL,
                strength=strength,
                metadata={
                    "sentiment": current,
                    "note": "Extreme bullish sentiment (contrarian SELL)",
                },
            )

        if current < cfg["sentiment_lower"]:
            strength = self._normalize_strength(
                1.0 - current, 1.0 - cfg["sentiment_lower"], 1.0
            )
            strength = max(cfg["contrarian_strength"], strength)
            return SignalResult(
                date=sentiment.index[-1],
                signal_type=SignalType.BUY,
                strength=strength,
                metadata={
                    "sentiment": current,
                    "note": "Extreme bearish sentiment (contrarian BUY)",
                },
            )

        return SignalResult(
            date=sentiment.index[-1],
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"sentiment": current, "note": "Neutral sentiment"},
        )

    def _extract_sentiment(
        self, factor_values: dict[str, pd.DataFrame | pd.Series]
    ) -> Optional[pd.Series]:
        """Extract sentiment series from factor values."""
        if "sentiment" in factor_values:
            data = factor_values["sentiment"]
            if isinstance(data, pd.DataFrame):
                return data.iloc[:, -1]
            return data
        return None

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral HOLD result when signal cannot be computed."""
        import datetime

        return SignalResult(
            date=pd.Timestamp(datetime.date.today()),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )


class VolatilityTimingSignal(Signal):
    """Volatility-based position sizing signal.

    Adjusts position sizing based on market volatility. High volatility
    triggers position reduction (REDUCE signal), while low volatility
    allows for position increases (INCREASE signal).

    Default parameters:
        window: 20 (days for volatility calculation)
        high_vol_percentile: 0.8 (volatility above 80th percentile -> REDUCE)
        low_vol_percentile: 0.2 (volatility below 20th percentile -> INCREASE)
        base_position: 1.0 (baseline position multiplier)
        vol_scaling: 0.5 (how aggressively to scale positions)
    """

    @property
    def name(self) -> str:
        return "VOLATILITY_TIMING"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate volatility-based position sizing signal.

        Args:
            factor_values: Must contain 'close' Series for return-based
                           volatility, or a pre-computed 'volatility' Series.
            params: Optional overrides for windows and thresholds.

        Returns:
            SignalResult with REDUCE/INCREASE/HOLD and position strength.
        """
        defaults = {
            "window": 20,
            "high_vol_percentile": 0.8,
            "low_vol_percentile": 0.2,
            "base_position": 1.0,
            "vol_scaling": 0.5,
        }
        cfg = self._merge_params(defaults, params)

        volatility = self._extract_volatility(factor_values, cfg["window"])
        if volatility is None or volatility.empty:
            return self._empty_result("No volatility data available")

        if len(volatility) < 60:
            return self._empty_result("Insufficient data for volatility percentile")

        vol_history = volatility.iloc[:-1]
        current_vol = volatility.iloc[-1]

        high_threshold = vol_history.quantile(cfg["high_vol_percentile"])
        low_threshold = vol_history.quantile(cfg["low_vol_percentile"])

        if current_vol > high_threshold:
            excess = (
                (current_vol - high_threshold) / high_threshold
                if high_threshold > 0
                else 0
            )
            reduction = min(1.0, cfg["vol_scaling"] * excess)
            strength = 1.0 - reduction
            return SignalResult(
                date=volatility.index[-1],
                signal_type=SignalType.REDUCE,
                strength=self._normalize_strength(strength),
                metadata={
                    "current_vol": current_vol,
                    "high_threshold": high_threshold,
                    "position_multiplier": strength,
                },
            )

        if current_vol < low_threshold:
            room = (
                (low_threshold - current_vol) / low_threshold
                if low_threshold > 0
                else 0
            )
            increase = min(1.0, cfg["base_position"] + cfg["vol_scaling"] * room)
            return SignalResult(
                date=volatility.index[-1],
                signal_type=SignalType.INCREASE,
                strength=self._normalize_strength(increase),
                metadata={
                    "current_vol": current_vol,
                    "low_threshold": low_threshold,
                    "position_multiplier": increase,
                },
            )

        return SignalResult(
            date=volatility.index[-1],
            signal_type=SignalType.HOLD,
            strength=cfg["base_position"],
            metadata={"current_vol": current_vol, "note": "Normal volatility range"},
        )

    def _extract_volatility(
        self, factor_values: dict[str, pd.DataFrame | pd.Series], window: int
    ) -> Optional[pd.Series]:
        """Extract or compute volatility series from factor values."""
        if "volatility" in factor_values:
            data = factor_values["volatility"]
            if isinstance(data, pd.DataFrame):
                return data.iloc[:, -1]
            return data

        if "close" in factor_values:
            close = factor_values["close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, -1]
            returns = close.pct_change()
            return returns.rolling(window=window, min_periods=window).std() * np.sqrt(
                252
            )

        return None

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral HOLD result when signal cannot be computed."""
        import datetime

        return SignalResult(
            date=pd.Timestamp(datetime.date.today()),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )
