"""Automatic strategy selector with dynamic weight routing."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import numpy as np

from src.core.models import Signal, SignalType


class StrategyEvaluator:
    """Evaluates indicator performance over a rolling window."""

    def __init__(self, window: int = 60) -> None:
        self.window = window

    def evaluate(
        self,
        signals_history: List[Signal],
        price_history: np.ndarray,
        forward_bars: int = 5,
    ) -> dict[str, float]:
        """Score each indicator source based on recent signal performance.

        Args:
            signals_history: Chronological list of Signal objects.
            price_history: 1-D array of closing prices aligned with signals.
            forward_bars: Number of bars ahead to measure return after a signal.

        Returns:
            Dict mapping source name to a composite score in [0, 1].
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(days=self.window)

        recent = [s for s in signals_history if s.timestamp >= cutoff]

        if not recent:
            return self._neutral_scores(signals_history)

        source_signals: dict[str, list[Signal]] = {}
        for sig in recent:
            source_signals.setdefault(sig.source, []).append(sig)

        all_names = self._collect_all_names(signals_history)
        scores: dict[str, float] = {}

        for name in all_names:
            sigs = source_signals.get(name, [])
            if not sigs:
                scores[name] = 0.5
                continue

            returns = self._compute_forward_returns(sigs, price_history, forward_bars)

            if len(returns) == 0:
                scores[name] = 0.5
                continue

            hit_rate = float(np.mean(returns > 0))
            avg_return = float(np.mean(returns))
            std_return = float(np.std(returns))
            sharpe_approx = avg_return / std_return if std_return > 1e-12 else 0.0

            composite = (
                0.4 * hit_rate
                + 0.3 * self._sigmoid(avg_return)
                + 0.3 * self._sigmoid(sharpe_approx)
            )
            scores[name] = round(composite, 4)

        return scores

    def _compute_forward_returns(
        self,
        signals: List[Signal],
        price_history: np.ndarray,
        forward_bars: int,
    ) -> np.ndarray:
        """Approximate forward returns for each signal based on price index."""
        returns: list[float] = []
        n = len(price_history)

        for sig in signals:
            idx = self._find_price_index(sig, price_history)
            if idx is None or idx + forward_bars >= n:
                continue
            entry = price_history[idx]
            exit_price = price_history[idx + forward_bars]
            if entry > 1e-12:
                ret = (exit_price - entry) / entry
                if sig.signal_type < SignalType.NEUTRAL:
                    ret = -ret
                returns.append(ret)

        return np.array(returns, dtype=np.float64)

    def _find_price_index(
        self, signal: Signal, price_history: np.ndarray
    ) -> int | None:
        """Locate the price bar closest to the signal timestamp."""
        n = len(price_history)
        if n == 0:
            return None

        ts_ord = signal.timestamp.toordinal()
        best_idx = 0
        best_diff = abs(self._ordinal_at_index(price_history, 0) - ts_ord)

        for i in range(n):
            diff = abs(self._ordinal_at_index(price_history, i) - ts_ord)
            if diff < best_diff:
                best_diff = diff
                best_idx = i

        return best_idx

    @staticmethod
    def _ordinal_at_index(price_history: np.ndarray, idx: int) -> int:
        """Stub: in production, pair price_history with a datetime index.

        Here we approximate by linear spacing so the evaluator works
        with a bare np.ndarray.  The caller should ideally pass a
        structured array or separate datetime index.
        """
        return idx

    def _collect_all_names(self, signals_history: List[Signal]) -> list[str]:
        """Return unique indicator source names seen across the full history."""
        seen: set[str] = set()
        for s in signals_history:
            seen.add(s.source)
        return sorted(seen)

    def _neutral_scores(self, signals_history: List[Signal]) -> dict[str, float]:
        """Assign neutral 0.5 score when no recent signals exist."""
        return {name: 0.5 for name in self._collect_all_names(signals_history)}

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Map any real value into (0, 1)."""
        return float(1.0 / (1.0 + np.exp(-np.clip(x, -10, 10))))


class AutoRouter:
    """Dynamically blends base weights with live performance scores."""

    def __init__(self, evaluator: StrategyEvaluator) -> None:
        self.evaluator = evaluator

    def get_dynamic_weights(
        self,
        current_scores: dict[str, float],
        base_weights: dict[str, float],
        performance_blend: float = 0.5,
        max_weight: float = 0.5,
    ) -> dict[str, float]:
        """Return blended, normalised weights for each indicator.

        Blends *base_weights* (1 - performance_blend) with performance-derived
        weights (performance_blend), applies softmax, then caps any single
        weight at *max_weight* and re-normalises.
        """
        all_names = sorted(set(base_weights) | set(current_scores))

        base = np.array([base_weights.get(n, 0.0) for n in all_names], dtype=np.float64)
        perf = np.array(
            [current_scores.get(n, 0.5) for n in all_names], dtype=np.float64
        )

        base_sum = base.sum()
        if base_sum > 0:
            base = base / base_sum

        perf_sum = perf.sum()
        if perf_sum > 0:
            perf = perf / perf_sum
        else:
            perf = np.ones_like(perf) / len(perf)

        blended = (1 - performance_blend) * base + performance_blend * perf

        weights = self._softmax(blended)

        weights = np.minimum(weights, max_weight)
        w_sum = weights.sum()
        if w_sum > 0:
            weights = weights / w_sum

        return {name: round(float(w), 6) for name, w in zip(all_names, weights)}

    def select_top_strategy(
        self,
        scores: dict[str, float],
        top_k: int = 2,
    ) -> list[str]:
        """Return the names of the *top_k* best-performing indicators."""
        if not scores:
            return []

        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [name for name, _ in sorted_items[:top_k]]

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        """Numerically stable softmax."""
        shifted = logits - np.max(logits)
        exp_vals = np.exp(shifted)
        total = exp_vals.sum()
        if total < 1e-12:
            return np.ones_like(logits) / len(logits)
        return exp_vals / total
