"""
Markdown Report Generator

Wraps the DiagnosticMarkdownRenderer from the market_diagnostic package
and provides additional jq_workbench-specific formatting utilities.

Requirements: Req 19
"""

from typing import Optional

try:
    from market_diagnostic.reports.schema import DiagnosticReport
    from market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer
except ImportError:
    import sys
    from pathlib import Path
    dsa_path = Path(__file__).parent.parent.parent.parent / "daily_stock_analysis" / "src"
    sys.path.insert(0, str(dsa_path))
    from market_diagnostic.reports.schema import DiagnosticReport
    from market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer


class MarketDiagnosticMarkdownRenderer:
    """
    Enhanced Markdown renderer for jq_workbench platform integration.

    Wraps DiagnosticMarkdownRenderer and adds jq_workbench-specific
    header/footer formatting and output path utilities.

    Requirements: Req 19.1-19.12
    """

    def __init__(self):
        self._renderer = DiagnosticMarkdownRenderer()

    def render(
        self,
        report: DiagnosticReport,
        llm_narrative: str = "",
        include_header: bool = True,
        include_footer: bool = True,
    ) -> str:
        """
        Render a DiagnosticReport to a Markdown string.

        Parameters
        ----------
        report : DiagnosticReport
            The structured diagnostic report to render.
        llm_narrative : str, optional
            Optional LLM-generated narrative.
        include_header : bool
            Whether to include YAML frontmatter header (default True).
        include_footer : bool
            Whether to include standard footer (default True).

        Returns
        -------
        str
            Complete Markdown report.
        """
        md = self._renderer.render(report, llm_narrative=llm_narrative)

        if include_header:
            md = self._add_frontmatter(report) + md

        if include_footer:
            md = md + self._add_footer(report)

        return md

    def _add_frontmatter(self, report: DiagnosticReport) -> str:
        """Add YAML frontmatter with metadata."""
        fm = [
            "---",
            f"date: {report.date}",
            f"regime: {report.composite_regime}",
            f"confidence: {report.confidence:.2f}",
            f"trend_state: {report.trend_state}",
            f"breadth_state: {report.breadth_state}",
            f"sentiment_state: {report.sentiment_state}",
            f"risk_state: {report.risk_state}",
            "---",
            "",
        ]
        return "\n".join(fm)

    def _add_footer(self, report: DiagnosticReport) -> str:
        """Add standard footer with generation metadata."""
        footer = [
            "",
            "---",
            "*本报告由大盘全维度诊断系统自动生成*",
            f"*生成时间: {report.date}*",
            f"*Regime: {report.composite_regime} | 置信度: {report.confidence:.0%}*",
        ]
        return "\n".join(footer)

    def save_to_file(
        self,
        report: DiagnosticReport,
        filepath: str,
        llm_narrative: str = "",
    ) -> None:
        """
        Render report and save to a Markdown file.

        Parameters
        ----------
        report : DiagnosticReport
            The report to save.
        filepath : str
            Output file path.
        llm_narrative : str, optional
            Optional LLM narrative.
        """
        md = self.render(report, llm_narrative=llm_narrative)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)


def render_diagnostic_report(
    report: DiagnosticReport,
    llm_narrative: str = "",
    include_metadata: bool = True,
) -> str:
    """
    Convenience function to render a diagnostic report as Markdown.

    Parameters
    ----------
    report : DiagnosticReport
        The structured diagnostic report.
    llm_narrative : str, optional
        Optional LLM narrative to append.
    include_metadata : bool
        Whether to include YAML frontmatter (default True).

    Returns
    -------
    str
        Markdown-formatted report.
    """
    renderer = MarketDiagnosticMarkdownRenderer()
    return renderer.render(
        report,
        llm_narrative=llm_narrative,
        include_header=include_metadata,
        include_footer=True,
    )