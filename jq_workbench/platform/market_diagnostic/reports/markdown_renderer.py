"""
Markdown Report Renderer

Renders a DiagnosticReport as a human-readable Markdown document.
Supports optional LLM-generated narrative paragraphs.

Reference: Requirements 19.1-19.12
"""

from typing import Optional, List, Dict


class DiagnosticMarkdownRenderer:
    """
    Render DiagnosticReport to Markdown format.

    Produces structured Markdown reports with:
    - YAML frontmatter with metadata
    - One-sentence summary
    - State dashboard table
    - Detailed metrics sections per dimension
    - Strategy mapping recommendations
    - Evidence and confidence section
    - Optional LLM narrative

    Reference: Requirements 19.1-19.12
    """

    def __init__(self, include_frontmatter: bool = True):
        """
        Initialize the renderer.

        Parameters
        ----------
        include_frontmatter : bool
            Whether to include YAML frontmatter (default True).
        """
        self.include_frontmatter = include_frontmatter

    def render(
        self,
        report,
        llm_narrative: str = "",
    ) -> str:
        """
        Render a DiagnosticReport to Markdown string.

        Parameters
        ----------
        report : DiagnosticReport
            The structured report to render.
        llm_narrative : str, optional
            Optional LLM-generated narrative to append.

        Returns
        -------
        str
            Complete Markdown report.

        Reference: Requirement 19
        """
        parts = []

        # YAML frontmatter (Req 19.1)
        if self.include_frontmatter:
            parts.append(self._render_frontmatter(report))

        # Title and one-sentence summary (Req 19.1, 19.2)
        parts.append(self._render_summary(report))

        # State dashboard table (Req 19.2)
        parts.append(self._render_state_dashboard(report))

        # Index structure section (Req 19.3)
        if report.indices:
            parts.append(self._render_index_section(report))

        # Market breadth section (Req 19.4)
        parts.append(self._render_breadth_section(report))

        # Sentiment section (Req 19.5)
        parts.append(self._render_sentiment_section(report))

        # Style rotation section (Req 19.6)
        parts.append(self._render_style_section(report))

        # Sector diagnosis section (Req 19.7)
        if report.sector_table:
            parts.append(self._render_sector_section(report))

        # Capital flow section (Req 19.8)
        parts.append(self._render_capital_section(report))

        # Risk alert section (Req 19.9)
        if report.risk_flags:
            parts.append(self._render_risk_alert(report))

        # Strategy mapping section (Req 19.10)
        if report.strategy_mapping:
            parts.append(self._render_strategy_mapping(report))

        # Evidence and confidence section (Req 19.11)
        parts.append(self._render_evidence(report))

        # Missing data section
        if report.missing_data:
            parts.append(self._render_missing_data(report))

        # LLM narrative (Req 19.12)
        if llm_narrative:
            parts.append(self._render_llm_narrative(llm_narrative))

        return "\n\n".join(parts)

    def _render_frontmatter(self, report) -> str:
        """Add YAML frontmatter with metadata."""
        lines = [
            "---",
            f"date: {report.date}",
            f"regime: {report.composite_regime}",
            f"regime_display: {report.get_regime_display_name()}",
            f"confidence: {report.confidence:.2f}",
            f"trend_state: {report.trend_state}",
            f"breadth_state: {report.breadth_state}",
            f"sentiment_state: {report.sentiment_state}",
            f"risk_state: {report.risk_state}",
            f"regime_score: {report.regime_score:.1f}",
            f"missing_data_count: {len(report.missing_data)}",
            "---",
        ]
        return "\n".join(lines)

    def _render_summary(self, report) -> str:
        """Render title and one-sentence summary."""
        parts = [
            f"# {report.date} 大盘全维度诊断\n",
            f"## 一句话结论\n",
            f"{report.one_sentence_summary}\n",
        ]
        return "".join(parts)

    def _render_state_dashboard(self, report) -> str:
        """Render state dashboard table."""
        lines = ["## 状态仪表盘\n"]

        # Summary table
        lines.append("| 维度 | 状态 | 得分 |")
        lines.append("|------|------|------|")
        for item in report.get_state_summary_table():
            score_str = f"{item['score']:.0f}" if item["score"] is not None else "-"
            lines.append(f"| {item['dimension']} | {item['state']} | {score_str} |")

        lines.append("")
        lines.append(
            f"**综合 Regime**: **{report.composite_regime}** "
            f"({report.get_regime_display_name()})，"
            f"得分 **{report.regime_score:.1f}**，置信度 **{report.confidence:.0%}**"
        )

        return "\n".join(lines)

    def _render_index_section(self, report) -> str:
        """Render index structure with technical indicators."""
        lines = ["## 📈 指数与价格结构\n"]

        if report.indices:
            lines.append("| 代码 | MA5 | MA10 | MA20 | MA60 | 均线排列 | MACD信号 | RSRS |")
            lines.append("|------|-----|------|------|------|----------|---------|------|")
            for idx in report.indices:
                lines.append(
                    f"| {idx.get('code', '')} "
                    f"| {idx.get('ma5', 0):.2f} "
                    f"| {idx.get('ma10', 0):.2f} "
                    f"| {idx.get('ma20', 0):.2f} "
                    f"| {idx.get('ma60', 0):.2f} "
                    f"| {idx.get('ma_alignment', '-')} "
                    f"| {idx.get('macd_signal', '-')} "
                    f"| {idx.get('rsrs_score', 0):.2f} |"
                )
        else:
            lines.append("*（暂无指数数据）*")

        return "\n".join(lines)

    def _render_breadth_section(self, report) -> str:
        """Render market breadth metrics table."""
        lines = ["## 🌊 市场广度\n"]

        m = report.breadth_metrics
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 上涨/下跌比 | {m.get('up_down_ratio', 0):.2f} |")
        lines.append(f"| 涨停率 | {m.get('limit_up_rate', 0):.2%} |")
        lines.append(f"| 封板率 | {m.get('seal_rate', 0):.2%} |")
        lines.append(f"| 站上MA20比例 | {m.get('above_ma20_ratio', 0):.2%} |")
        lines.append(f"| 站上MA60比例 | {m.get('above_ma60_ratio', 0):.2%} |")
        lines.append(f"| 创20日新高比例 | {m.get('new_high_ratio', 0):.2%} |")
        lines.append(f"| 广度综合得分 | {m.get('breadth_score', 0):.0f} |")

        return "\n".join(lines)

    def _render_sentiment_section(self, report) -> str:
        """Render sentiment metrics table."""
        lines = ["## 情绪与赚钱效应\n"]

        m = report.sentiment_metrics
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 涨停/跌停比 | {m.get('limit_up_down_ratio', 0):.2f} |")
        lines.append(f"| 连板家数 | {m.get('continuous_limit_up', 0)} |")
        lines.append(f"| 封板率 | {m.get('seal_rate', 0):.2%} |")
        lines.append(f"| 次日溢价 | {m.get('next_day_premium', 0):.2%} |")
        lines.append(f"| 情绪综合分 | {m.get('sentiment_score', 0):.0f} |")

        return "\n".join(lines)

    def _render_style_section(self, report) -> str:
        """Render style rotation relative strength table."""
        lines = ["## 🔄 风格轮动\n"]

        m = report.style_metrics
        lines.append("| 风格对 | 相对强弱 |")
        lines.append("|------|------|")
        rs_large_vs_small = m.get("rs_large_vs_small", 1.0)
        rs_300_vs_1000 = m.get("rs_300_vs_1000", 1.0)
        lines.append(f"| 大盘 vs 创业板 | {rs_large_vs_small:.3f} |")
        lines.append(f"| 沪深300 vs 中证1000 | {rs_300_vs_1000:.3f} |")
        lines.append("")
        lines.append(f"**主导风格**: {m.get('dominant_style', '未知')}")

        return "\n".join(lines)

    def _render_sector_section(self, report) -> str:
        """Render sector diagnosis with top-5 strongest and weakest."""
        lines = ["## 🏭 板块主线诊断\n"]

        top_sectors = report.get_top_sectors(5)
        weak_sectors = report.get_weak_sectors(5)

        lines.append("**强势行业 TOP5**\n")
        if top_sectors:
            lines.append("| 行业 | 强度分 | 持续性分 | 状态 | 成交额占比 |")
            lines.append("|------|--------|----------|------|----------|")
            for s in top_sectors:
                lines.append(
                    f"| {s.get('industry_name', s.get('industry_code', '-'))} "
                    f"| {s.get('strength_score', 0):.2f} "
                    f"| {s.get('persistence_score', 0):.2f} "
                    f"| {s.get('state', '-')} "
                    f"| {s.get('amount_share', 0):.2%} |"
                )
        else:
            lines.append("*（暂无行业数据）*")

        lines.append("")
        lines.append("**弱势行业 TOP5**\n")
        if weak_sectors:
            lines.append("| 行业 | 强度分 | 状态 |")
            lines.append("|------|--------|------|")
            for s in weak_sectors:
                lines.append(
                    f"| {s.get('industry_name', s.get('industry_code', '-'))} "
                    f"| {s.get('strength_score', 0):.2f} "
                    f"| {s.get('state', '-')} |"
                )

        return "\n".join(lines)

    def _render_capital_section(self, report) -> str:
        """Render capital flow metrics."""
        lines = ["## 💰 资金流向\n"]

        m = report.capital_metrics
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        total = m.get("total_amount", 0)
        if total:
            lines.append(f"| 两市成交额 | {total:.0f}亿元 |")
        north = m.get("north_net_flow", 0)
        if north:
            lines.append(f"| 北向净流入 | {north:.1f}亿元 |")
        north_5d = m.get("north_5d_avg", 0)
        if north_5d:
            lines.append(f"| 北向5日均值 | {north_5d:.1f}亿元 |")
        margin = m.get("margin_balance", 0)
        if margin:
            lines.append(f"| 融资余额 | {margin:.0f}亿元 |")
        main = m.get("main_net_flow", 0)
        if main:
            lines.append(f"| 主力净流入 | {main:.1f}亿元 |")

        if m.get("has_delayed_data"):
            lines.append("")
            lines.append("*注：北向和融资数据为T+1延迟*")

        return "\n".join(lines)

    def _render_risk_alert(self, report) -> str:
        """Render active risk flags."""
        lines = ["## ⚠️ 风险警报\n"]

        risk_flag_descriptions = {
            "vol_spike": "已实现波动率超过历史均值2倍",
            "breadth_collapse": "站上MA20比例单日下降超过10个百分点",
            "sector_overcrowding": "单行业成交额占比超过历史均值+2σ",
            "northbound_outflow": "北向资金连续3日净流出",
            "leadership_breakdown": "前5强势行业龙头股平均跌幅超过2%",
            "index_break_support": "沪深300跌破MA60",
        }

        for flag in report.risk_flags:
            desc = risk_flag_descriptions.get(flag, flag)
            lines.append(f"- **{flag}**: {desc}")

        return "\n".join(lines)

    def _render_strategy_mapping(self, report) -> str:
        """Render strategy mapping recommendations."""
        lines = ["## 🗺️ 策略映射建议\n"]

        if not report.strategy_mapping:
            lines.append("*（暂无策略映射数据）*")
            return "\n".join(lines)

        lines.append(f"**当前 Regime**: {report.composite_regime} ({report.get_regime_display_name()})\n")

        # Check if mapping is list of strings (simple) or list of dicts (enriched)
        if report.strategy_mapping and isinstance(report.strategy_mapping[0], dict):
            lines.append("| 策略组 | 配置权重 | 风险等级 | 说明 |")
            lines.append("|--------|----------|----------|------|")
            for item in report.strategy_mapping:
                lines.append(
                    f"| {item.get('strategy_group', '-')} "
                    f"| {item.get('allocation_weight', 0):.0%} "
                    f"| {item.get('risk_level', '-')} "
                    f"| {item.get('description', '-')} |"
                )
        else:
            lines.append("**推荐策略组**：")
            for group in report.strategy_mapping:
                lines.append(f"- {group}")

        return "\n".join(lines)

    def _render_evidence(self, report) -> str:
        """Render evidence and confidence section."""
        lines = ["## 📝 证据与置信度\n"]

        lines.append("**支持证据**：\n")
        for i, ev in enumerate(report.key_evidence, 1):
            lines.append(f"{i}. {ev}")

        if report.counter_evidence:
            lines.append("\n**反向证据**：\n")
            for i, ev in enumerate(report.counter_evidence, 1):
                lines.append(f"{i}. {ev}")

        lines.append(f"\n置信度: **{report.confidence:.0%}**")

        return "\n".join(lines)

    def _render_missing_data(self, report) -> str:
        """Render missing data section."""
        lines = ["## 数据缺失\n"]
        if report.missing_data:
            for item in report.missing_data:
                lines.append(f"- {item}")
        else:
            lines.append("*（无数据缺失）*")
        return "\n".join(lines)

    def _render_llm_narrative(self, narrative: str) -> str:
        """Render LLM-generated narrative section."""
        lines = [
            "## 📖 AI 解读\n",
            narrative,
        ]
        return "\n".join(lines)

    def save_to_file(
        self,
        report,
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
    report,
    llm_narrative: str = "",
) -> str:
    """
    Convenience function to render a diagnostic report as Markdown.

    Parameters
    ----------
    report : DiagnosticReport
        The structured diagnostic report.
    llm_narrative : str, optional
        Optional LLM narrative.

    Returns
    -------
    str
        Markdown-formatted report.
    """
    renderer = DiagnosticMarkdownRenderer()
    return renderer.render(report, llm_narrative=llm_narrative)