"""Pattern-based and regression-based signal generators.

Implements:
- RoundingBottomGenerator: Kernel regression smoothing + symmetry validation + breakout confirmation.
- RSRSGenerator: Rolling OLS/WLS regression (high ~ low) with standardized/corrected/dampened variants.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from src.core.exceptions import IndicatorCalculationError, InsufficientDataError
from src.core.models import MarketData, Signal, SignalType
from src.indicators.base import BaseSignalGenerator

# ---------------------------------------------------------------------------
# Regression helpers
# ---------------------------------------------------------------------------

try:
    from sklearn.linear_model import LinearRegression, WeightedLinearRegression

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

try:
    import statsmodels.api as sm

    _HAS_STATSMODELS = True
except ImportError:
    _HAS_STATSMODELS = False


def _rolling_ols(
    y: np.ndarray,
    x: np.ndarray,
    window: int,
    weights: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rolling OLS regression returning (beta, r2, intercept).

    Falls back to ``np.linalg.lstsq`` if sklearn/statsmodels are unavailable.

    Parameters
    ----------
    y : ndarray
        Dependent variable (e.g. high prices).
    x : ndarray
        Independent variable (e.g. low prices).
    window : int
        Rolling window size.
    weights : ndarray, optional
        Sample weights for WLS.

    Returns
    -------
    beta : ndarray
        Slope coefficients.
    r2 : ndarray
        R-squared values.
    intercept : ndarray
        Intercept values.
    """
    n = len(y)
    beta = np.full(n, np.nan)
    r2 = np.full(n, np.nan)
    intercept = np.full(n, np.nan)

    if _HAS_SKLEARN:
        for i in range(window - 1, n):
            start = i - window + 1
            xi = x[start : i + 1].reshape(-1, 1)
            yi = y[start : i + 1]
            try:
                if weights is not None and hasattr(
                    LinearRegression, "fit"
                ):  # sklearn >= 1.2 has no WLS directly
                    # Use np.linalg.lstsq with weights as fallback
                    w = np.sqrt(weights[start : i + 1])
                    xi_w = xi * w[:, None]
                    yi_w = yi * w
                    result = np.linalg.lstsq(
                        np.hstack([xi_w, np.ones_like(xi_w)]), yi_w, rcond=None
                    )
                    coef = result[0]
                    beta[i] = coef[0]
                    intercept[i] = coef[1]
                    y_pred = xi * coef[0] + coef[1]
                    ss_res = np.sum((yi - y_pred) ** 2)
                    ss_tot = np.sum((yi - np.mean(yi)) ** 2)
                    r2[i] = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
                else:
                    model = LinearRegression().fit(xi, yi)
                    beta[i] = model.coef_[0]
                    intercept[i] = model.intercept_
                    y_pred = model.predict(xi)
                    ss_res = np.sum((yi - y_pred) ** 2)
                    ss_tot = np.sum((yi - np.mean(yi)) ** 2)
                    r2[i] = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
            except Exception:
                pass
    elif _HAS_STATSMODELS:
        for i in range(window - 1, n):
            start = i - window + 1
            xi = x[start : i + 1]
            yi = y[start : i + 1]
            try:
                xi_const = sm.add_constant(xi)
                if weights is not None:
                    w = weights[start : i + 1]
                    model = sm.WLS(yi, xi_const, weights=w).fit()
                else:
                    model = sm.OLS(yi, xi_const).fit()
                beta[i] = model.params[1]
                intercept[i] = model.params[0]
                r2_val = model.rsquared
                r2[i] = r2_val if r2_val >= 0 else 0.0
            except Exception:
                pass
    else:
        # Pure numpy fallback
        for i in range(window - 1, n):
            start = i - window + 1
            xi = x[start : i + 1]
            yi = y[start : i + 1]
            try:
                if weights is not None:
                    w = np.sqrt(weights[start : i + 1])
                    xi_w = xi * w
                    yi_w = yi * w
                else:
                    xi_w = xi
                    yi_w = yi
                A = np.vstack([xi_w, np.ones(len(xi_w))]).T
                result = np.linalg.lstsq(A, yi_w, rcond=None)
                coef = result[0]
                beta[i] = coef[0]
                intercept[i] = coef[1]
                y_pred = xi * coef[0] + coef[1]
                ss_res = np.sum((yi - y_pred) ** 2)
                ss_tot = np.sum((yi - np.mean(yi)) ** 2)
                r2[i] = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
            except Exception:
                pass

    return beta, r2, intercept


def _gaussian_kernel(x: np.ndarray, bandwidth: float) -> np.ndarray:
    """Gaussian kernel weights for kernel regression."""
    return np.exp(-0.5 * (x / bandwidth) ** 2)


def _kernel_regression_smooth(
    y: np.ndarray, bandwidth: Optional[float] = None
) -> np.ndarray:
    """Nadaraya-Watson kernel regression smoother.

    Parameters
    ----------
    y : ndarray
        Input series (e.g. close prices).
    bandwidth : float, optional
        Kernel bandwidth. Defaults to ``len(y) / 10``.

    Returns
    -------
    smoothed : ndarray
        Smoothed series of same length.
    """
    n = len(y)
    if bandwidth is None:
        bandwidth = max(n / 10, 2.0)

    x_indices = np.arange(n, dtype=float)
    smoothed = np.empty(n)

    for i in range(n):
        dist = np.abs(x_indices - i)
        w = _gaussian_kernel(dist, bandwidth)
        w_sum = w.sum()
        if w_sum > 0:
            smoothed[i] = np.dot(w, y) / w_sum
        else:
            smoothed[i] = y[i]

    return smoothed


def _find_extrema(y: np.ndarray, order: int = 5) -> tuple[list[int], list[int]]:
    """Find local minima and maxima indices in a series.

    Parameters
    ----------
    y : ndarray
        Input series.
    order : int
        Number of points on each side to use for comparison.

    Returns
    -------
    minima : list[int]
        Indices of local minima.
    maxima : list[int]
        Indices of local maxima.
    """
    minima = []
    maxima = []

    for i in range(order, len(y) - order):
        is_min = True
        is_max = True
        for j in range(i - order, i + order + 1):
            if j == i:
                continue
            if y[j] <= y[i]:
                is_min = False
            if y[j] >= y[i]:
                is_max = False
        if is_min:
            minima.append(i)
        if is_max:
            maxima.append(i)

    return minima, maxima


# ---------------------------------------------------------------------------
# RoundingBottomGenerator
# ---------------------------------------------------------------------------


class RoundingBottomGenerator(BaseSignalGenerator):
    """Detect rounding-bottom (saucer) patterns with breakout confirmation.

    Algorithm
    ---------
    1. Kernel regression smoothing on close price.
    2. Find local min/max on smoothed series.
    3. Validate symmetry (left/right shoulder height diff < 30%).
    4. Check correlation with ideal U-shape > 0.7.
    5. Breakout confirmation: Price > MA200 & Volume > 1.5x avg.
    """

    name = "rounding_bottom"
    min_history = 100

    def __init__(
        self,
        bandwidth: Optional[float] = None,
        symmetry_threshold: float = 0.30,
        correlation_threshold: float = 0.70,
        volume_multiplier: float = 1.5,
        ma_period: int = 200,
        **params: Any,
    ) -> None:
        super().__init__(**params)
        self._bandwidth = bandwidth
        self._symmetry_threshold = symmetry_threshold
        self._correlation_threshold = correlation_threshold
        self._volume_multiplier = volume_multiplier
        self._ma_period = ma_period

    def generate(self, data: List[MarketData]) -> List[Signal]:
        """Batch-compute rounding-bottom signals.

        Parameters
        ----------
        data : list[MarketData]
            Ordered list of bars (oldest first). Must have at least
            ``min_history`` bars.

        Returns
        -------
        list[Signal]
            BUY signals where a rounding bottom with breakout is confirmed.
        """
        if len(data) < self.min_history:
            raise InsufficientDataError(self.min_history, len(data), self.name)

        try:
            return self._calculate(data)
        except Exception as exc:
            raise IndicatorCalculationError(self.name, str(exc)) from exc

    def _calculate(self, data: List[MarketData]) -> List[Signal]:
        closes = np.array([d.close for d in data], dtype=float)
        volumes = np.array([d.volume for d in data], dtype=float)
        timestamps = [d.timestamp for d in data]
        symbol = data[0].symbol

        # 1. Kernel regression smoothing
        smoothed = _kernel_regression_smooth(closes, self._bandwidth)

        # 2. Find local extrema
        minima, maxima = _find_extrema(smoothed, order=5)

        signals: List[Signal] = []

        # Need at least one minimum flanked by two maxima (left & right shoulder)
        for min_idx in minima:
            # Find nearest maximum to the left (left shoulder)
            left_shoulder = None
            for mx in reversed(maxima):
                if mx < min_idx:
                    left_shoulder = mx
                    break

            # Find nearest maximum to the right (right shoulder)
            right_shoulder = None
            for mx in maxima:
                if mx > min_idx:
                    right_shoulder = mx
                    break

            if left_shoulder is None or right_shoulder is None:
                continue

            # 3. Validate symmetry: shoulder height diff < threshold
            left_height = smoothed[left_shoulder] - smoothed[min_idx]
            right_height = smoothed[right_shoulder] - smoothed[min_idx]

            if left_height <= 0 or right_height <= 0:
                continue

            height_diff_ratio = abs(left_height - right_height) / max(
                left_height, right_height
            )
            if height_diff_ratio > self._symmetry_threshold:
                continue

            # 4. Check correlation with ideal U-shape
            pattern_start = left_shoulder
            pattern_end = right_shoulder
            pattern_len = pattern_end - pattern_start + 1

            if pattern_len < 10:
                continue

            # Ideal U-shape: parabola opening upward
            x_pattern = np.arange(pattern_len, dtype=float)
            x_centered = x_pattern - pattern_len / 2.0
            ideal_u = x_centered**2
            ideal_u_normalized = (ideal_u - ideal_u.min()) / (
                ideal_u.max() - ideal_u.min() if ideal_u.max() != ideal_u.min() else 1.0
            )

            actual_pattern = smoothed[pattern_start : pattern_end + 1]
            actual_normalized = (actual_pattern - actual_pattern.min()) / (
                actual_pattern.max() - actual_pattern.min()
                if actual_pattern.max() != actual_pattern.min()
                else 1.0
            )

            corr, _ = stats.pearsonr(actual_normalized, ideal_u_normalized)

            if corr < self._correlation_threshold:
                continue

            # 5. Breakout confirmation at right shoulder
            breakout_idx = right_shoulder
            if breakout_idx >= len(data):
                continue

            # Price > MA200
            ma_start = max(0, breakout_idx - self._ma_period)
            ma_window = closes[ma_start : breakout_idx + 1]
            if len(ma_window) < self._ma_period // 2:
                continue
            ma200 = np.mean(ma_window)

            if closes[breakout_idx] <= ma200:
                continue

            # Volume > 1.5x average
            vol_start = max(0, breakout_idx - 20)
            vol_window = volumes[vol_start:breakout_idx]
            if len(vol_window) < 5:
                continue
            avg_vol = np.mean(vol_window)
            if avg_vol <= 0:
                continue

            if volumes[breakout_idx] <= self._volume_multiplier * avg_vol:
                continue

            # Signal confirmed
            strength = self._compute_strength(corr, volumes[breakout_idx], avg_vol)

            signals.append(
                Signal(
                    symbol=symbol,
                    timestamp=timestamps[breakout_idx],
                    signal_type=SignalType.BUY,
                    strength=strength,
                    indicator_name=self.name,
                    raw_value=corr,
                    metadata={
                        "correlation": float(corr),
                        "left_shoulder_idx": int(left_shoulder),
                        "bottom_idx": int(min_idx),
                        "right_shoulder_idx": int(right_shoulder),
                        "symmetry_ratio": float(1.0 - height_diff_ratio),
                        "volume_ratio": float(volumes[breakout_idx] / avg_vol),
                    },
                )
            )

        return signals

    @staticmethod
    def _compute_strength(
        correlation: float, current_volume: float, avg_volume: float
    ) -> float:
        """Compute signal strength in [0, 1] based on correlation & volume."""
        corr_strength = min(max((correlation - 0.7) / 0.3, 0.0), 1.0)
        vol_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        vol_strength = min(max((vol_ratio - 1.5) / 2.0, 0.0), 1.0)
        return float(0.6 * corr_strength + 0.4 * vol_strength)


# ---------------------------------------------------------------------------
# RSRSGenerator
# ---------------------------------------------------------------------------


class RSRSGenerator(BaseSignalGenerator):
    """Resistance Support Relative Strength (RSRS) indicator.

    Uses rolling regression of ``high ~ low`` to compute beta (slope) and R2,
    then produces standardized, corrected, and dampened variants.

    Variants
    --------
    - Standardized: z-score of beta over lookback window.
    - Corrected: z-score * R2.
    - Dampened: z-score * R2^(2*quantile) where quantile is the rank of
      current R2 within the lookback window.

    Signals
    -------
    - BUY: Dampened crosses above 0.7 (golden cross).
    - SELL: Dampened crosses below -0.7 (death cross).

    Parameters
    ----------
    n : int
        Rolling regression window (default 18).
    m : int
        Z-score lookback window (default 600).
    buy_threshold : float
        Dampened threshold for BUY (default 0.7).
    sell_threshold : float
        Dampened threshold for SELL (default -0.7).
    """

    name = "rsrs"
    min_history = 650  # M + N approximately

    def __init__(
        self,
        n: int = 18,
        m: int = 600,
        buy_threshold: float = 0.7,
        sell_threshold: float = -0.7,
        **params: Any,
    ) -> None:
        super().__init__(**params)
        self._n = n
        self._m = m
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    def generate(self, data: List[MarketData]) -> List[Signal]:
        """Batch-compute RSRS signals.

        Parameters
        ----------
        data : list[MarketData]
            Ordered list of bars (oldest first).

        Returns
        -------
        list[Signal]
            BUY/SELL signals based on dampened RSRS crossovers.
        """
        required = self._m + self._n
        if len(data) < required:
            raise InsufficientDataError(required, len(data), self.name)

        try:
            return self._calculate(data)
        except Exception as exc:
            raise IndicatorCalculationError(self.name, str(exc)) from exc

    def _calculate(self, data: List[MarketData]) -> List[Signal]:
        highs = np.array([d.high for d in data], dtype=float)
        lows = np.array([d.low for d in data], dtype=float)
        timestamps = [d.timestamp for d in data]
        symbol = data[0].symbol

        n = len(data)

        # 1. Rolling OLS: high ~ low
        beta, r2, _ = _rolling_ols(highs, lows, self._n)

        # 2. Standardized (z-score of beta over M-window)
        z_score = np.full(n, np.nan)
        for i in range(self._m + self._n - 1, n):
            window_start = i - self._m
            beta_window = beta[window_start:i]
            valid = beta_window[~np.isnan(beta_window)]
            if len(valid) < 30:
                continue
            mean_b = np.mean(valid)
            std_b = np.std(valid, ddof=1)
            if std_b > 0:
                z_score[i] = (beta[i] - mean_b) / std_b
            else:
                z_score[i] = 0.0

        # 3. Corrected: z * R2
        corrected = np.full(n, np.nan)
        for i in range(self._m + self._n - 1, n):
            if np.isnan(z_score[i]) or np.isnan(r2[i]):
                continue
            r2_safe = max(r2[i], 0.0)  # Handle negative R2
            corrected[i] = z_score[i] * r2_safe

        # 4. Dampened: z * R2^(2*quantile)
        dampened = np.full(n, np.nan)
        for i in range(self._m + self._n - 1, n):
            if np.isnan(z_score[i]) or np.isnan(r2[i]):
                continue

            r2_window = r2[i - self._m : i]
            valid_r2 = r2_window[~np.isnan(r2_window)]
            if len(valid_r2) < 2:
                continue

            # Quantile rank of current R2 within window
            current_r2 = max(r2[i], 0.0)
            quantile = stats.percentileofscore(valid_r2, current_r2) / 100.0

            exponent = 2.0 * quantile
            r2_damp = current_r2**exponent if current_r2 > 0 else 0.0
            dampened[i] = z_score[i] * r2_damp

        # 5. Signal generation: golden/death cross on dampened
        signals: List[Signal] = []
        prev_dampened = np.nan

        for i in range(self._m + self._n - 1, n):
            curr = dampened[i]
            if np.isnan(curr) or np.isnan(prev_dampened):
                prev_dampened = curr
                continue

            # BUY: crosses above threshold
            if prev_dampened <= self._buy_threshold < curr:
                strength = self._compute_strength(curr, z_score[i], r2[i])
                signals.append(
                    Signal(
                        symbol=symbol,
                        timestamp=timestamps[i],
                        signal_type=SignalType.BUY,
                        strength=strength,
                        indicator_name=self.name,
                        raw_value=float(curr),
                        metadata={
                            "beta": float(beta[i]) if not np.isnan(beta[i]) else None,
                            "r2": float(r2[i]) if not np.isnan(r2[i]) else None,
                            "z_score": float(z_score[i])
                            if not np.isnan(z_score[i])
                            else None,
                            "corrected": float(corrected[i])
                            if not np.isnan(corrected[i])
                            else None,
                            "dampened": float(curr),
                            "variant": "dampened",
                        },
                    )
                )

            # SELL: crosses below threshold
            elif prev_dampened >= self._sell_threshold > curr:
                strength = self._compute_strength(abs(curr), abs(z_score[i]), r2[i])
                signals.append(
                    Signal(
                        symbol=symbol,
                        timestamp=timestamps[i],
                        signal_type=SignalType.SELL,
                        strength=strength,
                        indicator_name=self.name,
                        raw_value=float(curr),
                        metadata={
                            "beta": float(beta[i]) if not np.isnan(beta[i]) else None,
                            "r2": float(r2[i]) if not np.isnan(r2[i]) else None,
                            "z_score": float(z_score[i])
                            if not np.isnan(z_score[i])
                            else None,
                            "corrected": float(corrected[i])
                            if not np.isnan(corrected[i])
                            else None,
                            "dampened": float(curr),
                            "variant": "dampened",
                        },
                    )
                )

            prev_dampened = curr

        return signals

    @staticmethod
    def _compute_strength(dampened_val: float, z_score: float, r2: float) -> float:
        """Compute signal strength in [0, 1]."""
        # Strength increases with absolute dampened value beyond threshold
        abs_damp = abs(dampened_val)
        strength = min(max((abs_damp - 0.7) / 0.5, 0.0), 1.0)

        # Bonus for high R2
        r2_bonus = 0.0
        if not np.isnan(r2) and r2 > 0:
            r2_bonus = min(r2 * 0.2, 0.2)

        return float(min(strength + r2_bonus, 1.0))
