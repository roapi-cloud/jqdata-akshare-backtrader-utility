"""
Market Diagnostic Platform Reports Module

Integrates the market_diagnostic reports system for jq_workbench.
Provides report generation (Markdown + JSON) for market regime analysis.

Requirements: Req 18-20
"""

try:
    from market_diagnostic.reports.schema import DiagnosticReport
    from market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer
    from market_diagnostic.reports.strategy_mapper import (
        map_regime_to_strategies,
        get_regime_description,
        get_all_regimes,
    )
except ImportError:
    # Fallback for standalone usage
    import sys
    from pathlib import Path
    dsa_path = Path(__file__).parent.parent.parent.parent / "daily_stock_analysis" / "src"
    sys.path.insert(0, str(dsa_path))
    from market_diagnostic.reports.schema import DiagnosticReport
    from market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer
    from market_diagnostic.reports.strategy_mapper import (
        map_regime_to_strategies,
        get_regime_description,
        get_all_regimes,
    )

from diag_platform.market_diagnostic.reports.markdown_report import MarketDiagnosticMarkdownRenderer
from diag_platform.market_diagnostic.reports.json_exporter import DiagnosticJsonExporter

__all__ = [
    "DiagnosticReport",
    "DiagnosticMarkdownRenderer",
    "MarketDiagnosticMarkdownRenderer",
    "DiagnosticJsonExporter",
    "map_regime_to_strategies",
    "get_regime_description",
    "get_all_regimes",
]