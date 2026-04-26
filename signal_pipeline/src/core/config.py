"""Pipeline configuration dataclasses and loaders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineConfig:
    """Top-level configuration for the signal pipeline."""

    indicators: list[str] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    fusion_method: str = "weighted_vote"
    market_regime: str = "unknown"
    min_history: int = 100
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.indicators and not self.weights:
            self.weights = [1.0] * len(self.indicators)
        if len(self.indicators) != len(self.weights):
            raise ValueError(
                "indicators and weights must have the same length, "
                f"got {len(self.indicators)} and {len(self.weights)}"
            )


def load_config(path: str | None = None) -> PipelineConfig:
    """Load a PipelineConfig from a JSON/YAML file or return defaults."""
    if path is None:
        return PipelineConfig()

    # TODO: implement file-based config loading
    raise NotImplementedError(
        f"Config file loading from '{path}' is not yet implemented. "
        "Pass a PipelineConfig directly for now."
    )
