"""Chan Theory (缠论) Signal Generator.

Implements the core Chan Theory structure identification pipeline:
  1. K-bar standardization (inclusion relationship handling)
  2. FenXing (分型) — Top/Bottom divergence point detection
  3. Bi (笔) — Stroke construction with minimum bar requirements
  4. ZhongShu (中枢) — Center overlap identification
  5. Signal generation — FIRST_BUY/SELL, THIRD_BUY/SELL, DIVERGENCE

References:
  - ChanLun (缠论) original theory by ChanZhongShuoChan
  - Standard K-bar merge rules for inclusion relationships
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Tuple

import numpy as np

from src.core.exceptions import InsufficientDataError
from src.core.models import MarketData, Signal, SignalType
from src.indicators.base import BaseSignalGenerator
from src.indicators.strength_normalizer import StrengthNormalizer


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


class BiDirection(Enum):
    """Direction of a Bi (stroke)."""

    UP = "up"
    DOWN = "down"


class FenXingType(Enum):
    """Type of FenXing (分型)."""

    TOP = "top"
    BOTTOM = "bottom"


@dataclass
class StandardizedBar:
    """A K-bar after inclusion relationship processing."""

    index: int
    high: float
    low: float
    close: float
    timestamp: datetime
    direction: int


@dataclass
class FenXing:
    """A FenXing (分型) point."""

    index: int
    original_index: int
    fx_type: FenXingType
    high: float
    low: float
    close: float
    timestamp: datetime


@dataclass
class Bi:
    """A Bi (笔) — stroke connecting two FenXing points."""

    start_fx: FenXing
    end_fx: FenXing
    direction: BiDirection
    start_idx: int
    end_idx: int
    high: float
    low: float
    bar_count: int


@dataclass
class ZhongShu:
    """A ZhongShu (中枢) — center formed by overlapping Bi ranges."""

    start_bi_idx: int
    end_bi_idx: int
    zg: float
    zd: float
    bi_count: int
    start_timestamp: datetime
    end_timestamp: datetime
    is_broken: bool = False


# ---------------------------------------------------------------------------
# MACD helper (pure numpy, no talib dependency)
# ---------------------------------------------------------------------------


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Compute Exponential Moving Average using numpy."""
    result = np.empty_like(data, dtype=np.float64)
    alpha = 2.0 / (period + 1.0)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def _compute_macd(
    close: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute MACD (DIF, DEA, Histogram) using pure numpy.

    Returns:
        dif: Fast EMA - Slow EMA
        dea: EMA of DIF
        hist: 2 * (DIF - DEA)  (convention used in Chinese markets)
    """
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal_period)
    hist = 2.0 * (dif - dea)
    return dif, dea, hist


# ---------------------------------------------------------------------------
# Chan Theory Generator
# ---------------------------------------------------------------------------


class ChanTheoryGenerator(BaseSignalGenerator):
    """Chan Theory (缠论) signal generator.

    Identifies market structure via Bi (strokes), ZhongShu (centers),
    and generates trading signals based on FenXing confirmation,
    ZhongShu breakouts, and MACD divergence.

    Parameters:
        min_bi_kbars: Minimum number of standardized bars required to
            form a valid Bi. Default 4 (standard Chan Theory value).
        use_macd_div: Whether to compute and use MACD divergence for
            signal strength enhancement. Default True.
    """

    name = "chan_theory"
    min_history = 150

    def __init__(
        self,
        min_bi_kbars: int = 4,
        use_macd_div: bool = True,
        **params: Any,
    ) -> None:
        super().__init__(
            min_bi_kbars=min_bi_kbars,
            use_macd_div=use_macd_div,
            **params,
        )
        self._min_bi_kbars = min_bi_kbars
        self._use_macd_div = use_macd_div
        self._normalizer = StrengthNormalizer(history_window=250)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def generate(self, data: List[MarketData]) -> List[Signal]:
        """Generate Chan Theory signals from market data.

        Accepts a list containing one or more MarketData instances.
        Each MarketData holds OHLCV arrays; the first instance is used.

        Pipeline:
          1. Validate data length
          2. K-bar standardization (inclusion handling)
          3. FenXing identification
          4. Bi (stroke) construction
          5. ZhongShu (center) detection
          6. Signal generation with strength normalization

        Args:
            data: List of MarketData (array-based OHLCV containers).

        Returns:
            List of Signal objects.

        Raises:
            InsufficientDataError: If data length < min_history.
        """
        if not data:
            raise InsufficientDataError(
                required=self.min_history,
                actual=0,
                indicator=self.name,
            )

        md = data[0]
        n_bars = len(md)

        if n_bars < self.min_history:
            raise InsufficientDataError(
                required=self.min_history,
                actual=n_bars,
                indicator=self.name,
            )

        closes = md.close.astype(np.float64)
        highs = md.high.astype(np.float64)
        lows = md.low.astype(np.float64)
        timestamps = md.datetime

        std_bars = self._standardize_kbars(timestamps, highs, lows, closes)

        if len(std_bars) < 7:
            return []

        fenxing_list = self._identify_fenxing(std_bars)

        if len(fenxing_list) < 2:
            return []

        bi_list = self._construct_bi(fenxing_list, std_bars)

        if len(bi_list) < 2:
            return []

        zhongshu_list = self._identify_zhongshu(bi_list)

        if self._use_macd_div:
            dif, dea, hist = _compute_macd(closes)
        else:
            dif = dea = hist = np.zeros_like(closes)

        signals = self._generate_signals(
            md,
            bi_list,
            zhongshu_list,
            dif,
            dea,
            hist,
            closes,
        )

        return signals

    # ------------------------------------------------------------------
    # K-bar standardization (包含关系处理)
    # ------------------------------------------------------------------

    def _standardize_kbars(
        self,
        timestamps: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> List[StandardizedBar]:
        """Process K-bars by resolving inclusion relationships.

        Two consecutive bars have an inclusion relationship when one's
        [low, high] range is fully contained within the other's.

        Merge rules:
          - Uptrend context: new_high = max(h1, h2), new_low = max(l1, l2)
          - Downtrend context: new_high = min(h1, h2), new_low = min(l1, l2)
        """
        n = len(highs)
        if n < 2:
            ts = timestamps[0]
            if not isinstance(ts, datetime):
                ts = self._to_datetime(ts)
            return [
                StandardizedBar(
                    index=0,
                    high=float(highs[0]),
                    low=float(lows[0]),
                    close=float(closes[0]),
                    timestamp=ts,
                    direction=0,
                )
            ]

        result: List[StandardizedBar] = []
        ts0 = timestamps[0]
        if not isinstance(ts0, datetime):
            ts0 = self._to_datetime(ts0)

        result.append(
            StandardizedBar(
                index=0,
                high=float(highs[0]),
                low=float(lows[0]),
                close=float(closes[0]),
                timestamp=ts0,
                direction=0,
            )
        )

        for i in range(1, n):
            prev = result[-1]
            curr_high = float(highs[i])
            curr_low = float(lows[i])

            is_included = (curr_high <= prev.high and curr_low >= prev.low) or (
                curr_high >= prev.high and curr_low <= prev.low
            )

            if is_included:
                if len(result) >= 2:
                    prev_prev = result[-2]
                    if prev.high > prev_prev.high:
                        direction = 1
                    elif prev.low < prev_prev.low:
                        direction = -1
                    else:
                        direction = prev.direction
                else:
                    direction = prev.direction

                if direction >= 0:
                    merged_high = max(prev.high, curr_high)
                    merged_low = max(prev.low, curr_low)
                else:
                    merged_high = min(prev.high, curr_high)
                    merged_low = min(prev.low, curr_low)

                ts = timestamps[i]
                if not isinstance(ts, datetime):
                    ts = self._to_datetime(ts)

                result[-1] = StandardizedBar(
                    index=i,
                    high=merged_high,
                    low=merged_low,
                    close=float(closes[i]),
                    timestamp=ts,
                    direction=direction,
                )
            else:
                if curr_high > prev.high:
                    direction = 1
                elif curr_low < prev.low:
                    direction = -1
                else:
                    direction = prev.direction

                ts = timestamps[i]
                if not isinstance(ts, datetime):
                    ts = self._to_datetime(ts)

                result.append(
                    StandardizedBar(
                        index=i,
                        high=curr_high,
                        low=curr_low,
                        close=float(closes[i]),
                        timestamp=ts,
                        direction=direction,
                    )
                )

        return result

    @staticmethod
    def _to_datetime(ts: Any) -> datetime:
        """Convert a timestamp value to datetime."""
        import pandas as pd

        if isinstance(ts, pd.Timestamp):
            return ts.to_pydatetime()
        if isinstance(ts, datetime):
            return ts
        return pd.Timestamp(ts).to_pydatetime()

    # ------------------------------------------------------------------
    # FenXing (分型) identification
    # ------------------------------------------------------------------

    def _identify_fenxing(
        self,
        std_bars: List[StandardizedBar],
    ) -> List[FenXing]:
        """Identify Top and Bottom FenXing points.

        Top FenXing: bar[i].high >= bar[i-1].high AND bar[i].high > bar[i+1].high
        Bottom FenXing: bar[i].low <= bar[i-1].low AND bar[i].low < bar[i+1].low
        """
        if len(std_bars) < 3:
            return []

        fenxing_list: List[FenXing] = []
        n = len(std_bars)

        i = 1
        while i < n - 1:
            prev_bar = std_bars[i - 1]
            curr_bar = std_bars[i]

            j = i + 1
            while (
                j < n - 1
                and std_bars[j].high == curr_bar.high
                and std_bars[j].low == curr_bar.low
            ):
                j += 1
            compare_bar = std_bars[j] if j < n else std_bars[-1]

            is_top = (
                curr_bar.high >= prev_bar.high and curr_bar.high > compare_bar.high
            ) or (curr_bar.high > prev_bar.high and curr_bar.high >= compare_bar.high)

            is_bottom = (
                curr_bar.low <= prev_bar.low and curr_bar.low < compare_bar.low
            ) or (curr_bar.low < prev_bar.low and curr_bar.low <= compare_bar.low)

            if is_top:
                fenxing_list.append(
                    FenXing(
                        index=0,
                        original_index=curr_bar.index,
                        fx_type=FenXingType.TOP,
                        high=curr_bar.high,
                        low=curr_bar.low,
                        close=curr_bar.close,
                        timestamp=curr_bar.timestamp,
                    )
                )
                i = j + 1
                continue

            if is_bottom:
                fenxing_list.append(
                    FenXing(
                        index=0,
                        original_index=curr_bar.index,
                        fx_type=FenXingType.BOTTOM,
                        high=curr_bar.high,
                        low=curr_bar.low,
                        close=curr_bar.close,
                        timestamp=curr_bar.timestamp,
                    )
                )
                i = j + 1
                continue

            i += 1

        cleaned: List[FenXing] = []
        for fx in fenxing_list:
            if cleaned and cleaned[-1].fx_type == fx.fx_type:
                if fx.fx_type == FenXingType.TOP:
                    if fx.high > cleaned[-1].high:
                        cleaned[-1] = fx
                else:
                    if fx.low < cleaned[-1].low:
                        cleaned[-1] = fx
            else:
                cleaned.append(fx)

        for idx, fx in enumerate(cleaned):
            fx.index = idx

        return cleaned

    # ------------------------------------------------------------------
    # Bi (笔) construction
    # ------------------------------------------------------------------

    def _construct_bi(
        self,
        fenxing_list: List[FenXing],
        std_bars: List[StandardizedBar],
    ) -> List[Bi]:
        """Construct Bi (strokes) from alternating FenXing points."""
        if len(fenxing_list) < 2:
            return []

        bi_list: List[Bi] = []

        for i in range(len(fenxing_list) - 1):
            start_fx = fenxing_list[i]
            end_fx = fenxing_list[i + 1]

            if start_fx.fx_type == end_fx.fx_type:
                continue

            start_std_idx = self._find_std_bar_index(std_bars, start_fx.original_index)
            end_std_idx = self._find_std_bar_index(std_bars, end_fx.original_index)

            if start_std_idx < 0 or end_std_idx < 0:
                continue

            bar_count = abs(end_std_idx - start_std_idx) + 1

            if bar_count < self._min_bi_kbars:
                continue

            if start_fx.fx_type == FenXingType.BOTTOM:
                direction = BiDirection.UP
                bi_high = end_fx.high
                bi_low = start_fx.low
            else:
                direction = BiDirection.DOWN
                bi_high = start_fx.high
                bi_low = end_fx.low

            bi_list.append(
                Bi(
                    start_fx=start_fx,
                    end_fx=end_fx,
                    direction=direction,
                    start_idx=start_std_idx,
                    end_idx=end_std_idx,
                    high=bi_high,
                    low=bi_low,
                    bar_count=bar_count,
                )
            )

        return bi_list

    @staticmethod
    def _find_std_bar_index(
        std_bars: List[StandardizedBar],
        original_index: int,
    ) -> int:
        """Find the index in std_bars that corresponds to an original index."""
        for idx, bar in enumerate(std_bars):
            if bar.index == original_index:
                return idx
        best_idx = -1
        best_dist = float("inf")
        for idx, bar in enumerate(std_bars):
            dist = abs(bar.index - original_index)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx

    # ------------------------------------------------------------------
    # ZhongShu (中枢) identification
    # ------------------------------------------------------------------

    def _identify_zhongshu(self, bi_list: List[Bi]) -> List[ZhongShu]:
        """Identify ZhongShu (centers) from overlapping Bi ranges.

        A ZhongShu is formed when at least 3 consecutive Bi have
        overlapping price ranges:
          ZG = min(high_1, high_2, high_3)
          ZD = max(low_1, low_2, low_3)
          Valid if ZG > ZD
        """
        if len(bi_list) < 3:
            return []

        zhongshu_list: List[ZhongShu] = []
        i = 0

        while i <= len(bi_list) - 3:
            bi1 = bi_list[i]
            bi2 = bi_list[i + 1]
            bi3 = bi_list[i + 2]

            zg = min(bi1.high, bi2.high, bi3.high)
            zd = max(bi1.low, bi2.low, bi3.low)

            if zg <= zd:
                i += 1
                continue

            end_bi_idx = i + 2
            current_zg = zg
            current_zd = zd

            for j in range(i + 3, len(bi_list)):
                bi_next = bi_list[j]
                if bi_next.high > current_zd and bi_next.low < current_zg:
                    current_zg = min(current_zg, bi_next.high)
                    current_zd = max(current_zd, bi_next.low)
                    end_bi_idx = j
                else:
                    break

            if end_bi_idx - i + 1 >= 3:
                zhongshu_list.append(
                    ZhongShu(
                        start_bi_idx=i,
                        end_bi_idx=end_bi_idx,
                        zg=current_zg,
                        zd=current_zd,
                        bi_count=end_bi_idx - i + 1,
                        start_timestamp=bi_list[i].start_fx.timestamp,
                        end_timestamp=bi_list[end_bi_idx].end_fx.timestamp,
                        is_broken=False,
                    )
                )

            i = end_bi_idx + 1

        return zhongshu_list

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------

    def _generate_signals(
        self,
        md: MarketData,
        bi_list: List[Bi],
        zhongshu_list: List[ZhongShu],
        dif: np.ndarray,
        dea: np.ndarray,
        hist: np.ndarray,
        closes: np.ndarray,
    ) -> List[Signal]:
        """Generate trading signals from Chan Theory structure.

        Signal types:
          - FIRST_BUY: Bottom FenXing confirmation after a DOWN Bi
          - FIRST_SELL: Top FenXing confirmation after an UP Bi
          - THIRD_BUY: Price breaks above ZhongShu, pulls back without re-entry
          - THIRD_SELL: Price breaks below ZhongShu, pulls back without re-entry
          - DIVERGENCE: MACD divergence at Bi endpoints
        """
        signals: List[Signal] = []
        asset = self._infer_asset(md)

        for bi in bi_list:
            end_fx = bi.end_fx
            ts = end_fx.timestamp
            price = end_fx.close

            if bi.direction == BiDirection.UP and end_fx.fx_type == FenXingType.TOP:
                raw_strength = self._calc_bi_strength(bi, hist, closes)
                strength = self._normalizer.normalize(raw_strength)
                signals.append(
                    Signal(
                        timestamp=ts,
                        asset=asset,
                        signal_type=SignalType.SELL,
                        strength=strength,
                        source=self.name,
                        price=price,
                        metadata={
                            "signal_subtype": "FIRST_SELL",
                            "bi_direction": bi.direction.value,
                            "zhongshu_range": None,
                            "divergence_type": None,
                            "bi_high": bi.high,
                            "bi_low": bi.low,
                            "bi_bar_count": bi.bar_count,
                        },
                    )
                )

            elif (
                bi.direction == BiDirection.DOWN
                and end_fx.fx_type == FenXingType.BOTTOM
            ):
                raw_strength = self._calc_bi_strength(bi, hist, closes)
                strength = self._normalizer.normalize(raw_strength)
                signals.append(
                    Signal(
                        timestamp=ts,
                        asset=asset,
                        signal_type=SignalType.BUY,
                        strength=strength,
                        source=self.name,
                        price=price,
                        metadata={
                            "signal_subtype": "FIRST_BUY",
                            "bi_direction": bi.direction.value,
                            "zhongshu_range": None,
                            "divergence_type": None,
                            "bi_high": bi.high,
                            "bi_low": bi.low,
                            "bi_bar_count": bi.bar_count,
                        },
                    )
                )

        for zs in zhongshu_list:
            for bi_idx in range(zs.end_bi_idx + 1, len(bi_list)):
                bi = bi_list[bi_idx]

                if bi.direction == BiDirection.UP and bi.low > zs.zg:
                    raw_strength = self._calc_breakout_strength(bi, zs, hist)
                    strength = self._normalizer.normalize(raw_strength)
                    signals.append(
                        Signal(
                            timestamp=bi.end_fx.timestamp,
                            asset=asset,
                            signal_type=SignalType.BUY,
                            strength=strength,
                            source=self.name,
                            price=bi.end_fx.close,
                            metadata={
                                "signal_subtype": "THIRD_BUY",
                                "bi_direction": bi.direction.value,
                                "zhongshu_range": [round(zs.zd, 4), round(zs.zg, 4)],
                                "divergence_type": None,
                                "bi_high": bi.high,
                                "bi_low": bi.low,
                            },
                        )
                    )
                    zs.is_broken = True
                    break

                if bi.direction == BiDirection.DOWN and bi.high < zs.zd:
                    raw_strength = self._calc_breakout_strength(bi, zs, hist)
                    strength = self._normalizer.normalize(raw_strength)
                    signals.append(
                        Signal(
                            timestamp=bi.end_fx.timestamp,
                            asset=asset,
                            signal_type=SignalType.SELL,
                            strength=strength,
                            source=self.name,
                            price=bi.end_fx.close,
                            metadata={
                                "signal_subtype": "THIRD_SELL",
                                "bi_direction": bi.direction.value,
                                "zhongshu_range": [round(zs.zd, 4), round(zs.zg, 4)],
                                "divergence_type": None,
                                "bi_high": bi.high,
                                "bi_low": bi.low,
                            },
                        )
                    )
                    zs.is_broken = True
                    break

        if self._use_macd_div and len(bi_list) >= 2:
            for i in range(1, len(bi_list)):
                prev_bi = bi_list[i - 1]
                curr_bi = bi_list[i]

                if prev_bi.direction != curr_bi.direction:
                    continue

                div_type = self._check_divergence(prev_bi, curr_bi, hist, closes)
                if div_type is None:
                    continue

                if curr_bi.direction == BiDirection.UP:
                    signal_type = SignalType.SELL
                else:
                    signal_type = SignalType.BUY

                end_fx = curr_bi.end_fx
                raw_strength = abs(
                    self._calc_macd_area(prev_bi, hist)
                    - self._calc_macd_area(curr_bi, hist)
                )
                strength = self._normalizer.normalize(raw_strength)

                signals.append(
                    Signal(
                        timestamp=end_fx.timestamp,
                        asset=asset,
                        signal_type=signal_type,
                        strength=strength,
                        source=self.name,
                        price=end_fx.close,
                        metadata={
                            "signal_subtype": "DIVERGENCE",
                            "bi_direction": curr_bi.direction.value,
                            "zhongshu_range": None,
                            "divergence_type": div_type,
                            "bi_high": curr_bi.high,
                            "bi_low": curr_bi.low,
                            "prev_bi_high": prev_bi.high,
                            "prev_bi_low": prev_bi.low,
                        },
                    )
                )

        return signals

    @staticmethod
    def _infer_asset(md: MarketData) -> str:
        """Try to infer asset identifier from MarketData."""
        extra = getattr(md, "extra", {})
        if isinstance(extra, dict) and "symbol" in extra:
            return str(extra["symbol"])
        if isinstance(extra, dict) and "asset" in extra:
            return str(extra["asset"])
        return "UNKNOWN"

    # ------------------------------------------------------------------
    # Strength calculation helpers
    # ------------------------------------------------------------------

    def _calc_bi_strength(
        self,
        bi: Bi,
        hist: np.ndarray,
        closes: np.ndarray,
    ) -> float:
        """Calculate raw strength for a FIRST_BUY/FIRST_SELL signal."""
        price_move = abs(bi.high - bi.low) / max(bi.low, 1e-9)
        macd_area = self._calc_macd_area(bi, hist)
        bar_factor = min(bi.bar_count / 20.0, 1.0)
        return price_move * 0.4 + abs(macd_area) * 0.4 + bar_factor * 0.2

    def _calc_breakout_strength(
        self,
        bi: Bi,
        zs: ZhongShu,
        hist: np.ndarray,
    ) -> float:
        """Calculate raw strength for a THIRD_BUY/THIRD_SELL signal."""
        if bi.direction == BiDirection.UP:
            breakout_dist = (bi.low - zs.zg) / max(zs.zg, 1e-9)
        else:
            breakout_dist = (zs.zd - bi.high) / max(zs.zd, 1e-9)
        macd_area = self._calc_macd_area(bi, hist)
        return max(breakout_dist, 0.0) * 0.5 + abs(macd_area) * 0.5

    def _calc_macd_area(self, bi: Bi, hist: np.ndarray) -> float:
        """Calculate the MACD histogram area during a Bi."""
        start = max(0, bi.start_idx - 1)
        end = min(len(hist), bi.end_idx + 1)

        if start >= end:
            return 0.0

        area = 0.0
        for i in range(start, end):
            if bi.direction == BiDirection.UP and hist[i] > 0:
                area += hist[i]
            elif bi.direction == BiDirection.DOWN and hist[i] < 0:
                area -= hist[i]
        return area

    def _check_divergence(
        self,
        prev_bi: Bi,
        curr_bi: Bi,
        hist: np.ndarray,
        closes: np.ndarray,
    ) -> Optional[str]:
        """Check for MACD divergence between two consecutive same-direction Bi."""
        prev_area = self._calc_macd_area(prev_bi, hist)
        curr_area = self._calc_macd_area(curr_bi, hist)

        if curr_bi.direction == BiDirection.UP:
            if curr_bi.high > prev_bi.high and curr_area < prev_area * 0.8:
                return "top_divergence"
        else:
            if curr_bi.low < prev_bi.low and curr_area < prev_area * 0.8:
                return "bottom_divergence"

        return None
