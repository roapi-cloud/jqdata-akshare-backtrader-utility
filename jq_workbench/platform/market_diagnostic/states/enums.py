"""
Market State Enums for the Market Diagnostic System.

Defines all state enumerations for trend, breadth, sentiment, style,
sector, risk, and composite regime classifications.
"""

from enum import Enum


class TrendState(str, Enum):
    """Trend state classification (5 levels)."""
    STRONG_UP = "强趋势上行"
    PULLBACK_IN_UPTREND = "趋势上行中的回调"
    RANGING = "震荡"
    WEAKENING = "趋势转弱"
    BREAKDOWN = "破位下行"


class BreadthState(str, Enum):
    """Breadth state classification (5 levels)."""
    EXTREME_WEAK = "极弱"
    WEAK = "偏弱"
    NEUTRAL = "中性"
    STRONG = "偏强"
    OVERHEATED = "过热"


class SentimentState(str, Enum):
    """Sentiment state classification (5 levels)."""
    FROZEN = "冰点"
    WARMING = "回暖"
    NEUTRAL = "中性"
    ACTIVE = "活跃"
    EUPHORIC = "狂热"


class StyleState(str, Enum):
    """Style state classification (5 types)."""
    LARGE_CAP_DEFENSIVE = "大盘防守"
    SMALL_CAP_OFFENSIVE = "小盘进攻"
    GROWTH_DOMINANT = "成长主导"
    DIVIDEND_DEFENSIVE = "红利防守"
    STYLE_CONFLICT = "风格冲突"


class SectorState(str, Enum):
    """Sector rotation state classification (5 types)."""
    NO_THEME = "无主线"
    SINGLE_THEME = "单主线"
    DUAL_THEME = "双主线并行"
    FAST_ROTATION = "高速轮动"
    FADING = "退潮分化"


class RiskState(str, Enum):
    """Risk level classification (4 levels)."""
    LOW = "低风险"
    NEUTRAL = "中性风险"
    HIGH = "高风险"
    EXTREME = "极端风险"


class CompositeRegime(str, Enum):
    """
    Composite market regime (7 types).
    Highest priority: HIGH_VOL_WARNING > PANIC_BOTTOMING > BROAD_WEAKNESS_HOLD
    > TREND_RISK_ON_* > DEFENSIVE_DIVIDEND > BALANCED_ROTATION
    """
    TREND_RISK_ON_GROWTH = "trend_risk_on_growth"
    TREND_RISK_ON_SMALLCAP = "trend_risk_on_smallcap"
    BALANCED_ROTATION = "balanced_rotation"
    DEFENSIVE_DIVIDEND = "defensive_dividend"
    HIGH_VOL_WARNING = "high_volatility_warning"
    PANIC_BOTTOMING = "panic_bottoming"
    BROAD_WEAKNESS_HOLD = "broad_weakness_hold"


# Breadth state thresholds (above_ma20_ratio boundaries)
BREADTH_THRESHOLDS = {
    "extreme_weak": 0.20,
    "weak": 0.35,
    "neutral": 0.55,
    "strong": 0.70,
}

# Risk flag definitions (6 flags)
RISK_FLAG_DEFINITIONS = {
    "vol_spike": "已实现波动率 > 2倍历史均值",
    "breadth_collapse": "站上MA20比例单日下降 > 10pct",
    "sector_overcrowding": "单行业成交额占比 > 历史均值 + 2σ",
    "northbound_outflow": "北向连续3日净流出",
    "leadership_breakdown": "前5强势行业龙头股平均跌幅 > 2%",
    "index_break_support": "沪深300跌破MA60",
}

# Regime to strategy group mapping
REGIME_STRATEGY_MAPPING = {
    "trend_risk_on_growth": ["趋势ETF组", "行业轮动组", "小市值进攻组"],
    "trend_risk_on_smallcap": ["趋势ETF组", "小市值进攻组"],
    "balanced_rotation": ["行业轮动组", "红利价值组", "股债平衡组"],
    "defensive_dividend": ["红利价值组", "股债平衡组"],
    "high_volatility_warning": ["红利价值组", "股债平衡组", "全天候组"],
    "panic_bottoming": ["趋势ETF组小仓试探"],
    "broad_weakness_hold": ["股债平衡组", "全天候组", "高现金"],
}
