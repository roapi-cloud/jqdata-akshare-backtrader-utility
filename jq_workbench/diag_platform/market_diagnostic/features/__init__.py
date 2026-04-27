"""
Feature Layer

Computes quantitative indicators from raw market data.
"""

from .trend import TrendFeatures, compute_trend_features, compute_all_trend_features
from .breadth import BreadthFeatures, compute_breadth_features
from .sentiment import SentimentFeatures, compute_sentiment_features
from .style import StyleFeatures, compute_style_features
from .sector import SectorFeatureResult, compute_sector_features, compute_all_sector_features

__all__ = [
    "TrendFeatures",
    "compute_trend_features",
    "compute_all_trend_features",
    "BreadthFeatures",
    "compute_breadth_features",
    "SentimentFeatures",
    "compute_sentiment_features",
    "StyleFeatures",
    "compute_style_features",
    "SectorFeatureResult",
    "compute_sector_features",
    "compute_all_sector_features",
]
