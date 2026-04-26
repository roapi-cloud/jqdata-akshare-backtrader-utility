"""Core data models for the signal pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any

import numpy as np
import pandas as pd


class SignalType(IntEnum):
    """Enumerated signal direction with integer ordering for comparison."""

    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


def _normalize_strength(value: float) -> float:
    """Clamp a raw strength value into [0.0, 1.0]."""
    return float(np.clip(value, 0.0, 1.0))


@dataclass(frozen=True)
class Signal:
    """A single trading signal emitted by one indicator or strategy.

    Attributes:
        timestamp: When the signal was generated.
        asset: Ticker or identifier of the target asset.
        signal_type: Directional bias (STRONG_BUY … STRONG_SELL).
        strength: Confidence magnitude in [0.0, 1.0]; always normalized.
        source: Name of the indicator / model that produced this signal.
        price: Reference price at signal generation (usually close).
        stop_loss: Suggested stop-loss price (may be None).
        take_profit: Suggested take-profit price (may be None).
        metadata: Arbitrary key-value payload for downstream consumers.
    """

    timestamp: datetime
    asset: str
    signal_type: SignalType
    strength: float
    source: str
    price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Enforce strength normalization after dataclass init."""
        object.__setattr__(self, "strength", _normalize_strength(self.strength))

    @property
    def is_bullish(self) -> bool:
        """Return True if the signal direction is BUY or STRONG_BUY."""
        return self.signal_type > SignalType.NEUTRAL

    @property
    def is_bearish(self) -> bool:
        """Return True if the signal direction is SELL or STRONG_SELL."""
        return self.signal_type < SignalType.NEUTRAL

    def signed_strength(self) -> float:
        """Return strength with sign: positive for bullish, negative for bearish."""
        return self.strength * self.signal_type.value / 2.0


@dataclass(frozen=True)
class FusedSignal:
    """Result of fusing multiple source signals into one composite view.

    Attributes:
        symbol: Asset identifier.
        timestamp: Signal generation time.
        direction: Aggregated SignalType after fusion.
        net_score: Raw fused score in [-1.0, 1.0]; positive = bullish.
        confidence: Fusion confidence in [0.0, 1.0].
        position_suggestion: Recommended position sizing ratio in [0.0, 1.0].
        component_signals: Mapping from source name to the original Signal.
    """

    symbol: str
    timestamp: datetime | None
    direction: SignalType
    net_score: float
    confidence: float
    position_suggestion: float
    component_signals: dict[str, Signal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "net_score", float(np.clip(self.net_score, -1.0, 1.0)))
        object.__setattr__(self, "confidence", _normalize_strength(self.confidence))
        object.__setattr__(
            self, "position_suggestion", _normalize_strength(self.position_suggestion)
        )


_CORE_COLS = {"datetime", "open", "high", "low", "close", "volume", "money"}


@dataclass
class MarketData:
    """OHLCV bar container backed by numpy arrays for performance.

    Attributes:
        symbol: Asset identifier (e.g. 'sh600000').
        datetime: Array of bar timestamps.
        open: Opening prices.
        high: Highest prices.
        low: Lowest prices.
        close: Closing prices.
        volume: Traded volumes.
        money: Traded turnover (currency amount).
        extra: Optional DataFrame of additional columns (features, flags, etc.).
    """

    symbol: str
    datetime: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    money: np.ndarray
    extra: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        """Validate array shapes and dtype consistency."""
        arrays = [
            self.datetime,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.money,
        ]
        lengths = {len(arr) for arr in arrays}
        if len(lengths) != 1:
            raise ValueError(
                f"All market data arrays must have the same length, got {lengths}"
            )
        self._length = lengths.pop()

        if self.extra is not None and len(self.extra) != self._length:
            raise ValueError(
                f"extra DataFrame length ({len(self.extra)}) must match "
                f"OHLCV array length ({self._length})"
            )

    def __len__(self) -> int:
        return self._length

    @classmethod
    def from_df(cls, df: pd.DataFrame, symbol: str = "") -> MarketData:
        """Construct a MarketData instance from a pandas DataFrame.

        Expected columns (case-insensitive):
            datetime / date / time, open, high, low, close, volume, money / amount.
        Any additional columns are stored in the ``extra`` attribute.

        Args:
            df: DataFrame with OHLCV columns.
            symbol: Asset identifier (optional, defaults to empty string).

        Returns:
            A new MarketData object.

        Raises:
            ValueError: If required columns are missing.
        """
        col_map = {c.lower(): c for c in df.columns}

        def _resolve(*candidates: str) -> str:
            for c in candidates:
                if c in col_map:
                    return col_map[c]
            raise ValueError(
                f"DataFrame must contain one of {candidates}; found: {list(df.columns)}"
            )

        dt_col = _resolve("datetime", "date", "time", "index")
        open_col = _resolve("open")
        high_col = _resolve("high")
        low_col = _resolve("low")
        close_col = _resolve("close")
        vol_col = _resolve("volume", "vol")
        money_col = _resolve("money", "amount", "turnover")

        dt_raw = df[dt_col].values
        datetime_arr = np.array(
            [
                pd.Timestamp(t).to_pydatetime() if not isinstance(t, datetime) else t
                for t in dt_raw
            ],
            dtype=object,
        )

        core_cols = {dt_col, open_col, high_col, low_col, close_col, vol_col, money_col}
        extra_cols = [c for c in df.columns if c not in core_cols]
        extra = df[extra_cols].copy() if extra_cols else None

        return cls(
            symbol=symbol,
            datetime=datetime_arr,
            open=df[open_col].values.astype(np.float64),
            high=df[high_col].values.astype(np.float64),
            low=df[low_col].values.astype(np.float64),
            close=df[close_col].values.astype(np.float64),
            volume=df[vol_col].values.astype(np.float64),
            money=df[money_col].values.astype(np.float64),
            extra=extra,
        )

    def slice(self, n: int) -> MarketData:
        """Return the last *n* bars (or all if ``n >= len``).

        Args:
            n: Number of most-recent bars to keep.

        Returns:
            A new MarketData containing only the last ``n`` rows.
        """
        if n <= 0:
            raise ValueError("slice size must be positive")
        start = max(0, self._length - n)
        extra_slice = self.extra.iloc[start:].copy() if self.extra is not None else None
        return MarketData(
            symbol=self.symbol,
            datetime=self.datetime[start:],
            open=self.open[start:],
            high=self.high[start:],
            low=self.low[start:],
            close=self.close[start:],
            volume=self.volume[start:],
            money=self.money[start:],
            extra=extra_slice,
        )

    def to_df(self) -> pd.DataFrame:
        """Convert back to a pandas DataFrame, merging extra columns if present."""
        core = pd.DataFrame(
            {
                "datetime": self.datetime,
                "open": self.open,
                "high": self.high,
                "low": self.low,
                "close": self.close,
                "volume": self.volume,
                "money": self.money,
            }
        )
        if self.extra is not None and not self.extra.empty:
            core = pd.concat([core, self.extra.reset_index(drop=True)], axis=1)
        return core
