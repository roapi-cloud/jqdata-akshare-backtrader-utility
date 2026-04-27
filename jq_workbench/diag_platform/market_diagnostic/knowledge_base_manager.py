"""
Knowledge Base Manager

Provides indexing, querying, and visualization capabilities for the market
diagnostic knowledge base. Manages diagnostic reports, regime patterns, and
strategy mappings.

Features:
- Index reports by date and regime type
- Query historical reports with filters
- Generate regime timeline visualizations
- Calculate strategy performance statistics
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReportQuery:
    """Query parameters for searching diagnostic reports."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    regime: Optional[str] = None
    min_confidence: Optional[float] = None
    trend_state: Optional[str] = None
    breadth_state: Optional[str] = None
    sentiment_state: Optional[str] = None
    risk_state: Optional[str] = None


@dataclass
class RegimeStats:
    """Statistics for a specific regime type."""
    regime: str
    count: int
    avg_confidence: float
    avg_regime_score: float
    date_range: Tuple[str, str]
    success_rate: Optional[float] = None  # If we track outcome


@dataclass
class TimelineEntry:
    """A single entry in the regime timeline."""
    date: str
    regime: str
    display_name: str
    regime_score: float
    confidence: float
    trend_state: str
    breadth_state: str
    sentiment_state: str
    risk_state: str
    key_evidence: List[str]


# ---------------------------------------------------------------------------
# Knowledge Base Manager
# ---------------------------------------------------------------------------

class KnowledgeBaseManager:
    """
    Manages the market diagnostic knowledge base.

    Provides indexing, querying, and visualization capabilities for
    diagnostic reports, regime patterns, and strategy mappings.

    Directory structure:
        knowledge/
        ├── diagnostic_reports/YYYY-MM/YYYY-MM-DD_regime_report.{md,json}
        ├── regime_patterns/{regime}/
        └── strategy_mapping/
    """

    def __init__(
        self,
        base_path: str = None,
        diagnostic_reports_path: str = None,
        regime_patterns_path: str = None,
        strategy_mapping_path: str = None,
    ):
        """
        Initialize the KnowledgeBaseManager.

        Parameters
        ----------
        base_path : str, optional
            Base path for the knowledge base. If provided, subdirectories
            are inferred from standard locations.
        diagnostic_reports_path : str, optional
            Path to diagnostic reports directory.
        regime_patterns_path : str, optional
            Path to regime patterns directory.
        strategy_mapping_path : str, optional
            Path to strategy mapping directory.
        """
        if base_path:
            self.base_path = Path(base_path)
            self.diagnostic_reports_path = self.base_path / "diagnostic_reports"
            self.regime_patterns_path = self.base_path / "regime_patterns"
            self.strategy_mapping_path = self.base_path / "strategy_mapping"
        else:
            if diagnostic_reports_path:
                self.diagnostic_reports_path = Path(diagnostic_reports_path)
            else:
                self.diagnostic_reports_path = Path(__file__).parent.parent.parent / "knowledge" / "diagnostic_reports"

            if regime_patterns_path:
                self.regime_patterns_path = Path(regime_patterns_path)
            else:
                self.regime_patterns_path = Path(__file__).parent.parent.parent / "knowledge" / "regime_patterns"

            if strategy_mapping_path:
                self.strategy_mapping_path = Path(strategy_mapping_path)
            else:
                self.strategy_mapping_path = Path(__file__).parent.parent.parent / "knowledge" / "strategy_mapping"

        self.base_path = self.diagnostic_reports_path.parent
        self._ensure_directories()
        self._report_index: Optional[Dict[str, Dict]] = None

    def _ensure_directories(self) -> None:
        """Ensure all knowledge base directories exist."""
        self.diagnostic_reports_path.mkdir(parents=True, exist_ok=True)
        self.regime_patterns_path.mkdir(parents=True, exist_ok=True)
        self.strategy_mapping_path.mkdir(parents=True, exist_ok=True)

        # Create month directories for diagnostic reports
        now = datetime.now()
        for months_back in range(12):
            month_date = now - timedelta(days=months_back * 30)
            month_dir = self.diagnostic_reports_path / month_date.strftime("%Y-%m")
            month_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Report storage and retrieval
    # -------------------------------------------------------------------------

    def save_report(
        self,
        report_dict: Dict,
        date: str = None,
        format: str = "both",
    ) -> List[str]:
        """
        Save a diagnostic report to the knowledge base.

        Parameters
        ----------
        report_dict : Dict
            Report data as a dictionary (from DiagnosticReport.to_dict()).
        date : str, optional
            Report date in YYYY-MM-DD format. If not provided, uses today's date.
        format : str
            Save format: "markdown", "json", or "both" (default).

        Returns
        -------
        List[str]
            List of file paths where the report was saved.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Parse date for month directory
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        month_dir = self.diagnostic_reports_path / date_obj.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)

        regime = report_dict.get("composite_regime", "unknown")
        base_name = f"{date}_{regime}_report"

        saved_files = []

        if format in ("json", "both"):
            json_path = month_dir / f"{base_name}.json"
            self._save_json_report(report_dict, json_path)
            saved_files.append(str(json_path))

        if format in ("markdown", "both"):
            md_path = month_dir / f"{base_name}.md"
            self._save_markdown_report(report_dict, md_path)
            saved_files.append(str(md_path))

        # Invalidate cache
        self._report_index = None
        logger.info(f"Saved diagnostic report to {saved_files}")
        return saved_files

    def _save_json_report(self, report_dict: Dict, filepath: Path) -> None:
        """Save report as JSON."""
        data = dict(report_dict)
        data["_meta"] = {
            "generated_at": datetime.now().isoformat(),
            "source": "market_diagnostic_knowledge_base",
            "version": "1.0",
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_markdown_report(self, report_dict: Dict, filepath: Path) -> None:
        """Save report as Markdown."""
        lines = [
            "---",
            f"date: {report_dict.get('date', '')}",
            f"regime: {report_dict.get('composite_regime', '')}",
            f"confidence: {report_dict.get('confidence', 0):.2f}",
            "---",
            "",
            f"# {report_dict.get('date', '')} 大盘诊断报告",
            "",
            f"**综合Regime**: {report_dict.get('composite_regime', 'N/A')}",
            f"**置信度**: {report_dict.get('confidence', 0):.0%}",
            "",
            "## 状态摘要",
            "",
        ]

        states = [
            ("趋势", report_dict.get("trend_state")),
            ("广度", report_dict.get("breadth_state")),
            ("情绪", report_dict.get("sentiment_state")),
            ("风格", report_dict.get("style_state")),
            ("板块", report_dict.get("sector_state")),
            ("风险", report_dict.get("risk_state")),
        ]

        for name, state in states:
            if state:
                lines.append(f"- **{name}**: {state}")

        key_evidence = report_dict.get("key_evidence", [])
        if key_evidence:
            lines.append("")
            lines.append("## 关键证据")
            for ev in key_evidence:
                lines.append(f"- {ev}")

        counter_evidence = report_dict.get("counter_evidence", [])
        if counter_evidence:
            lines.append("")
            lines.append("## 反向证据")
            for ev in counter_evidence:
                lines.append(f"- {ev}")

        lines.append("")
        lines.append(f"*本报告由大盘全维度诊断系统自动生成*")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # -------------------------------------------------------------------------
    # Report indexing
    # -------------------------------------------------------------------------

    def _build_report_index(self) -> Dict[str, Dict]:
        """
        Build or rebuild the report index.

        Returns
        -------
        Dict[str, Dict]
            Index mapping date → report metadata.
        """
        index: Dict[str, Dict] = {}

        if not self.diagnostic_reports_path.exists():
            return index

        for month_dir in self.diagnostic_reports_path.iterdir():
            if not month_dir.is_dir():
                continue
            for json_file in month_dir.glob("*_report.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Skip metadata
                    if "_meta" in data:
                        del data["_meta"]

                    date = data.get("date")
                    if date:
                        index[date] = {
                            "filepath": str(json_file),
                            "regime": data.get("composite_regime"),
                            "confidence": data.get("confidence"),
                            "regime_score": data.get("regime_score"),
                            "trend_state": data.get("trend_state"),
                            "breadth_state": data.get("breadth_state"),
                            "sentiment_state": data.get("sentiment_state"),
                            "risk_state": data.get("risk_state"),
                            "one_sentence_summary": data.get("one_sentence_summary"),
                        }
                except Exception as exc:
                    logger.warning(f"Failed to index {json_file}: {exc}")

        self._report_index = index
        return index

    def get_report_index(self) -> Dict[str, Dict]:
        """
        Get the report index (builds if needed).

        Returns
        -------
        Dict[str, Dict]
            Report index mapping date → metadata.
        """
        if self._report_index is None:
            self._build_report_index()
        return self._report_index or {}

    # -------------------------------------------------------------------------
    # Query methods
    # -------------------------------------------------------------------------

    def query_reports(self, query: ReportQuery) -> List[Dict]:
        """
        Query diagnostic reports with filters.

        Parameters
        ----------
        query : ReportQuery
            Query parameters for filtering reports.

        Returns
        -------
        List[Dict]
            List of matching report data dictionaries.
        """
        index = self.get_report_index()
        results = []

        for date_str, meta in index.items():
            # Date filter
            if query.start_date and date_str < query.start_date:
                continue
            if query.end_date and date_str > query.end_date:
                continue

            # Regime filter
            if query.regime and meta.get("regime") != query.regime:
                continue

            # Confidence filter
            if query.min_confidence is not None:
                conf = meta.get("confidence", 0)
                if conf is None or conf < query.min_confidence:
                    continue

            # State filters
            if query.trend_state and meta.get("trend_state") != query.trend_state:
                continue
            if query.breadth_state and meta.get("breadth_state") != query.breadth_state:
                continue
            if query.sentiment_state and meta.get("sentiment_state") != query.sentiment_state:
                continue
            if query.risk_state and meta.get("risk_state") != query.risk_state:
                continue

            # Load full report data
            filepath = meta.get("filepath")
            if filepath:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "_meta" in data:
                        del data["_meta"]
                    results.append(data)
                except Exception as exc:
                    logger.warning(f"Failed to load report {filepath}: {exc}")

        # Sort by date descending
        results.sort(key=lambda x: x.get("date", ""), reverse=True)
        return results

    def get_report_by_date(self, date: str) -> Optional[Dict]:
        """
        Get a specific report by date.

        Parameters
        ----------
        date : str
            Report date in YYYY-MM-DD format.

        Returns
        -------
        Dict or None
            Report data or None if not found.
        """
        index = self.get_report_index()
        meta = index.get(date)
        if not meta:
            return None

        filepath = meta.get("filepath")
        if not filepath:
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "_meta" in data:
                del data["_meta"]
            return data
        except Exception as exc:
            logger.warning(f"Failed to load report for {date}: {exc}")
            return None

    def get_reports_by_regime(
        self,
        regime: str,
        start_date: str = None,
        end_date: str = None,
    ) -> List[Dict]:
        """
        Get all reports for a specific regime.

        Parameters
        ----------
        regime : str
            Composite regime identifier.
        start_date : str, optional
            Start date filter.
        end_date : str, optional
            End date filter.

        Returns
        -------
        List[Dict]
            List of reports for the regime.
        """
        query = ReportQuery(
            regime=regime,
            start_date=start_date,
            end_date=end_date,
        )
        return self.query_reports(query)

    def get_recent_reports(self, days: int = 30, regime: str = None) -> List[Dict]:
        """
        Get the most recent reports.

        Parameters
        ----------
        days : int
            Number of days to look back (default 30).
        regime : str, optional
            Optional regime filter.

        Returns
        -------
        List[Dict]
            Recent reports sorted by date descending.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = ReportQuery(
            start_date=start_date,
            end_date=end_date,
            regime=regime,
        )
        return self.query_reports(query)

    # -------------------------------------------------------------------------
    # Statistics and analytics
    # -------------------------------------------------------------------------

    def get_regime_stats(self, start_date: str = None, end_date: str = None) -> List[RegimeStats]:
        """
        Calculate statistics for each regime type.

        Parameters
        ----------
        start_date : str, optional
            Start date filter.
        end_date : str, optional
            End date filter.

        Returns
        -------
        List[RegimeStats]
            Statistics for each regime type.
        """
        query = ReportQuery(start_date=start_date, end_date=end_date)
        reports = self.query_reports(query)

        regime_data: Dict[str, List] = {}
        for report in reports:
            regime = report.get("composite_regime", "unknown")
            if regime not in regime_data:
                regime_data[regime] = []
            regime_data[regime].append(report)

        stats = []
        for regime, reports in regime_data.items():
            if not reports:
                continue

            confidences = [r.get("confidence", 0) for r in reports if r.get("confidence") is not None]
            scores = [r.get("regime_score", 0) for r in reports if r.get("regime_score") is not None]
            dates = [r.get("date", "") for r in reports]

            stats.append(RegimeStats(
                regime=regime,
                count=len(reports),
                avg_confidence=sum(confidences) / len(confidences) if confidences else 0,
                avg_regime_score=sum(scores) / len(scores) if scores else 0,
                date_range=(min(dates), max(dates)) if dates else ("", ""),
            ))

        return sorted(stats, key=lambda s: s.count, reverse=True)

    def get_regime_timeline(
        self,
        start_date: str = None,
        end_date: str = None,
    ) -> List[TimelineEntry]:
        """
        Generate a timeline of regime classifications.

        Parameters
        ----------
        start_date : str, optional
            Start date filter.
        end_date : str, optional
            End date filter.

        Returns
        -------
        List[TimelineEntry]
            Timeline of regime states sorted by date.
        """
        query = ReportQuery(start_date=start_date, end_date=end_date)
        reports = self.query_reports(query)

        # Import regime display names
        try:
            from diag_platform.market_diagnostic.strategy_mapping import get_regime_display_name
        except ImportError:
            from strategy_mapping import get_regime_display_name

        timeline = []
        for report in reports:
            regime = report.get("composite_regime", "unknown")
            timeline.append(TimelineEntry(
                date=report.get("date", ""),
                regime=regime,
                display_name=get_regime_display_name(regime),
                regime_score=report.get("regime_score", 0),
                confidence=report.get("confidence", 0),
                trend_state=report.get("trend_state", ""),
                breadth_state=report.get("breadth_state", ""),
                sentiment_state=report.get("sentiment_state", ""),
                risk_state=report.get("risk_state", ""),
                key_evidence=report.get("key_evidence", [])[:3],
            ))

        # Sort by date
        timeline.sort(key=lambda x: x.date)
        return timeline

    def get_strategy_performance_summary(
        self,
        start_date: str = None,
        end_date: str = None,
    ) -> Dict[str, Any]:
        """
        Generate a summary of strategy mapping effectiveness.

        Parameters
        ----------
        start_date : str, optional
            Start date filter.
        end_date : str, optional
            End date filter.

        Returns
        -------
        Dict
            Strategy performance summary.
        """
        query = ReportQuery(start_date=start_date, end_date=end_date)
        reports = self.query_reports(query)

        regime_counts: Dict[str, int] = {}
        for report in reports:
            regime = report.get("composite_regime", "unknown")
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        # Calculate confidence statistics
        confidences = [r.get("confidence", 0) for r in reports if r.get("confidence")]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "total_reports": len(reports),
            "regime_distribution": regime_counts,
            "avg_confidence": avg_confidence,
            "date_range": {
                "start": reports[-1].get("date", "") if reports else "",
                "end": reports[0].get("date", "") if reports else "",
            },
        }

    # -------------------------------------------------------------------------
    # Visualization helpers
    # -------------------------------------------------------------------------

    def generate_regime_timeline_ascii(
        self,
        start_date: str = None,
        end_date: str = None,
        width: int = 80,
    ) -> str:
        """
        Generate an ASCII visualization of the regime timeline.

        Parameters
        ----------
        start_date : str, optional
            Start date filter.
        end_date : str, optional
            End date filter.
        width : int
            Display width in characters.

        Returns
        -------
        str
            ASCII art timeline visualization.
        """
        timeline = self.get_regime_timeline(start_date, end_date)
        if not timeline:
            return "（暂无数据）"

        # Map regimes to single characters for compact display
        regime_chars = {
            "trend_risk_on_growth": "▲",
            "trend_risk_on_smallcap": "△",
            "balanced_rotation": "●",
            "defensive_dividend": "▼",
            "high_volatility_warning": "◆",
            "panic_bottoming": "◇",
            "broad_weakness_hold": "○",
        }

        lines = ["## Regime 时间线\n"]

        for entry in timeline:
            date_str = entry.date[5:]  # MM-DD
            regime_char = regime_chars.get(entry.regime, "?")
            conf_indicator = "✓" if entry.confidence >= 0.7 else "✗"

            lines.append(
                f"{date_str} [{regime_char}] {entry.display_name} "
                f"(得分{entry.regime_score:.0f}, 置信{entry.confidence:.0%}) {conf_indicator}"
            )

        return "\n".join(lines)

    def generate_regime_distribution_text(
        self,
        start_date: str = None,
        end_date: str = None,
    ) -> str:
        """
        Generate text showing regime distribution.

        Parameters
        ----------
        start_date : str, optional
            Start date filter.
        end_date : str, optional
            End date filter.

        Returns
        -------
        str
            Text showing regime distribution.
        """
        stats = self.get_regime_stats(start_date, end_date)
        if not stats:
            return "（暂无数据）"

        lines = ["## Regime 分布统计\n"]

        total = sum(s.count for s in stats)

        for stat in stats:
            pct = stat.count / total * 100 if total > 0 else 0
            bar_len = int(pct / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(
                f"{stat.regime:30s} {bar} {pct:5.1f}% ({stat.count}次) "
                f"avg_conf={stat.avg_confidence:.0%}"
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_default_kb: Optional[KnowledgeBaseManager] = None


def get_knowledge_base(
    base_path: str = None,
) -> KnowledgeBaseManager:
    """
    Get the default knowledge base manager instance.

    Parameters
    ----------
    base_path : str, optional
        Base path for the knowledge base.

    Returns
    -------
    KnowledgeBaseManager
        The singleton knowledge base manager.
    """
    global _default_kb
    if _default_kb is None:
        _default_kb = KnowledgeBaseManager(base_path=base_path)
    return _default_kb


def save_diagnostic_report(
    report_dict: Dict,
    date: str = None,
    base_path: str = None,
) -> List[str]:
    """
    Convenience function to save a diagnostic report.

    Parameters
    ----------
    report_dict : Dict
        Report data dictionary.
    date : str, optional
        Report date.
    base_path : str, optional
        Knowledge base path.

    Returns
    -------
    List[str]
        Saved file paths.
    """
    kb = get_knowledge_base(base_path=base_path)
    return kb.save_report(report_dict, date=date)