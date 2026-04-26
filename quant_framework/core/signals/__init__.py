"""Signal layer for generating trading signals from factors."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class SignalType(Enum):
    LONG = 1
    SHORT = -1
    HOLD = 0


@dataclass
class Signal:
    """A trading signal for a single symbol at a point in time."""

    code: str
    signal_type: SignalType
    strength: float
    date: Optional[pd.Timestamp] = None
    reason: str = ""


class SignalGenerator:
    """Generates trading signals from factor values.

    Args:
        upper_threshold: Factor value above which to generate LONG signal.
        lower_threshold: Factor value below which to generate SHORT signal.
    """

    def __init__(
        self,
        upper_threshold: float = 0.7,
        lower_threshold: float = 0.3,
    ) -> None:
        self.upper_threshold = upper_threshold
        self.lower_threshold = lower_threshold

    def generate_from_factor(
        self,
        factor_values: pd.Series,
        date: Optional[pd.Timestamp] = None,
    ) -> list:
        """Generate signals from a cross-section of factor values."""
        signals = []
        for code, value in factor_values.items():
            if pd.isna(value):
                continue

            if value >= self.upper_threshold:
                stype = SignalType.LONG
                strength = min(1.0, value)
            elif value <= self.lower_threshold:
                stype = SignalType.SHORT
                strength = min(1.0, 1.0 - value)
            else:
                stype = SignalType.HOLD
                strength = 0.0

            signals.append(
                Signal(
                    code=code,
                    signal_type=stype,
                    strength=strength,
                    date=date,
                    reason=f"factor_value={value:.4f}",
                )
            )

        return signals

    def generate_top_bottom(
        self,
        factor_values: pd.Series,
        top_n: int = 10,
        bottom_n: int = 10,
        date: Optional[pd.Timestamp] = None,
    ) -> list:
        """Generate LONG signals for top-N and SHORT for bottom-N."""
        signals = []
        sorted_vals = factor_values.dropna().sort_values()

        for code in sorted_vals.head(bottom_n).index:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.SHORT,
                    strength=1.0,
                    date=date,
                    reason="bottom_n",
                )
            )

        for code in sorted_vals.tail(top_n).index:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.LONG,
                    strength=1.0,
                    date=date,
                    reason="top_n",
                )
            )

        return signals


__all__ = ["Signal", "SignalGenerator", "SignalType"]
