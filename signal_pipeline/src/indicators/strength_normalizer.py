"""Rolling percentile-based strength normalizer.

Maps raw indicator values to a [0, 1] scale using a rolling history window,
which adapts to changing market regimes (bull / bear).
"""

from __future__ import annotations

from collections import deque
from typing import List


class StrengthNormalizer:
    """Normalizes raw metric values to [0, 1] via rolling percentile.

    Maintains an internal history buffer of the last ``history_window`` values.
    Each call to :meth:`normalize` updates the buffer and returns the percentile
    rank of the new value relative to the buffer.

    This solves the bull/bear scale problem: a raw value that is extreme in a
    bear market may be ordinary in a bull market. The rolling window ensures
    the normalization is always relative to recent history.
    """

    def __init__(self, history_window: int = 250) -> None:
        """
        Args:
            history_window: Number of recent values to keep in the rolling
                buffer. Defaults to 250 (approximately one trading year).
        """
        if history_window < 2:
            raise ValueError("history_window must be >= 2")
        self._history_window = history_window
        self._buffer: deque[float] = deque(maxlen=history_window)

    @property
    def history_window(self) -> int:
        return self._history_window

    @property
    def current_size(self) -> int:
        """Number of values currently in the buffer."""
        return len(self._buffer)

    def normalize(self, raw_value: float, history_window: int | None = None) -> float:
        """Normalize a raw value to [0, 1] using the rolling percentile.

        The new value is added to the history buffer *before* computing the
        percentile, so the result reflects the value's position within the
        updated window.

        Args:
            raw_value: The raw metric value to normalize.
            history_window: Optional override for the window size. If provided,
                the buffer is resized accordingly.

        Returns:
            A float in [0, 1] representing the percentile rank of ``raw_value``
            within the rolling history. Returns 0.5 when the buffer has only
            one element (no meaningful ranking possible).
        """
        if history_window is not None and history_window != self._history_window:
            self._history_window = history_window
            self._buffer = deque(
                list(self._buffer)[-history_window:], maxlen=history_window
            )

        self._buffer.append(raw_value)

        if len(self._buffer) <= 1:
            return 0.5

        return self._percentile_rank(raw_value)

    def _percentile_rank(self, value: float) -> float:
        """Compute the percentile rank of *value* within the current buffer.

        Uses the fraction of values less than or equal to *value*,
        clipped to [0, 1].
        """
        n = len(self._buffer)
        if n == 0:
            return 0.5

        count_le = sum(1 for v in self._buffer if v <= value)
        return count_le / n

    def reset(self) -> None:
        """Clear the history buffer."""
        self._buffer.clear()

    def get_history(self) -> List[float]:
        """Return a copy of the current history buffer (oldest first)."""
        return list(self._buffer)

    def __repr__(self) -> str:
        return (
            f"StrengthNormalizer(window={self._history_window}, "
            f"size={len(self._buffer)})"
        )
