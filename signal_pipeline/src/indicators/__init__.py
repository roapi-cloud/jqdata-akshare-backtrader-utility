"""Indicator base classes and registry."""

from .base import BaseSignalGenerator
from .registry import IndicatorRegistry, auto_discover_indicators
from .strength_normalizer import StrengthNormalizer

__all__ = [
    "BaseSignalGenerator",
    "IndicatorRegistry",
    "auto_discover_indicators",
    "StrengthNormalizer",
]
