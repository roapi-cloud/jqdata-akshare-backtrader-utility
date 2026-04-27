"""
Strategy Mapping Knowledge Module

Defines the mapping between market regimes and recommended strategy groups.
Includes allocation weights, risk levels, and suitability descriptions.

Reference: Requirements 20.1-20.7
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class StrategyGroup:
    """A strategy group with allocation metadata."""
    name: str
    allocation_weight: float
    risk_level: str  # "low", "medium", "high"
    description: str
    suitable_investors: List[str]


# Strategy group definitions
STRATEGY_GROUPS: Dict[str, StrategyGroup] = {
    "趋势ETF组": StrategyGroup(
        name="趋势ETF组",
        allocation_weight=0.0,  # Set per regime
        risk_level="high",
        description="跟踪趋势，顺势而为。适用于趋势型投资者。推荐标的：创业板ETF、科创50ETF、沪深300ETF。",
        suitable_investors=["积极型", "激进型"],
    ),
    "行业轮动组": StrategyGroup(
        name="行业轮动组",
        allocation_weight=0.0,
        risk_level="medium",
        description="把握行业轮动机会。适用于对行业景气度有判断能力的投资者。推荐方式：行业ETF轮动、主题热点跟踪。",
        suitable_investors=["积极型"],
    ),
    "小市值进攻组": StrategyGroup(
        name="小市值进攻组",
        allocation_weight=0.0,
        risk_level="high",
        description="小市值高弹性配置。适用于激进型投资者。注意流动性风险。推荐方式：小市值ETF、个股精选。",
        suitable_investors=["激进型"],
    ),
    "红利价值组": StrategyGroup(
        name="红利价值组",
        allocation_weight=0.0,
        risk_level="low",
        description="高股息，低波动，防御优先。适用于稳健型投资者。推荐标的：中证红利ETF、红利低波ETF。",
        suitable_investors=["稳健型", "保守型"],
    ),
    "股债平衡组": StrategyGroup(
        name="股债平衡组",
        allocation_weight=0.0,
        risk_level="low",
        description="稳健配置，分散风险。股债比例通常为5:5或4:6。推荐方式：可转债、股债平衡基金。",
        suitable_investors=["稳健型", "保守型"],
    ),
    "全天候组": StrategyGroup(
        name="全天候组",
        allocation_weight=0.0,
        risk_level="low",
        description="多资产配置，适应性强。桥水全天候策略的A股适配版本。推荐方式：多资产配置FOF。",
        suitable_investors=["稳健型", "保守型"],
    ),
    "高现金配置": StrategyGroup(
        name="高现金配置",
        allocation_weight=0.0,
        risk_level="low",
        description="保持流动性，等待机会。在高波动或下行市场中尤为重要。推荐方式：货币基金、短期理财。",
        suitable_investors=["保守型", "稳健型"],
    ),
}


# Regime → Strategy mapping with full metadata
REGIME_STRATEGY_MAPPING: Dict[str, Dict] = {
    "trend_risk_on_growth": {
        "display_name": "趋势进攻·成长主导",
        "description": "市场处于强趋势上行阶段，成长风格占优。适合重仓趋势ETF并配合行业轮动和小市值进攻策略。",
        "allocations": [
            {"strategy_group": "趋势ETF组", "allocation_weight": 0.50},
            {"strategy_group": "行业轮动组", "allocation_weight": 0.30},
            {"strategy_group": "小市值进攻组", "allocation_weight": 0.20},
        ],
        "suitable_investors": ["积极型", "激进型"],
        "expected_return": "高",
        "max_drawdown_warn": "趋势反转时回撤可能较大",
    },
    "trend_risk_on_smallcap": {
        "display_name": "趋势进攻·小盘主导",
        "description": "市场处于强趋势上行阶段，小盘风格占优。趋势ETF为主力仓位，小市值进攻组为重要补充。",
        "allocations": [
            {"strategy_group": "趋势ETF组", "allocation_weight": 0.55},
            {"strategy_group": "小市值进攻组", "allocation_weight": 0.30},
            {"strategy_group": "行业轮动组", "allocation_weight": 0.15},
        ],
        "suitable_investors": ["积极型", "激进型"],
        "expected_return": "高",
        "max_drawdown_warn": "小盘股流动性风险",
    },
    "balanced_rotation": {
        "display_name": "均衡轮动",
        "description": "市场处于震荡整理阶段，行业轮动活跃。建议均衡配置行业轮动、红利价值和股债平衡策略。",
        "allocations": [
            {"strategy_group": "行业轮动组", "allocation_weight": 0.40},
            {"strategy_group": "红利价值组", "allocation_weight": 0.35},
            {"strategy_group": "股债平衡组", "allocation_weight": 0.25},
        ],
        "suitable_investors": ["稳健型", "积极型"],
        "expected_return": "中",
        "max_drawdown_warn": "轮动加速时可能频繁止损",
    },
    "defensive_dividend": {
        "display_name": "防守·红利",
        "description": "市场趋势转弱，红利价值风格防御性突出。以红利价值为核心，辅以股债平衡和全天候策略。",
        "allocations": [
            {"strategy_group": "红利价值组", "allocation_weight": 0.45},
            {"strategy_group": "股债平衡组", "allocation_weight": 0.35},
            {"strategy_group": "全天候组", "allocation_weight": 0.20},
        ],
        "suitable_investors": ["稳健型", "保守型"],
        "expected_return": "中低",
        "max_drawdown_warn": "趋势反转可能踏空",
    },
    "high_volatility_warning": {
        "display_name": "高波动预警",
        "description": "市场风险显著上升，波动率处于高位。优先保全资本，提高现金比例，配置全天候和股债平衡策略。",
        "allocations": [
            {"strategy_group": "高现金配置", "allocation_weight": 0.40},
            {"strategy_group": "股债平衡组", "allocation_weight": 0.30},
            {"strategy_group": "全天候组", "allocation_weight": 0.30},
        ],
        "suitable_investors": ["保守型", "稳健型"],
        "expected_return": "低",
        "max_drawdown_warn": "高波动市场，止损纪律很重要",
    },
    "panic_bottoming": {
        "display_name": "恐慌探底",
        "description": "市场广度极弱、情绪冰点，可能处于阶段性底部。仅以小仓位试探趋势ETF，同时观察小市值反弹信号。",
        "allocations": [
            {"strategy_group": "趋势ETF组", "allocation_weight": 0.70},
            {"strategy_group": "小市值进攻组", "allocation_weight": 0.30},
        ],
        "suitable_investors": ["激进型"],
        "expected_return": "高风险高回报",
        "max_drawdown_warn": "底部区域可能继续下探，严格止损",
    },
    "broad_weakness_hold": {
        "display_name": "全面弱势·持币观望",
        "description": "市场破位下行，广度偏弱。以防御性策略为主，保持较高现金比例，等待趋势明朗。",
        "allocations": [
            {"strategy_group": "高现金配置", "allocation_weight": 0.30},
            {"strategy_group": "股债平衡组", "allocation_weight": 0.35},
            {"strategy_group": "全天候组", "allocation_weight": 0.35},
        ],
        "suitable_investors": ["保守型", "稳健型"],
        "expected_return": "低",
        "max_drawdown_warn": "下行趋势中避免加仓",
    },
}


def get_regime_mapping(regime: str) -> Dict:
    """Get the strategy mapping for a regime."""
    return REGIME_STRATEGY_MAPPING.get(regime, {})


def get_all_regime_mappings() -> List[Dict]:
    """Get all regime strategy mappings."""
    return list(REGIME_STRATEGY_MAPPING.values())


def get_strategy_group(name: str) -> StrategyGroup:
    """Get a strategy group definition."""
    return STRATEGY_GROUPS.get(name)


__all__ = [
    "STRATEGY_GROUPS",
    "REGIME_STRATEGY_MAPPING",
    "StrategyGroup",
    "get_regime_mapping",
    "get_all_regime_mappings",
    "get_strategy_group",
]