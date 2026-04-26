"""Preset strategy templates for single-strategy research."""

from .weighting_strategies import (
    BasePredictionStrategy,
    WeightedTopNStrategy,
    EqualWeightStrategy,
    DirectExecutionStrategy,
)

__all__ = [
    "BasePredictionStrategy",
    "WeightedTopNStrategy",
    "EqualWeightStrategy",
    "DirectExecutionStrategy",
]
