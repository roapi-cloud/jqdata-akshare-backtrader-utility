"""Spectral and trend-momentum signal generators.

Provides:
- :class:`MESAGenerator`: MESA (Maximum Entropy Spectral Analysis) regime
  detection via AR spectral density and spectral flatness.
- :class:`TrendMomentumGenerator`: Trend-momentum scoring via normalized
  displacement and cumulative act/trend scores.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import numpy as np

from src.core.exceptions import InsufficientDataError
from src.core.models import MarketData, Signal, SignalType
from src.indicators.base import BaseSignalGenerator

# ---------------------------------------------------------------------------
# Optional statsmodels import
# ---------------------------------------------------------------------------
try:
    from statsmodels.tsa.ar_model import AutoReg
    from statsmodels.tsa.stattools import adfuller

    _HAS_STATSMODELS = True
except ImportError:
    _HAS_STATSMODELS = False
    AutoReg = None  # type: ignore[misc,assignment]
    adfuller = None  # type: ignore[misc,assignment]


# ---------------------------------------------------------------------------
# Helper: manual Yule-Walker AR estimation (fallback)
# ---------------------------------------------------------------------------


def _yule_walker(x: np.ndarray, max_order: int = 20) -> tuple[np.ndarray, int]:
    """Estimate AR coefficients via Yule-Walker equations.

    Selects order by minimising AIC across ``1..max_order``.

    Returns
    -------
    ar_coeffs : ndarray of shape (order,)
        AR coefficients (excluding intercept).
    best_order : int
        Selected AR order.
    """
    n = len(x)
    x = x - x.mean()
    best_aic = np.inf
    best_coeffs: np.ndarray = np.array([])
    best_order = 1

    for order in range(1, min(max_order, n // 4) + 1):
        gamma = np.array([np.mean(x[: n - k] * x[k:]) for k in range(order + 1)])

        R = np.zeros((order, order))
        for i in range(order):
            for j in range(order):
                R[i, j] = gamma[abs(i - j)]
        r = gamma[1 : order + 1]

        try:
            coeffs = np.linalg.solve(R, r)
        except np.linalg.LinAlgError:
            continue

        sigma2 = gamma[0] - coeffs @ r
        if sigma2 <= 0:
            continue

        aic = n * np.log(sigma2) + 2 * order
        if aic < best_aic:
            best_aic = aic
            best_coeffs = coeffs
            best_order = order

    if len(best_coeffs) == 0:
        best_order = 1
        best_coeffs = np.array([0.0])

    return best_coeffs, best_order


def _ar_to_spectral_density(ar_coeffs: np.ndarray, n_freqs: int = 256) -> np.ndarray:
    """Compute spectral density from AR coefficients.

    S(f) = sigma^2 / |1 - sum(a_k * exp(-2*pi*i*f*k))|^2
    """
    freqs = np.linspace(0, 0.5, n_freqs)
    denom = np.ones_like(freqs, dtype=complex)
    for k, a in enumerate(ar_coeffs, start=1):
        denom -= a * np.exp(-2j * np.pi * freqs * k)
    power = 1.0 / np.abs(denom) ** 2
    return power


def _spectral_flatness(power: np.ndarray) -> float:
    """Geometric mean / arithmetic mean of spectral power."""
    power = power[power > 0]
    if len(power) == 0:
        return 0.0
    log_mean = np.mean(np.log(power))
    geo_mean = np.exp(log_mean)
    arith_mean = np.mean(power)
    if arith_mean == 0:
        return 0.0
    return float(geo_mean / arith_mean)


def _adf_test(x: np.ndarray) -> float:
    """Augmented Dickey-Fuller test; returns p-value."""
    if _HAS_STATSMODELS and adfuller is not None:
        result = adfuller(x)
        return float(result[1])
    x = x - x.mean()
    n = len(x)
    if n < 2:
        return 1.0
    rho = np.sum(x[:-1] * x[1:]) / np.sum(x**2)
    p_approx = max(0.0, min(1.0, 1.0 - abs(rho)))
    return p_approx


def _difference_once(x: np.ndarray) -> np.ndarray:
    """Return first differences."""
    return np.diff(x)


# ---------------------------------------------------------------------------
# MESAGenerator
# ---------------------------------------------------------------------------


class MESAGenerator(BaseSignalGenerator):
    """MESA regime detector via AR spectral analysis.

    Algorithm
    ---------
    1. ADF test for stationarity; difference series if non-stationary.
    2. Fit AR model (order selected via AIC).
    3. Compute spectral density from AR coefficients.
    4. Spectral Flatness = geometric_mean / arithmetic_mean.
    5. Regime: Flatness > 0.6 -> Trending, else Oscillating.
    6. Signal: Trending -> BUY/SELL by AR trend direction; Oscillating -> NEUTRAL.
    """

    name = "mesa"
    min_history = 200
    supports_incremental = False

    def __init__(
        self, max_ar_order: int = 20, flatness_threshold: float = 0.6, **params: Any
    ) -> None:
        super().__init__(
            max_ar_order=max_ar_order, flatness_threshold=flatness_threshold, **params
        )
        self._max_ar_order = max_ar_order
        self._flatness_threshold = flatness_threshold

    def generate(self, data: List[MarketData]) -> List[Signal]:
        if len(data) < self.min_history:
            raise InsufficientDataError(
                required=self.min_history,
                actual=len(data),
                indicator=self.name,
            )

        closes = np.array([bar.close for bar in data], dtype=float)
        timestamps = [bar.timestamp for bar in data]
        symbol = data[0].symbol if hasattr(data[0], "symbol") else ""

        signals: List[Signal] = []

        for i in range(self.min_history - 1, len(closes)):
            window = closes[: i + 1]
            try:
                sig = self._compute_single(window, symbol, timestamps[i])
            except Exception:
                sig = Signal(
                    timestamp=timestamps[i],
                    asset=symbol,
                    signal_type=SignalType.NEUTRAL,
                    strength=0.5,
                    source=self.name,
                    price=float(closes[i]),
                    metadata={"error": True},
                )
            signals.append(sig)

        return signals

    def _compute_single(self, prices: np.ndarray, symbol: str, ts: datetime) -> Signal:
        series = prices.copy()
        p_value = _adf_test(series)
        if p_value > 0.05 and len(series) > 2:
            series = _difference_once(series)

        if len(series) < 10:
            return self._neutral_signal(symbol, ts, float(prices[-1]), 0.0)

        ar_coeffs, ar_order = _yule_walker(series, self._max_ar_order)

        power = _ar_to_spectral_density(ar_coeffs)

        flatness = _spectral_flatness(power)

        is_trending = flatness > self._flatness_threshold

        if is_trending:
            ar_sum = float(np.sum(ar_coeffs))
            raw_value = ar_sum
            if ar_sum > 0.1:
                sig_type = SignalType.BUY
                strength = min(1.0, max(0.0, 0.5 + 0.5 * ar_sum))
            elif ar_sum < -0.1:
                sig_type = SignalType.SELL
                strength = min(1.0, max(0.0, 0.5 - 0.5 * ar_sum))
            else:
                sig_type = SignalType.NEUTRAL
                strength = 0.5
        else:
            sig_type = SignalType.NEUTRAL
            strength = 0.5
            raw_value = 0.0

        return Signal(
            timestamp=ts,
            asset=symbol,
            signal_type=sig_type,
            strength=round(float(strength), 4),
            source=self.name,
            price=float(prices[-1]),
            raw_value=round(float(raw_value), 6),
            metadata={
                "flatness": round(float(flatness), 4),
                "ar_order": ar_order,
                "regime": "trending" if is_trending else "oscillating",
                "adf_pvalue": round(float(p_value), 4),
            },
        )

    def _neutral_signal(
        self, symbol: str, ts: datetime, price: float, raw_value: float
    ) -> Signal:
        return Signal(
            timestamp=ts,
            asset=symbol,
            signal_type=SignalType.NEUTRAL,
            strength=0.5,
            source=self.name,
            price=price,
            raw_value=raw_value,
            metadata={"insufficient_data_after_diff": True},
        )


# ---------------------------------------------------------------------------
# TrendMomentumGenerator
# ---------------------------------------------------------------------------


class TrendMomentumGenerator(BaseSignalGenerator):
    """Trend-momentum signal via normalised displacement scoring.

    Algorithm
    ---------
    1. Normalize price: compound method
       ``norm = (sign(pct_change) + sign(close - MA5)) / 2``.
    2. Cumulative sum to get displacement series.
    3. ``ActScore`` = net displacement; ``TrendScore`` = sum of squared displacements.
    4. ``Ultimate = max(opposite, absolute) / N^1.5``.
    5. Signal: High Ultimate + Positive Act -> BUY; High Ultimate + Negative Act -> SELL.
    """

    name = "trend_momentum"
    min_history = 50
    supports_incremental = False

    def __init__(
        self, ma_period: int = 5, ultimate_threshold: float = 0.3, **params: Any
    ) -> None:
        super().__init__(
            ma_period=ma_period, ultimate_threshold=ultimate_threshold, **params
        )
        self._ma_period = ma_period
        self._ultimate_threshold = ultimate_threshold

    def generate(self, data: MarketData) -> List[Signal]:
        if len(data.close) < self.min_history:
            raise InsufficientDataError(
                required=self.min_history,
                actual=len(data.close),
                indicator=self.name,
            )

        closes = np.array(data.close, dtype=float)
        timestamps = list(data.datetime)
        symbol = data.symbol if hasattr(data, "symbol") else ""

        signals: List[Signal] = []

        for i in range(self.min_history - 1, len(closes)):
            window = closes[: i + 1]
            try:
                sig = self._compute_single(window, symbol, timestamps[i])
            except Exception:
                sig = Signal(
                    timestamp=timestamps[i],
                    asset=symbol,
                    signal_type=SignalType.NEUTRAL,
                    strength=0.5,
                    source=self.name,
                    price=float(closes[i]),
                    metadata={"error": True},
                )
            signals.append(sig)

        return signals

    def _compute_single(self, prices: np.ndarray, symbol: str, ts: datetime) -> Signal:
        n = len(prices)

        pct_chg = np.zeros(n)
        pct_chg[1:] = np.diff(prices) / prices[:-1]

        ma = np.full(n, np.nan)
        for i in range(self._ma_period - 1, n):
            ma[i] = np.mean(prices[i - self._ma_period + 1 : i + 1])

        sign_pct = np.sign(pct_chg)
        sign_ma = np.sign(prices - ma)
        sign_ma = np.where(np.isnan(sign_ma), 0.0, sign_ma)

        norm = (sign_pct + sign_ma) / 2.0

        displacement = np.cumsum(norm)

        act_score = displacement[-1]

        trend_score = float(np.sum(displacement**2))

        direction = np.sign(np.diff(displacement))
        flips = np.where(np.diff(direction) != 0)[0]
        if len(flips) > 0:
            opposite = float(np.sum(np.abs(np.diff(displacement)[flips])))
        else:
            opposite = 0.0

        absolute = float(np.sum(np.abs(np.diff(displacement))))

        n_power = n**1.5
        if n_power == 0:
            n_power = 1.0

        ultimate = max(opposite, absolute) / n_power

        raw_value = ultimate * np.sign(act_score)

        if ultimate > self._ultimate_threshold:
            if act_score > 0:
                sig_type = SignalType.BUY
                strength = min(1.0, max(0.5, 0.5 + 0.5 * ultimate))
            elif act_score < 0:
                sig_type = SignalType.SELL
                strength = min(1.0, max(0.5, 0.5 + 0.5 * ultimate))
            else:
                sig_type = SignalType.NEUTRAL
                strength = 0.5
        else:
            sig_type = SignalType.NEUTRAL
            strength = max(0.0, min(0.5, ultimate / self._ultimate_threshold * 0.5))

        return Signal(
            timestamp=ts,
            asset=symbol,
            signal_type=sig_type,
            strength=round(float(strength), 4),
            source=self.name,
            price=float(prices[-1]),
            raw_value=round(float(raw_value), 6),
            metadata={
                "act_score": round(float(act_score), 4),
                "trend_score": round(float(trend_score), 4),
                "ultimate_score": round(float(ultimate), 4),
                "opposite": round(float(opposite), 4),
                "absolute": round(float(absolute), 4),
            },
        )
