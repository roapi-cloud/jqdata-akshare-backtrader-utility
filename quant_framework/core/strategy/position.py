"""Position sizing strategies for portfolio allocation."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class PositionSizer(ABC):
    """Abstract base class for position sizing strategies.

    Position sizers convert strategy signals (scores/weights) into
    actual portfolio weights that respect constraints.
    """

    def __init__(
        self,
        max_weight: float = 0.10,
        min_weight: float = 0.0,
        max_positions: int = 50,
        cash_reserve: float = 0.0,
    ):
        """Initialize the position sizer.

        Args:
            max_weight: Maximum weight for any single position.
            min_weight: Minimum weight for any position (below this is zeroed).
            max_positions: Maximum number of positions to hold.
            cash_reserve: Fraction of portfolio to keep as cash reserve.
        """
        self.max_weight = max_weight
        self.min_weight = min_weight
        self.max_positions = max_positions
        self.cash_reserve = cash_reserve

    def size(
        self,
        signals: Dict[str, float],
        volatilities: Optional[Dict[str, float]] = None,
        returns_history: Optional[pd.DataFrame] = None,
    ) -> Dict[str, float]:
        """Compute final position weights from signals.

        Applies the sizing strategy and then enforces constraints.

        Args:
            signals: Dictionary mapping stock codes to signal values.
            volatilities: Optional dictionary of stock volatilities.
            returns_history: Optional DataFrame of historical returns
                (columns are stock codes, index is dates).

        Returns:
            Dictionary mapping stock codes to target weights.
        """
        raw_weights = self._compute_raw_weights(signals, volatilities, returns_history)
        return self._apply_constraints(raw_weights)

    @abstractmethod
    def _compute_raw_weights(
        self,
        signals: Dict[str, float],
        volatilities: Optional[Dict[str, float]],
        returns_history: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        """Compute raw (unconstrained) weights from signals.

        Args:
            signals: Dictionary mapping stock codes to signal values.
            volatilities: Optional dictionary of stock volatilities.
            returns_history: Optional DataFrame of historical returns.

        Returns:
            Dictionary of raw weights (may not sum to 1).
        """
        ...

    def _apply_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Apply position constraints to weights.

        Args:
            weights: Raw weights dictionary.

        Returns:
            Constrained weights that sum to (1 - cash_reserve).
        """
        if not weights:
            return {}

        # Remove weights below minimum
        filtered = {code: w for code, w in weights.items() if w >= self.min_weight}

        if not filtered:
            return {}

        # Apply max weight constraint
        constrained = {code: min(w, self.max_weight) for code, w in filtered.items()}

        # Apply max positions constraint - keep highest weights
        if len(constrained) > self.max_positions:
            sorted_items = sorted(constrained.items(), key=lambda x: x[1], reverse=True)
            constrained = dict(sorted_items[: self.max_positions])

        # Normalize to target allocation (1 - cash_reserve)
        total = sum(constrained.values())
        if total > 0:
            target_sum = 1.0 - self.cash_reserve
            constrained = {
                code: w * target_sum / total for code, w in constrained.items()
            }

        return constrained


class EqualWeightSizer(PositionSizer):
    """Equal weight position sizing.

    Allocates equal weights to all selected stocks regardless of signal strength.
    Useful as a baseline or when signals are binary (in/out).
    """

    def _compute_raw_weights(
        self,
        signals: Dict[str, float],
        volatilities: Optional[Dict[str, float]],
        returns_history: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        """Compute equal weights for all stocks with positive signals.

        Args:
            signals: Dictionary mapping stock codes to signal values.
            volatilities: Unused.
            returns_history: Unused.

        Returns:
            Equal weights for all stocks with positive signals.
        """
        selected = [code for code, s in signals.items() if s > 0]
        if not selected:
            return {}

        weight = 1.0 / len(selected)
        return {code: weight for code in selected}


class RiskParitySizer(PositionSizer):
    """Risk parity position sizing.

    Allocates weights inversely proportional to volatility so that each
    position contributes equally to portfolio risk.
    """

    def _compute_raw_weights(
        self,
        signals: Dict[str, float],
        volatilities: Optional[Dict[str, float]],
        returns_history: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        """Compute risk parity weights.

        Uses provided volatilities or computes from returns history.

        Args:
            signals: Dictionary mapping stock codes to signal values.
            volatilities: Dictionary of stock volatilities (annualized).
            returns_history: DataFrame of historical returns as fallback.

        Returns:
            Risk-parity weights for selected stocks.
        """
        selected = {code: s for code, s in signals.items() if s > 0}
        if not selected:
            return {}

        # Get volatilities
        vols: Dict[str, float] = {}
        if volatilities is not None:
            vols = {code: volatilities.get(code, 0.0) for code in selected}
        elif returns_history is not None:
            for code in selected:
                if code in returns_history.columns:
                    vols[code] = float(returns_history[code].std() * np.sqrt(252))
                else:
                    vols[code] = 0.0

        # Filter out zero volatilities
        valid = {code: v for code, v in vols.items() if v > 0}
        if not valid:
            # Fallback to equal weight
            weight = 1.0 / len(selected)
            return {code: weight for code in selected}

        # Risk parity: weight inversely proportional to volatility
        inv_vols = {code: 1.0 / v for code, v in valid.items()}
        total_inv_vol = sum(inv_vols.values())

        weights = {code: iv / total_inv_vol for code, iv in inv_vols.items()}

        # Include stocks without volatility data with zero weight
        for code in selected:
            if code not in weights:
                weights[code] = 0.0

        return weights


class KellySizer(PositionSizer):
    """Kelly criterion position sizing.

    Sizes positions based on the Kelly formula: f* = (bp - q) / b
    where b is the win/loss ratio, p is win probability, q = 1 - p.

    For continuous returns, uses: f* = mu / sigma^2
    where mu is expected return and sigma is volatility.
    """

    def __init__(
        self,
        max_weight: float = 0.10,
        min_weight: float = 0.0,
        max_positions: int = 50,
        cash_reserve: float = 0.0,
        kelly_fraction: float = 0.25,
        risk_free_rate: float = 0.02,
    ):
        """Initialize Kelly sizer.

        Args:
            max_weight: Maximum weight for any single position.
            min_weight: Minimum weight threshold.
            max_positions: Maximum number of positions.
            cash_reserve: Cash reserve fraction.
            kelly_fraction: Fraction of full Kelly to use (0.25 = quarter Kelly).
            risk_free_rate: Annual risk-free rate for excess return calculation.
        """
        super().__init__(max_weight, min_weight, max_positions, cash_reserve)
        self.kelly_fraction = kelly_fraction
        self.risk_free_rate = risk_free_rate

    def _compute_raw_weights(
        self,
        signals: Dict[str, float],
        volatilities: Optional[Dict[str, float]],
        returns_history: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        """Compute Kelly criterion weights.

        Requires returns_history to estimate expected returns and volatility.
        Falls back to equal weight if insufficient data.

        Args:
            signals: Dictionary mapping stock codes to signal values.
            volatilities: Optional pre-computed volatilities.
            returns_history: DataFrame of historical returns.

        Returns:
            Kelly criterion weights for selected stocks.
        """
        selected = {code: s for code, s in signals.items() if s > 0}
        if not selected or returns_history is None:
            # Fallback to equal weight
            if selected:
                weight = 1.0 / len(selected)
                return {code: weight for code in selected}
            return {}

        daily_rf = self.risk_free_rate / 252.0
        weights = {}

        for code in selected:
            if code not in returns_history.columns:
                continue

            ret_series = returns_history[code].dropna()
            if len(ret_series) < 20:
                continue

            mu = float(ret_series.mean()) - daily_rf
            sigma = float(ret_series.std())

            if sigma <= 0:
                continue

            # Kelly formula: f* = mu / sigma^2
            kelly = mu / (sigma**2)

            # Apply fraction and signal strength scaling
            f = self.kelly_fraction * kelly * min(selected[code], 1.0)

            if f > 0:
                weights[code] = f

        if not weights:
            # Fallback to equal weight
            weight = 1.0 / len(selected)
            return {code: weight for code in selected}

        return weights


class VolatilityTargetSizer(PositionSizer):
    """Volatility targeting position sizing.

    Scales position sizes so that the portfolio achieves a target
    annualized volatility. Individual positions are scaled inversely
    to their volatility.
    """

    def __init__(
        self,
        max_weight: float = 0.10,
        min_weight: float = 0.0,
        max_positions: int = 50,
        cash_reserve: float = 0.0,
        target_volatility: float = 0.15,
        lookback: int = 60,
    ):
        """Initialize volatility target sizer.

        Args:
            max_weight: Maximum weight for any single position.
            min_weight: Minimum weight threshold.
            max_positions: Maximum number of positions.
            cash_reserve: Cash reserve fraction.
            target_volatility: Target annualized portfolio volatility.
            lookback: Number of periods for volatility calculation.
        """
        super().__init__(max_weight, min_weight, max_positions, cash_reserve)
        self.target_volatility = target_volatility
        self.lookback = lookback

    def _compute_raw_weights(
        self,
        signals: Dict[str, float],
        volatilities: Optional[Dict[str, float]],
        returns_history: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        """Compute volatility-targeted weights.

        Args:
            signals: Dictionary mapping stock codes to signal values.
            volatilities: Optional pre-computed volatilities.
            returns_history: DataFrame of historical returns.

        Returns:
            Volatility-targeted weights for selected stocks.
        """
        selected = {code: s for code, s in signals.items() if s > 0}
        if not selected:
            return {}

        # Get volatilities
        vols: Dict[str, float] = {}
        if volatilities is not None:
            vols = {code: volatilities.get(code, 0.0) for code in selected}
        elif returns_history is not None:
            for code in selected:
                if code in returns_history.columns:
                    recent = returns_history[code].dropna().tail(self.lookback)
                    if len(recent) >= 10:
                        vols[code] = float(recent.std() * np.sqrt(252))
                    else:
                        vols[code] = 0.0
                else:
                    vols[code] = 0.0

        # Filter valid volatilities
        valid = {code: v for code, v in vols.items() if v > 0}

        if not valid:
            # Fallback to equal weight
            weight = 1.0 / len(selected)
            return {code: weight for code in selected}

        # Scale by signal strength and inverse volatility
        raw = {}
        for code, vol in valid.items():
            signal_strength = selected[code]
            raw[code] = signal_strength / vol

        # Normalize
        total = sum(raw.values())
        if total > 0:
            weights = {code: r / total for code, r in raw.items()}
        else:
            weight = 1.0 / len(valid)
            weights = {code: weight for code in valid}

        # Add stocks without volatility data with zero weight
        for code in selected:
            if code not in weights:
                weights[code] = 0.0

        return weights
