"""
Market Diagnostic System

Full-dimensional A-share market diagnostic engine.
Outputs structured JSON and Markdown reports.

Reference: Requirements 18-20, 25
"""

from .engine import MarketDiagnosticEngine
from .states.classifier import (
    MarketStateClassifier,
    MarketStateResult,
    TrendFeatures,
    BreadthFeatures,
    SentimentFeatures,
    StyleFeatures,
    SectorFeatureResult,
    CapitalFeatures,
    RiskFeatures,
)
from .states.enums import (
    TrendState,
    BreadthState,
    SentimentState,
    StyleState,
    SectorState,
    RiskState,
    CompositeRegime,
    BREADTH_THRESHOLDS,
    RISK_FLAG_DEFINITIONS,
    REGIME_STRATEGY_MAPPING,
)
from .reports.schema import DiagnosticReport
from .reports.markdown_renderer import DiagnosticMarkdownRenderer, render_diagnostic_report
from .reports.json_exporter import DiagnosticJsonExporter, export_diagnostic_report
from .strategy_mapping import (
    get_regime_recommendation,
    get_strategy_allocations,
    get_regime_display_name,
    get_all_regime_recommendations,
    get_regime_summary_table,
    get_simple_strategy_groups,
)
from .knowledge_base_manager import (
    KnowledgeBaseManager,
    ReportQuery,
    RegimeStats,
    TimelineEntry,
    get_knowledge_base,
    save_diagnostic_report,
)

__all__ = [
    # Core engine
    "MarketDiagnosticEngine",
    # State classifier
    "MarketStateClassifier",
    "MarketStateResult",
    "TrendFeatures",
    "BreadthFeatures",
    "SentimentFeatures",
    "StyleFeatures",
    "SectorFeatureResult",
    "CapitalFeatures",
    "RiskFeatures",
    # Enums
    "TrendState",
    "BreadthState",
    "SentimentState",
    "StyleState",
    "SectorState",
    "RiskState",
    "CompositeRegime",
    "BREADTH_THRESHOLDS",
    "RISK_FLAG_DEFINITIONS",
    "REGIME_STRATEGY_MAPPING",
    # Reports
    "DiagnosticReport",
    "DiagnosticMarkdownRenderer",
    "DiagnosticJsonExporter",
    "render_diagnostic_report",
    "export_diagnostic_report",
    # Strategy mapping
    "get_regime_recommendation",
    "get_strategy_allocations",
    "get_regime_display_name",
    "get_all_regime_recommendations",
    "get_regime_summary_table",
    "get_simple_strategy_groups",
    # Knowledge base
    "KnowledgeBaseManager",
    "ReportQuery",
    "RegimeStats",
    "TimelineEntry",
    "get_knowledge_base",
    "save_diagnostic_report",
]