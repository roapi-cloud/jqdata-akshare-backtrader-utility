"""Signal Fusion Engine — combines multiple indicator signals into a single decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from src.core.models import FusedSignal, Signal, SignalType


@dataclass
class FusionConfig:
    """Configuration for the signal fusion engine."""

    base_weights: dict[str, float] = field(
        default_factory=lambda: {
            "Chan": 0.20,
            "RSRS": 0.15,
            "Trend": 0.20,
            "RoundingBottom": 0.10,
            "MESA": 0.15,
        }
    )
    regime_adjustments: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "trending": {
                "Chan": 1.3,
                "RSRS": 1.2,
                "Trend": 1.3,
                "RoundingBottom": 0.7,
            },
            "oscillating": {
                "MESA": 1.3,
                "RoundingBottom": 1.3,
                "Trend": 0.7,
            },
        }
    )
    conflict_threshold: float = 0.2
    buy_threshold: float = 0.5
    sell_threshold: float = -0.5
    conflict_tolerance: float = 0.2


class SignalFusionEngine:
    """Fuses multiple signals into a single actionable decision."""

    def __init__(self, config: FusionConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fuse(self, signals: list[Signal], market_regime: str) -> FusedSignal:
        """Fuse a list of signals into one FusedSignal.

        Steps: align → adjust weights by regime → score → resolve conflicts → consensus bonus.
        """
        if not signals:
            return self._neutral_fused_signal(signals)

        aligned = self._align(signals)
        weights = self._compute_weights(market_regime)
        buy_score, sell_score, buy_count, sell_count = self._score(aligned, weights)
        net = buy_score - sell_score

        is_conflict = False
        position_suggestion = 1.0

        is_conflict, position_suggestion = self._resolve_conflict(
            buy_score, sell_score, position_suggestion
        )

        confidence = self._confidence(net, buy_count, sell_count)
        confidence = self._consensus_bonus(confidence, buy_count, sell_count)

        direction = self._direction(net)

        return FusedSignal(
            symbol=aligned[0].symbol,
            timestamp=aligned[0].timestamp,
            direction=direction,
            net_score=float(np.clip(net, -1.0, 1.0)),
            confidence=min(confidence, 1.0),
            position_suggestion=position_suggestion,
            component_signals={s.source: s for s in aligned},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _align(signals: list[Signal]) -> list[Signal]:
        """Group signals by timestamp and keep the latest group."""
        latest_ts: datetime | None = None
        for s in signals:
            if latest_ts is None or s.timestamp > latest_ts:
                latest_ts = s.timestamp
        if latest_ts is None:
            return []
        return [s for s in signals if s.timestamp == latest_ts]

    def _compute_weights(self, regime: str) -> dict[str, float]:
        """Return effective weights after applying regime adjustments."""
        weights = dict(self.config.base_weights)
        adjustments = self.config.regime_adjustments.get(regime, {})
        for indicator, multiplier in adjustments.items():
            if indicator in weights:
                weights[indicator] *= multiplier
        return weights

    @staticmethod
    def _score(
        signals: list[Signal], weights: dict[str, float]
    ) -> tuple[float, float, int, int]:
        """Compute buy_score, sell_score and count agreeing indicators."""
        buy_score = 0.0
        sell_score = 0.0
        buy_count = 0
        sell_count = 0

        for sig in signals:
            w = weights.get(getattr(sig, "indicator_name", sig.source), 1.0)
            if sig.signal_type == SignalType.BUY:
                buy_score += sig.strength * w
                buy_count += 1
            elif sig.signal_type == SignalType.SELL:
                sell_score += sig.strength * w
                sell_count += 1

        return buy_score, sell_score, buy_count, sell_count

    def _resolve_conflict(
        self, buy_score: float, sell_score: float, position_suggestion: float
    ) -> tuple[bool, float]:
        """Detect and handle conflicting signals."""
        if (
            buy_score > 0.1
            and sell_score > 0.1
            and abs(buy_score - sell_score) < self.config.conflict_threshold
        ):
            position_suggestion *= 0.5
            return True, position_suggestion
        return False, position_suggestion

    def _confidence(self, net: float, buy_count: int, sell_count: int) -> float:
        """Derive base confidence from net score."""
        total = buy_count + sell_count
        if total == 0:
            return 0.0
        return abs(net) / total if total > 0 else 0.0

    @staticmethod
    def _consensus_bonus(confidence: float, buy_count: int, sell_count: int) -> float:
        """Boost confidence when >= 3 indicators agree on direction."""
        agreeing = max(buy_count, sell_count)
        if agreeing >= 3:
            confidence *= 1.2
        return confidence

    @staticmethod
    def _direction(net: float) -> SignalType:
        """Map net score to a SignalType."""
        if net > 0:
            return SignalType.BUY
        if net < 0:
            return SignalType.SELL
        return SignalType.HOLD

    @staticmethod
    def _neutral_fused_signal(signals: list[Signal]) -> FusedSignal:
        """Return a NEUTRAL FusedSignal when no signals are provided."""
        now = datetime.now()
        return FusedSignal(
            symbol="",
            timestamp=now,
            signal_type=SignalType.HOLD,
            strength=0.0,
            component_signals=signals,
            metadata={
                "buy_score": 0.0,
                "sell_score": 0.0,
                "net": 0.0,
                "is_conflict": False,
                "position_suggestion": 0.0,
                "market_regime": "unknown",
            },
        )
