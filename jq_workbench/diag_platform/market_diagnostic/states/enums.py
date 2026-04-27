"""
State Layer Enumerations

Defines all market state enums used by the diagnostic system.
Reference: Requirements 9-17, design.md Section 3.4
"""

from enum import Enum


class TrendState(str, Enum):
    """
    Trend state classification (5 levels).
    Based on MA alignment, MACD signals, and RSRS score.

    Req 9.1-9.5
    """
    STRONG_UP = "强趋势上行"           # MA5>MA10>MA20>MA60, MACD golden cross, RSRS>0.7
    PULLBACK_IN_UPTREND = "趋势上行中的回调"  # Bullish alignment but MA5<MA10
    RANGING = "震荡"                 # Tangled MAs, MACD near zero
    WEAKENING = "趋势转弱"            # MA5<MA10<MA20 OR MACD death cross
    BREAKDOWN = "破位下行"            # Below MA60 AND RSRS<0.3


class BreadthState(str, Enum):
    """
    Market breadth state classification (5 levels).
    Based on above_ma20_ratio.

    Req 10.1-10.5
    """
    EXTREME_WEAK = "极弱"   # above_ma20 < 20%
    WEAK = "偏弱"           # 20-35%
    NEUTRAL = "中性"        # 35-55%
    STRONG = "偏强"         # 55-70%
    OVERHEATED = "过热"     # > 70%


class SentimentState(str, Enum):
    """
    Market sentiment state classification (5 levels).
    Based on limit-up/limit-down ratio, seal rate, and next-day premium.

    Req 11.1-11.5
    """
    FROZEN = "冰点"    # Very low limit-up rate, high limit-down, low seal rate
    WARMING = "回暖"   # Recovering limit-up rate, improving seal rate
    NEUTRAL = "中性"   # Moderate values
    ACTIVE = "活跃"    # High limit-up, high seal rate, positive next-day premium
    EUPHORIC = "狂热"  # Extreme limit-up, very high seal rate, strong continuous limit-ups


class StyleState(str, Enum):
    """
    Market style state classification (5 levels).
    Based on large-cap vs small-cap, growth vs value relative strength.

    Req 12.1-12.5
    """
    LARGE_CAP_DEFENSIVE = "大盘防守"      # Large-cap outperforming, dividend > growth
    SMALL_CAP_OFFENSIVE = "小盘进攻"      # Small-cap outperforming
    GROWTH_DOMINANT = "成长主导"          # Growth significantly outperforming value
    DIVIDEND_DEFENSIVE = "红利防守"       # Dividend indices outperforming growth
    STYLE_CONFLICT = "风格冲突"          # Conflicting signals across style dimensions


class SectorState(str, Enum):
    """
    Sector rotation state classification (5 levels).
    Based on strength scores and persistence of top sectors.

    Req 13.1-13.5
    """
    NO_THEME = "无主线"           # No sector with strength_score > 1.5
    SINGLE_THEME = "单主线"       # Exactly one sector with strength>2.0 AND persistence>0.7
    DUAL_THEME = "双主线并行"     # Two sectors with strength>1.8 AND persistence>0.6
    FAST_ROTATION = "高速轮动"   # Top-5 rankings changing significantly
    FADING = "退潮分化"           # Declining strength across previously strong sectors


class RiskState(str, Enum):
    """
    Risk state classification (4 levels).
    Based on volatility, drawdown, and risk flags.

    Req 14.1-14.4
    """
    LOW = "低风险"        # Low realized volatility, low drawdown, no risk flags
    NEUTRAL = "中性风险"  # Moderate volatility and drawdown
    HIGH = "高风险"       # Elevated volatility OR significant drawdown OR 1-2 risk flags
    EXTREME = "极端风险"  # Extreme volatility OR severe drawdown OR 3+ risk flags


class CompositeRegime(str, Enum):
    """
    Composite market regime classification (7 types).
    Synthesizes all dimension states into a holistic market state.

    Req 15.1-15.7
    """
    # Trend + growth style with positive conditions
    TREND_RISK_ON_GROWTH = "trend_risk_on_growth"     # Strong trend + growth dominant
    TREND_RISK_ON_SMALLCAP = "trend_risk_on_smallcap"  # Strong trend + small-cap offensive

    # Balanced / neutral conditions
    BALANCED_ROTATION = "balanced_rotation"  # Ranging market, neutral breadth

    # Defensive conditions
    DEFENSIVE_DIVIDEND = "defensive_dividend"  # Dividend defensive style

    # High risk / warning conditions
    HIGH_VOL_WARNING = "high_volatility_warning"  # Extreme or high risk state

    # Bearish / panic conditions
    PANIC_BOTTOMING = "panic_bottoming"      # Extreme weak breadth + frozen sentiment
    BROAD_WEAKNESS_HOLD = "broad_weakness_hold"  # Breakdown/weakening trend + weak breadth
