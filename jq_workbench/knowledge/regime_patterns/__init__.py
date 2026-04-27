"""
Regime Patterns Knowledge Module

Defines the 7 composite market regimes with their characteristics,
conditions, and historical pattern examples.

Regime Patterns:
1. trend_risk_on_growth     - 趋势进攻·成长主导
2. trend_risk_on_smallcap   - 趋势进攻·小盘主导
3. balanced_rotation        - 均衡轮动
4. defensive_dividend       - 防守·红利
5. high_volatility_warning  - 高波动预警
6. panic_bottoming         - 恐慌探底
7. broad_weakness_hold     - 全面弱势·持币观望
"""

from typing import Dict, List

# All 7 regime patterns with full metadata
REGIME_PATTERNS: Dict[str, Dict] = {
    "trend_risk_on_growth": {
        "regime": "trend_risk_on_growth",
        "display_name": "趋势进攻·成长主导",
        "description": "市场处于强趋势上行阶段，成长风格占优",
        "conditions": {
            "trend_state": "STRONG_UP",
            "breadth_state": "STRONG",
            "sentiment_state": "ACTIVE",
            "style_state": "GROWTH",
        },
        "typical_indicators": [
            "MA多头排列，RSRS > 0.7",
            "站上MA20比例 > 70%",
            "涨停家数 > 100",
            "成长股相对沪深300超额收益明显",
        ],
        "warning_signs": [
            "成交量萎缩",
            "龙头股开始补跌",
            "北向资金开始流出",
        ],
    },
    "trend_risk_on_smallcap": {
        "regime": "trend_risk_on_smallcap",
        "display_name": "趋势进攻·小盘主导",
        "description": "市场处于强趋势上行阶段，小盘风格占优",
        "conditions": {
            "trend_state": "STRONG_UP",
            "breadth_state": "STRONG",
            "sentiment_state": "ACTIVE",
            "style_state": "SMALL_CAP_OFFENSIVE",
        },
        "typical_indicators": [
            "中证1000涨幅明显",
            "小市值因子持续强势",
            "涨停家数维持高位",
            "赚钱效应扩散",
        ],
        "warning_signs": [
            "小市值因子拥挤度上升",
            "大盘股开始补涨",
            "市场广度开始收窄",
        ],
    },
    "balanced_rotation": {
        "regime": "balanced_rotation",
        "display_name": "均衡轮动",
        "description": "市场处于震荡整理阶段，行业轮动活跃",
        "conditions": {
            "trend_state": "RANGING",
            "breadth_state": "NEUTRAL",
            "sentiment_state": "NEUTRAL",
        },
        "typical_indicators": [
            "指数震荡整理",
            "行业轮动加快",
            "无明显主线",
            "成交额相对平稳",
        ],
        "warning_signs": [
            "轮动加速导致止损频繁",
            "热点持续性下降",
            "市场广度持续收窄",
        ],
    },
    "defensive_dividend": {
        "regime": "defensive_dividend",
        "display_name": "防守·红利",
        "description": "市场趋势转弱，红利价值风格防御性突出",
        "conditions": {
            "trend_state": "WEAKENING",
            "breadth_state": "WEAK",
            "sentiment_state": "NEUTRAL",
            "style_state": "DIVIDEND_DEFENSIVE",
        },
        "typical_indicators": [
            "红利指数相对抗跌",
            "高股息股票溢价",
            "市场成交低迷",
            "防御性板块相对强势",
        ],
        "warning_signs": [
            "成交量持续萎缩",
            "情绪开始转向",
            "价值股补跌",
        ],
    },
    "high_volatility_warning": {
        "regime": "high_volatility_warning",
        "display_name": "高波动预警",
        "description": "市场风险显著上升，波动率处于高位",
        "conditions": {
            "risk_state": "EXTREME",
        },
        "typical_indicators": [
            "已实现波动率超过历史均值2倍",
            "VIX或C-VIX指数飙升",
            "成交额大幅放大",
            "多空双方激烈博弈",
        ],
        "warning_signs": [
            "波动率持续高位",
            "市场出现急涨急跌",
            "风险事件频发",
        ],
    },
    "panic_bottoming": {
        "regime": "panic_bottoming",
        "display_name": "恐慌探底",
        "description": "市场广度极弱、情绪冰点，可能处于阶段性底部",
        "conditions": {
            "breadth_state": "EXTREME_WEAK",
            "sentiment_state": "FROZEN",
        },
        "typical_indicators": [
            "站上MA20比例 < 20%",
            "涨停家数极少",
            "市场情绪极度悲观",
            "估值接近历史低位",
        ],
        "warning_signs": [
            "底部区域可能继续下探",
            "政策底出现",
            "资金开始试探性入场",
        ],
    },
    "broad_weakness_hold": {
        "regime": "broad_weakness_hold",
        "display_name": "全面弱势·持币观望",
        "description": "市场破位下行，广度偏弱，以防御为主",
        "conditions": {
            "trend_state": "BREAKDOWN",
            "breadth_state": "WEAK",
        },
        "typical_indicators": [
            "主要均线空头排列",
            "站上MA20比例 < 35%",
            "下跌家数远大于上涨家数",
            "成交额持续低迷",
        ],
        "warning_signs": [
            "下行趋势中避免加仓",
            "严格止损",
            "等待趋势明朗",
        ],
    },
}


def get_regime_pattern(regime: str) -> Dict:
    """Get the pattern definition for a regime."""
    return REGIME_PATTERNS.get(regime, {})


def get_all_regime_patterns() -> List[Dict]:
    """Get all regime pattern definitions."""
    return list(REGIME_PATTERNS.values())


__all__ = [
    "REGIME_PATTERNS",
    "get_regime_pattern",
    "get_all_regime_patterns",
]