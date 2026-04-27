"""
Regime to Strategy Mapping

Maps the 7 composite market regimes to recommended strategy groups with
allocation weights, descriptions, and risk profiles.

Reference: Requirements 20.1-20.7
"""

from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class StrategyAllocation:
    """A strategy group with allocation weight and metadata."""
    strategy_group: str
    allocation_weight: float
    risk_level: str = "medium"  # "low", "medium", "high"
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            "strategy_group": self.strategy_group,
            "allocation_weight": self.allocation_weight,
            "risk_level": self.risk_level,
            "description": self.description,
        }


@dataclass
class RegimeRecommendation:
    """Complete regime recommendation with all strategy groups."""
    regime: str
    display_name: str
    description: str
    allocations: List[StrategyAllocation]
    suitable_investors: List[str] = None
    expected_return: str = ""
    max_drawdown_warn: str = ""

    def __post_init__(self):
        if self.suitable_investors is None:
            self.suitable_investors = []

    def to_dict(self) -> Dict:
        return {
            "regime": self.regime,
            "display_name": self.display_name,
            "description": self.description,
            "allocations": [a.to_dict() for a in self.allocations],
            "suitable_investors": self.suitable_investors,
            "expected_return": self.expected_return,
            "max_drawdown_warn": self.max_drawdown_warn,
        }


# ---------------------------------------------------------------------------
# Regime Definitions (7 Composite Regimes)
# ---------------------------------------------------------------------------

_REGIME_RECOMMENDATIONS: Dict[str, RegimeRecommendation] = {
    "trend_risk_on_growth": RegimeRecommendation(
        regime="trend_risk_on_growth",
        display_name="趋势进攻·成长主导",
        description="市场处于强趋势上行阶段，成长风格占优。适合重仓趋势ETF并配合行业轮动和小市值进攻策略。",
        allocations=[
            StrategyAllocation("趋势ETF组", 0.50, "high", "跟踪趋势，顺势而为，适合趋势型投资者"),
            StrategyAllocation("行业轮动组", 0.30, "medium", "把握行业轮动机会，适合积极型投资者"),
            StrategyAllocation("小市值进攻组", 0.20, "high", "小市值高弹性，适合激进型投资者"),
        ],
        suitable_investors=["积极型", "激进型"],
        expected_return="高",
        max_drawdown_warn="趋势反转时回撤可能较大",
    ),
    "trend_risk_on_smallcap": RegimeRecommendation(
        regime="trend_risk_on_smallcap",
        display_name="趋势进攻·小盘主导",
        description="市场处于强趋势上行阶段，小盘风格占优。趋势ETF为主力仓位，小市值进攻组为重要补充。",
        allocations=[
            StrategyAllocation("趋势ETF组", 0.55, "high", "跟踪趋势，顺势而为"),
            StrategyAllocation("小市值进攻组", 0.30, "high", "小市值高弹性配置"),
            StrategyAllocation("行业轮动组", 0.15, "medium", "辅助轮动机会"),
        ],
        suitable_investors=["积极型", "激进型"],
        expected_return="高",
        max_drawdown_warn="小盘股流动性风险",
    ),
    "balanced_rotation": RegimeRecommendation(
        regime="balanced_rotation",
        display_name="均衡轮动",
        description="市场处于震荡整理阶段，行业轮动活跃。建议均衡配置行业轮动、红利价值和股债平衡策略。",
        allocations=[
            StrategyAllocation("行业轮动组", 0.40, "medium", "把握行业轮动机会"),
            StrategyAllocation("红利价值组", 0.35, "low", "稳定红利，防御性强"),
            StrategyAllocation("股债平衡组", 0.25, "low", "股债平衡，稳健配置"),
        ],
        suitable_investors=["稳健型", "积极型"],
        expected_return="中",
        max_drawdown_warn="轮动加速时可能频繁止损",
    ),
    "defensive_dividend": RegimeRecommendation(
        regime="defensive_dividend",
        display_name="防守·红利",
        description="市场趋势转弱，红利价值风格防御性突出。以红利价值为核心，辅以股债平衡和全天候策略。",
        allocations=[
            StrategyAllocation("红利价值组", 0.45, "low", "高股息，低波动，防御优先"),
            StrategyAllocation("股债平衡组", 0.35, "low", "稳健配置，分散风险"),
            StrategyAllocation("全天候组", 0.20, "low", "多资产配置，适应性强"),
        ],
        suitable_investors=["稳健型", "保守型"],
        expected_return="中低",
        max_drawdown_warn="趋势反转可能踏空",
    ),
    "high_volatility_warning": RegimeRecommendation(
        regime="high_volatility_warning",
        display_name="高波动预警",
        description="市场风险显著上升，波动率处于高位。优先保全资本，提高现金比例，配置全天候和股债平衡策略。",
        allocations=[
            StrategyAllocation("股债平衡组", 0.30, "low", "防御为主"),
            StrategyAllocation("全天候组", 0.30, "low", "多资产分散"),
            StrategyAllocation("高现金配置", 0.40, "low", "保持流动性，等待机会"),
        ],
        suitable_investors=["保守型", "稳健型"],
        expected_return="低",
        max_drawdown_warn="高波动市场，止损纪律很重要",
    ),
    "panic_bottoming": RegimeRecommendation(
        regime="panic_bottoming",
        display_name="恐慌探底",
        description="市场广度极弱、情绪冰点，可能处于阶段性底部。仅以小仓位试探趋势ETF，同时观察小市值反弹信号。",
        allocations=[
            StrategyAllocation("趋势ETF组小仓试探", 0.70, "high", "小仓位试探，严格止损"),
            StrategyAllocation("小市值观察", 0.30, "high", "观察反弹信号，谨慎参与"),
        ],
        suitable_investors=["激进型"],
        expected_return="高风险高回报",
        max_drawdown_warn="底部区域可能继续下探，严格止损",
    ),
    "broad_weakness_hold": RegimeRecommendation(
        regime="broad_weakness_hold",
        display_name="全面弱势·持币观望",
        description="市场破位下行，广度偏弱。以防御性策略为主，保持较高现金比例，等待趋势明朗。",
        allocations=[
            StrategyAllocation("股债平衡组", 0.35, "low", "防御配置"),
            StrategyAllocation("全天候组", 0.35, "low", "多资产分散"),
            StrategyAllocation("高现金配置", 0.30, "low", "持币观望，等待机会"),
        ],
        suitable_investors=["保守型", "稳健型"],
        expected_return="低",
        max_drawdown_warn="下行趋势中避免加仓",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_regime_recommendation(regime: str) -> Optional[RegimeRecommendation]:
    """
    Get complete regime recommendation including all allocations.

    Parameters
    ----------
    regime : str
        Composite regime identifier (e.g., "trend_risk_on_growth").

    Returns
    -------
    RegimeRecommendation or None
        Complete recommendation for the regime.
    """
    return _REGIME_RECOMMENDATIONS.get(regime)


def get_strategy_allocations(regime: str) -> List[Dict]:
    """
    Get strategy group allocations for a regime (simplified dict format).

    Parameters
    ----------
    regime : str
        Composite regime identifier.

    Returns
    -------
    List[Dict]
        List of strategy group allocations with weights.
    """
    rec = get_regime_recommendation(regime)
    if rec is None:
        return []
    return [a.to_dict() for a in rec.allocations]


def get_regime_display_name(regime: str) -> str:
    """
    Get human-readable display name for a regime.

    Parameters
    ----------
    regime : str
        Composite regime identifier.

    Returns
    -------
    str
        Display name in Chinese.
    """
    rec = get_regime_recommendation(regime)
    if rec is None:
        return regime
    return rec.display_name


def get_regime_description_text(regime: str) -> str:
    """
    Get description text for a regime.

    Parameters
    ----------
    regime : str
        Composite regime identifier.

    Returns
    -------
    str
        Description of the regime.
    """
    rec = get_regime_recommendation(regime)
    if rec is None:
        return ""
    return rec.description


def get_all_regime_recommendations() -> List[RegimeRecommendation]:
    """
    Get all regime recommendations.

    Returns
    -------
    List[RegimeRecommendation]
        All 7 regime recommendations sorted by regime name.
    """
    return sorted(
        _REGIME_RECOMMENDATIONS.values(),
        key=lambda r: r.regime,
    )


def get_regime_summary_table() -> List[Dict]:
    """
    Get a summary table of all regimes for display.

    Returns
    -------
    List[Dict]
        List of regime summaries with key info.
    """
    result = []
    for rec in get_all_regime_recommendations():
        total_weight = sum(a.allocation_weight for a in rec.allocations)
        result.append({
            "regime": rec.regime,
            "display_name": rec.display_name,
            "description": rec.description,
            "strategy_count": len(rec.allocations),
            "total_weight": total_weight,
            "suitable_investors": ", ".join(rec.suitable_investors),
            "expected_return": rec.expected_return,
        })
    return result


def apply_strategy_mapping_to_report(report) -> None:
    """
    Apply strategy mapping to a DiagnosticReport.

    Updates the report's strategy_mapping field with enriched
    allocation data for the report's composite_regime.

    Parameters
    ----------
    report : DiagnosticReport
        The report to update in-place.
    """
    allocations = get_strategy_allocations(report.composite_regime)
    report.strategy_mapping = allocations


# Convenience: simple list of strategy groups (backward compatible)
def get_simple_strategy_groups(regime: str) -> List[str]:
    """
    Get simple list of strategy group names for a regime.

    Parameters
    ----------
    regime : str
        Composite regime identifier.

    Returns
    -------
    List[str]
        List of strategy group names.
    """
    rec = get_regime_recommendation(regime)
    if rec is None:
        return []
    return [a.strategy_group for a in rec.allocations]