"""Strategy combination with signal voting and weight allocation."""

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .base import BaseStrategy, Portfolio
from .position import PositionSizer


class StrategyCombiner:
    """Combines multiple strategies into a single portfolio.

    Supports signal voting mechanisms and weight allocation across
    constituent strategies. Each strategy can have a different weight
    and position sizing method.

    Attributes:
        strategies: List of (strategy, weight) tuples.
        strategy_sizers: Dictionary mapping strategy names to position sizers.
        combiner_method: Method for combining signals ('weighted', 'voting', 'rank').
        voting_threshold: Minimum fraction of strategies needed for a buy signal.
    """

    def __init__(
        self,
        strategies: Optional[List[Tuple[BaseStrategy, float]]] = None,
        combiner_method: str = "weighted",
        voting_threshold: float = 0.5,
        default_sizer: Optional[PositionSizer] = None,
    ):
        """Initialize the strategy combiner.

        Args:
            strategies: List of (strategy, weight) tuples. Weights do not
                        need to sum to 1; they will be normalized.
            combiner_method: How to combine strategy outputs. Options:
                - 'weighted': Weighted average of target positions.
                - 'voting': Majority vote on inclusion, then average weights.
                - 'rank': Rank-based combination.
            voting_threshold: Fraction of strategies that must agree for
                              a stock to be included (used with 'voting' method).
            default_sizer: Default position sizer applied to combined output.
        """
        self.strategies: List[Tuple[BaseStrategy, float]] = strategies or []
        self.combiner_method = combiner_method
        self.voting_threshold = voting_threshold
        self.strategy_sizers: Dict[str, PositionSizer] = {}
        self.default_sizer = default_sizer
        self._strategy_results: Dict[str, Dict[str, float]] = {}

    def add_strategy(
        self,
        strategy: BaseStrategy,
        weight: float = 1.0,
        sizer: Optional[PositionSizer] = None,
    ) -> None:
        """Add a strategy to the combiner.

        Args:
            strategy: Strategy instance to add.
            weight: Relative weight for this strategy.
            sizer: Optional position sizer specific to this strategy.
        """
        self.strategies.append((strategy, weight))
        if sizer is not None:
            self.strategy_sizers[strategy.name] = sizer

    def remove_strategy(self, strategy_name: str) -> bool:
        """Remove a strategy by name.

        Args:
            strategy_name: Name of the strategy to remove.

        Returns:
            True if strategy was found and removed.
        """
        original_len = len(self.strategies)
        self.strategies = [
            (s, w) for s, w in self.strategies if s.name != strategy_name
        ]
        self.strategy_sizers.pop(strategy_name, None)
        return len(self.strategies) < original_len

    def get_target_positions(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """Get combined target positions from all strategies.

        Runs each strategy and combines their outputs according to
        the configured combiner method.

        Args:
            trade_date: Current trading date.
            data: Market data DataFrame.
            portfolio: Current portfolio state.

        Returns:
            Combined target position weights.
        """
        if not self.strategies:
            return {}

        # Collect individual strategy outputs
        strategy_outputs: List[Tuple[str, float, Dict[str, float]]] = []
        for strategy, weight in self.strategies:
            try:
                targets = strategy.on_bar(trade_date, data, portfolio)
                strategy_outputs.append((strategy.name, weight, targets))
                self._strategy_results[strategy.name] = targets
            except Exception:
                # Skip strategies that fail
                continue

        if not strategy_outputs:
            return {}

        # Combine based on method
        if self.combiner_method == "voting":
            combined = self._combine_voting(strategy_outputs)
        elif self.combiner_method == "rank":
            combined = self._combine_rank(strategy_outputs)
        else:
            combined = self._combine_weighted(strategy_outputs)

        # Apply default sizer if configured
        if self.default_sizer is not None:
            combined = self.default_sizer.size(combined)

        return combined

    def _combine_weighted(
        self,
        outputs: List[Tuple[str, float, Dict[str, float]]],
    ) -> Dict[str, float]:
        """Combine strategies using weighted average.

        Args:
            outputs: List of (name, weight, targets) tuples.

        Returns:
            Weighted average of target positions.
        """
        total_weight = sum(w for _, w, _ in outputs)
        if total_weight == 0:
            return {}

        combined: Dict[str, float] = defaultdict(float)
        for name, weight, targets in outputs:
            normalized_w = weight / total_weight
            for code, target_w in targets.items():
                combined[code] += target_w * normalized_w

        return dict(combined)

    def _combine_voting(
        self,
        outputs: List[Tuple[str, float, Dict[str, float]]],
    ) -> Dict[str, float]:
        """Combine strategies using voting mechanism.

        A stock is included only if at least `voting_threshold` fraction
        of strategies have a positive target for it.

        Args:
            outputs: List of (name, weight, targets) tuples.

        Returns:
            Combined weights for stocks that pass the voting threshold.
        """
        n_strategies = len(outputs)
        vote_count: Dict[str, int] = defaultdict(int)
        weight_sum: Dict[str, float] = defaultdict(float)
        total_weight: Dict[str, float] = defaultdict(float)

        for name, weight, targets in outputs:
            for code, target_w in targets.items():
                if target_w > 0:
                    vote_count[code] += 1
                    weight_sum[code] += target_w * weight
                    total_weight[code] += weight

        # Apply voting threshold
        required_votes = int(np.ceil(n_strategies * self.voting_threshold))
        combined: Dict[str, float] = {}

        for code, votes in vote_count.items():
            if votes >= required_votes:
                # Average weight among strategies that voted for it
                avg_weight = (
                    weight_sum[code] / total_weight[code]
                    if total_weight[code] > 0
                    else 0
                )
                combined[code] = avg_weight

        return combined

    def _combine_rank(
        self,
        outputs: List[Tuple[str, float, Dict[str, float]]],
    ) -> Dict[str, float]:
        """Combine strategies using rank-based method.

        Converts each strategy's weights to ranks and averages the ranks.

        Args:
            outputs: List of (name, weight, targets) tuples.

        Returns:
            Rank-based combined weights.
        """
        all_codes: set = set()
        ranks_per_strategy: List[Dict[str, float]] = []

        for name, weight, targets in outputs:
            if not targets:
                continue

            all_codes.update(targets.keys())

            # Convert weights to ranks (higher weight = higher rank)
            sorted_codes = sorted(targets.keys(), key=lambda c: targets[c])
            n = len(sorted_codes)
            ranks = {}
            for rank, code in enumerate(sorted_codes, 1):
                ranks[code] = rank / n  # Normalize to [0, 1]
            ranks_per_strategy.append(ranks)

        if not ranks_per_strategy:
            return {}

        # Average ranks across strategies
        rank_sum: Dict[str, float] = defaultdict(float)
        count: Dict[str, int] = defaultdict(int)

        for ranks in ranks_per_strategy:
            for code, r in ranks.items():
                rank_sum[code] += r
                count[code] += 1

        combined = {
            code: rank_sum[code] / count[code] for code in all_codes if count[code] > 0
        }

        # Normalize to sum to 1
        total = sum(combined.values())
        if total > 0:
            combined = {code: w / total for code, w in combined.items()}

        return combined

    def get_strategy_performance(
        self,
        portfolio_history: pd.DataFrame,
    ) -> Dict[str, Dict[str, float]]:
        """Get performance attribution for each strategy.

        Computes contribution metrics for each constituent strategy
        based on the portfolio history.

        Args:
            portfolio_history: DataFrame with portfolio snapshots.

        Returns:
            Dictionary mapping strategy names to performance metrics.
        """
        if portfolio_history.empty or not self._strategy_results:
            return {}

        performance = {}
        for name, targets in self._strategy_results.items():
            n_stocks = len(targets)
            avg_weight = np.mean(list(targets.values())) if targets else 0.0
            max_weight = max(targets.values()) if targets else 0.0

            performance[name] = {
                "n_signals": n_stocks,
                "avg_weight": avg_weight,
                "max_weight": max_weight,
                "concentration": max_weight / (avg_weight + 1e-10)
                if avg_weight > 0
                else 0.0,
            }

        return performance

    def get_weights(self) -> Dict[str, float]:
        """Get normalized strategy weights.

        Returns:
            Dictionary mapping strategy names to normalized weights.
        """
        total = sum(w for _, w in self.strategies)
        if total == 0:
            return {}
        return {s.name: w / total for s, w in self.strategies}

    def __repr__(self) -> str:
        names = [s.name for s, _ in self.strategies]
        return f"StrategyCombiner(method={self.combiner_method!r}, strategies={names})"
