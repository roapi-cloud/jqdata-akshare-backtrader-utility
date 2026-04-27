"""
Market Diagnostic Knowledge Base

Knowledge base for market regime analysis, strategy mappings, and diagnostic reports.

Directory structure:
    knowledge/
    ├── diagnostic_reports/   # Daily diagnostic reports (auto-generated)
    ├── regime_patterns/      # Regime pattern definitions and examples
    └── strategy_mapping/     # Strategy mapping rules and descriptions

Usage:
    from diag_platform.market_diagnostic.knowledge_base_manager import KnowledgeBaseManager

    kb = KnowledgeBaseManager()
    kb.save_report(report_dict, date="2026-04-27")
    results = kb.query_reports(ReportQuery(regime="trend_risk_on_growth"))
"""

from diag_platform.market_diagnostic.knowledge_base_manager import (
    KnowledgeBaseManager,
    ReportQuery,
    RegimeStats,
    TimelineEntry,
    get_knowledge_base,
    save_diagnostic_report,
)

__all__ = [
    "KnowledgeBaseManager",
    "ReportQuery",
    "RegimeStats",
    "TimelineEntry",
    "get_knowledge_base",
    "save_diagnostic_report",
]