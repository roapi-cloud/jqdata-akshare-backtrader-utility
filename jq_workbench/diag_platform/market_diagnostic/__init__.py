"""
Market Diagnostic Platform Module

Provides market regime analysis, state classification, and diagnostic reports
for the jq_workbench platform.

Reference: Requirements 9-17, 21-22

Main components:
- MarketDiagnosticEngine: Core diagnostic engine
- DiagnosticReport: Structured report schema
- MarketStateClassifier: State classification across all dimensions
- State enums: TrendState, BreadthState, SentimentState, etc.

Usage:
    from diag_platform.market_diagnostic import (
        MarketDiagnosticEngine,
        DiagnosticReport,
        MarketStateClassifier,
        TrendState,
        CompositeRegime,
    )

    # Run diagnostic
    engine = MarketDiagnosticEngine()
    report, markdown = engine.run(date="2024-01-15")

    # Classify states directly
    classifier = MarketStateClassifier()
    result = classifier.classify(trend_features={...}, breadth_features={...}, ...)
"""

__version__ = "1.0.0"

# States layer
from .states import (
    TrendState,
    BreadthState,
    SentimentState,
    StyleState,
    SectorState,
    RiskState,
    CompositeRegime,
    MarketStateClassifier,
    MarketStateResult,
)

# Engine
from .engine import (
    MarketDiagnosticEngine,
    DiagnosticReport,
    generate_one_sentence_summary,
)

# Config
from .config import (
    INDEX_POOL,
    PRIMARY_INDEX,
    STYLE_PAIRS,
    SHENWAN_INDUSTRIES,
    BREADTH_THRESHOLDS,
    TREND_THRESHOLDS,
    SENTIMENT_THRESHOLDS,
    SECTOR_THRESHOLDS,
    RISK_THRESHOLDS,
    REGIME_SCORE_WEIGHTS,
    SECTOR_STRENGTH_WEIGHTS,
    RISK_FLAGS,
    RISK_FLAG_DESCRIPTIONS,
    REGIME_STRATEGY_MAPPING,
    CACHE_TTL,
    STOCK_FILTERS,
    CONFIDENCE_PARAMS,
    PERFORMANCE_TARGETS,
)

# Strategy mapping
from .strategy_mapping import (
    get_regime_recommendation,
    get_strategy_allocations,
    get_regime_display_name,
    get_regime_description_text,
    get_all_regime_recommendations,
    get_regime_summary_table,
    RegimeRecommendation,
    StrategyAllocation,
)

# Knowledge base manager
from .knowledge_base_manager import (
    KnowledgeBaseManager,
    ReportQuery,
    RegimeStats,
    TimelineEntry,
    get_knowledge_base,
    save_diagnostic_report,
)

__all__ = [
    # Version
    "__version__",
    # States
    "TrendState",
    "BreadthState",
    "SentimentState",
    "StyleState",
    "SectorState",
    "RiskState",
    "CompositeRegime",
    "MarketStateClassifier",
    "MarketStateResult",
    # Engine
    "MarketDiagnosticEngine",
    "DiagnosticReport",
    "generate_one_sentence_summary",
    # Config
    "INDEX_POOL",
    "PRIMARY_INDEX",
    "STYLE_PAIRS",
    "SHENWAN_INDUSTRIES",
    "BREADTH_THRESHOLDS",
    "TREND_THRESHOLDS",
    "SENTIMENT_THRESHOLDS",
    "SECTOR_THRESHOLDS",
    "RISK_THRESHOLDS",
    "REGIME_SCORE_WEIGHTS",
    "SECTOR_STRENGTH_WEIGHTS",
    "RISK_FLAGS",
    "RISK_FLAG_DESCRIPTIONS",
    "REGIME_STRATEGY_MAPPING",
    "CACHE_TTL",
    "STOCK_FILTERS",
    "CONFIDENCE_PARAMS",
    "PERFORMANCE_TARGETS",
    # Strategy mapping
    "get_regime_recommendation",
    "get_strategy_allocations",
    "get_regime_display_name",
    "get_regime_description_text",
    "get_all_regime_recommendations",
    "get_regime_summary_table",
    "RegimeRecommendation",
    "StrategyAllocation",
    # Knowledge base
    "KnowledgeBaseManager",
    "ReportQuery",
    "RegimeStats",
    "TimelineEntry",
    "get_knowledge_base",
    "save_diagnostic_report",
]