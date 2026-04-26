"""Factor layer for quantitative trading framework."""

from .base import Factor, FactorRegistry, FactorResult
from .technical import MAFactor, MACDFactor, RSIFactor, BollingerFactor, ATRFactor
from .breadth import (
    NewHighRatioFactor,
    AboveMARatioFactor,
    AdvanceDeclineFactor,
    LimitUpDownFactor,
)
from .sentiment import (
    TurnoverSentimentFactor,
    VolumeShrinkageFactor,
    CrowdRateFactor,
    GSISIFactor,
)

__all__ = [
    "Factor",
    "FactorRegistry",
    "FactorResult",
    "MAFactor",
    "MACDFactor",
    "RSIFactor",
    "BollingerFactor",
    "ATRFactor",
    "NewHighRatioFactor",
    "AboveMARatioFactor",
    "AdvanceDeclineFactor",
    "LimitUpDownFactor",
    "TurnoverSentimentFactor",
    "VolumeShrinkageFactor",
    "CrowdRateFactor",
    "GSISIFactor",
]
