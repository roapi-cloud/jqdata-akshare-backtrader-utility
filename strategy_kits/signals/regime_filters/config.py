"""
默认配置与配置校验
"""
from copy import deepcopy
from typing import Dict, Any


DEFAULT_REGIME_CONFIG: Dict[str, Any] = {
    "signals": {
        "market_breadth": {
            "enabled": True,
            "index_code": "000902.XSHG",
            "window": 20,
            "threshold_low": 30.0,
            "threshold_high": 70.0,
        },
        "crowding_rate": {
            "enabled": True,
            "top_pct": 0.05,
            "threshold_low": 40.0,
            "threshold_high": 60.0,
        },
        "new_high_ratio": {
            "enabled": True,
            "window": 252,
            "check_days": 15,
            "gap": 60,
            "threshold_low": 1.0,
            "threshold_high": 5.0,
        },
        "volatility_regime": {
            "enabled": True,
            "method": "atr_approx",
            "short_window": 20,
            "long_window": 60,
            "threshold_high": 1.5,
        },
        "momentum_trend": {
            "enabled": True,
            "method": "icu_ma",
            "fast_window": 6,
            "slow_window": 28,
            "benchmark": "000300.XSHG",
        },
        "cvix_regime": {
            "enabled": True,
            "period": 20,
            "threshold_panic": 0.8,
            "threshold_calm": 0.3,
            "term_structure_threshold": 1.2,
            "weight": 1.5,
        },
    },
    "risk_flags": {
        "extreme_breadth_low": {
            "enabled": True,
            "condition": "market_breadth < 20",
            "severity": "high",
            "suggestion": "市场宽度极低，建议观望",
        },
        "extreme_crowding_high": {
            "enabled": True,
            "condition": "crowding_rate > 65",
            "severity": "medium",
            "suggestion": "资金高度拥挤，建议降仓",
        },
        "volatility_spike": {
            "enabled": True,
            "condition": "volatility_regime > threshold_high",
            "severity": "high",
            "suggestion": "波动率急剧放大，建议观望或收紧止损",
        },
        "momentum_bearish": {
            "enabled": True,
            "condition": "momentum_trend == 0",
            "severity": "medium",
            "suggestion": "趋势转空，建议降仓",
        },
        "cvix_panic": {
            "enabled": True,
            "condition": "cvix_regime > 0.8",
            "severity": "high",
            "suggestion": "CVIX恐慌分位极高，可能是底部抄底机会",
        },
    },
    "composite": {
        "any_high_risk_to_warning": True,
        "medium_risk_count_to_reduce": 2,
        "vote_weights": {
            "market_breadth": 1.0,
            "crowding_rate": 0.8,
            "new_high_ratio": 0.8,
            "volatility_regime": 1.2,
            "momentum_trend": 1.0,
            "cvix_regime": 1.5,
        },
        "thresholds": {
            "allowed": 0.2,
            "reduce": -0.3,
            "hold": -0.6,
        },
    },
}


def merge_config(user_config: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并用户配置到默认配置"""
    base = deepcopy(DEFAULT_REGIME_CONFIG)
    for key, value in user_config.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
