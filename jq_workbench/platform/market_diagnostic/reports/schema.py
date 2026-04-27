"""
DiagnosticReport Schema

Structured diagnostic report containing all market state information
for machine consumption (JSON export) and human reading (Markdown rendering).

Reference: Requirements 18.1-18.10
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


@dataclass
class DiagnosticReport:
    """
    Structured diagnostic report for the market diagnostic system.

    Contains all state classifications, dimension scores, detailed metrics,
    evidence, and strategy mapping.

    Attributes
    ----------
    date : str
        Trading date in 'YYYY-MM-DD' format.
    trend_state : str
        Trend state label (e.g., "强趋势上行").
    breadth_state : str
        Breadth state label (e.g., "中性").
    sentiment_state : str
        Sentiment state label (e.g., "活跃").
    style_state : str
        Style state label (e.g., "成长主导").
    sector_state : str
        Sector rotation state label (e.g., "单主线").
    risk_state : str
        Risk state label (e.g., "中性风险").
    composite_regime : str
        Composite regime identifier (e.g., "trend_risk_on_growth").
    trend_score : float
        Trend dimension score (0-100).
    breadth_score : float
        Breadth dimension score (0-100).
    sentiment_score : float
        Sentiment dimension score (0-100).
    risk_score : float
        Risk dimension score (0-100, higher = more risk).
    regime_score : float
        Composite regime score (0-100).
    indices : List[Dict]
        Index data with technical indicators for each of the 9 core indices.
    breadth_metrics : Dict
        Market breadth metrics (up/down ratio, MA20 ratio, etc.).
    sentiment_metrics : Dict
        Market sentiment metrics (limit-up/down ratio, seal rate, etc.).
    style_metrics : Dict
        Style relative strength metrics.
    sector_table : List[Dict]
        Industry diagnosis table with strength scores.
    capital_metrics : Dict
        Capital flow metrics (turnover, northbound, margin).
    risk_flags : List[str]
        Active risk warning flags.
    one_sentence_summary : str
        Concise one-sentence market summary.
    key_evidence : List[str]
        3 key supporting evidence items.
    counter_evidence : List[str]
        Counter-evidence items.
    strategy_mapping : List[Dict]
        Regime → strategy group mapping with allocation weights.
    confidence : float
        Overall confidence level (0.1-1.0).
    missing_data : List[str]
        List of unavailable data items.

    Reference: Requirements 18.1-18.10, 19.1-19.12
    """

    date: str = ""
    trend_state: str = ""
    breadth_state: str = ""
    sentiment_state: str = ""
    style_state: str = ""
    sector_state: str = ""
    risk_state: str = ""
    composite_regime: str = ""

    trend_score: float = 50.0
    breadth_score: float = 50.0
    sentiment_score: float = 50.0
    risk_score: float = 50.0
    regime_score: float = 50.0

    indices: List[Dict] = field(default_factory=list)
    breadth_metrics: Dict = field(default_factory=dict)
    sentiment_metrics: Dict = field(default_factory=dict)
    style_metrics: Dict = field(default_factory=dict)
    sector_table: List[Dict] = field(default_factory=list)
    capital_metrics: Dict = field(default_factory=dict)
    risk_flags: List[str] = field(default_factory=list)

    one_sentence_summary: str = ""
    key_evidence: List[str] = field(default_factory=list)
    counter_evidence: List[str] = field(default_factory=list)
    strategy_mapping: List[Dict] = field(default_factory=list)
    confidence: float = 0.5
    missing_data: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        """
        Serialize report to JSON string.

        Returns
        -------
        str
            JSON-formatted report string with all fields.

        Reference: Requirement 18.1
        """
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def to_dict(self) -> Dict:
        """
        Convert report to plain dictionary.

        Returns
        -------
        Dict
            Plain dictionary representation.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "DiagnosticReport":
        """
        Create a DiagnosticReport from a dictionary.

        Parameters
        ----------
        data : Dict
            Dictionary with report fields.

        Returns
        -------
        DiagnosticReport
            New report instance.
        """
        # Extract known fields; pass through any extra as generic fields
        known_fields = {
            "date", "trend_state", "breadth_state", "sentiment_state",
            "style_state", "sector_state", "risk_state", "composite_regime",
            "trend_score", "breadth_score", "sentiment_score", "risk_score",
            "regime_score", "indices", "breadth_metrics", "sentiment_metrics",
            "style_metrics", "sector_table", "capital_metrics", "risk_flags",
            "one_sentence_summary", "key_evidence", "counter_evidence",
            "strategy_mapping", "confidence", "missing_data",
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def get_regime_display_name(self) -> str:
        """Get human-readable display name for composite regime."""
        _display_names = {
            "trend_risk_on_growth": "趋势进攻·成长主导",
            "trend_risk_on_smallcap": "趋势进攻·小盘主导",
            "balanced_rotation": "均衡轮动",
            "defensive_divident": "防守·红利",
            "high_volatility_warning": "高波动预警",
            "panic_bottoming": "恐慌探底",
            "broad_weakness_hold": "全面弱势·持币观望",
        }
        return _display_names.get(self.composite_regime, self.composite_regime)

    def get_state_summary_table(self) -> List[Dict]:
        """
        Get a summary table of all dimension states.

        Returns
        -------
        List[Dict]
            List of {dimension, state, score} dicts.
        """
        return [
            {"dimension": "趋势", "state": self.trend_state, "score": self.trend_score},
            {"dimension": "广度", "state": self.breadth_state, "score": self.breadth_score},
            {"dimension": "情绪", "state": self.sentiment_state, "score": self.sentiment_score},
            {"dimension": "风格", "state": self.style_state, "score": None},
            {"dimension": "板块", "state": self.sector_state, "score": None},
            {"dimension": "风险", "state": self.risk_state, "score": self.risk_score},
        ]

    def get_top_sectors(self, n: int = 5) -> List[Dict]:
        """
        Get top N sectors by strength score.

        Parameters
        ----------
        n : int
            Number of top sectors to return.

        Returns
        -------
        List[Dict]
            Top N sector dicts sorted by strength_score descending.
        """
        sorted_sectors = sorted(
            self.sector_table,
            key=lambda s: s.get("strength_score", 0),
            reverse=True,
        )
        return sorted_sectors[:n]

    def get_weak_sectors(self, n: int = 5) -> List[Dict]:
        """
        Get bottom N sectors by strength score.

        Parameters
        ----------
        n : int
            Number of weak sectors to return.

        Returns
        -------
        List[Dict]
            Bottom N sector dicts sorted by strength_score ascending.
        """
        sorted_sectors = sorted(
            self.sector_table,
            key=lambda s: s.get("strength_score", 0),
        )
        return sorted_sectors[:n]

    def has_risk_flag(self, flag: str) -> bool:
        """
        Check if a specific risk flag is active.

        Parameters
        ----------
        flag : str
            Risk flag name (e.g., "vol_spike").

        Returns
        -------
        bool
            True if flag is active.
        """
        return flag in self.risk_flags

    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        """Check if confidence exceeds threshold."""
        return self.confidence >= threshold

    def __repr__(self) -> str:
        return (
            f"DiagnosticReport(date={self.date!r}, "
            f"regime={self.composite_regime!r}, "
            f"confidence={self.confidence:.0%})"
        )