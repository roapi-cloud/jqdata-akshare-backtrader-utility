"""
统一调度引擎

按 config 调度各 filter -> composite_gate -> RegimeFilterOutput
"""
from typing import Dict, List, Optional, Any
import pandas as pd

from .contract import RegimeFilterOutput, SubSignal, RiskFlag, RegimeState
from .config import merge_config
from .composite_gate import route_regime
from .breadth_filter import calc_market_breadth
from .crowding_filter import calc_crowding_rate
from .newhigh_filter import calc_new_high_ratio
from .volatility_filter import calc_volatility_regime
from .momentum_filter import calc_momentum_trend
from .cvix_filter import calc_cvix_regime


def run_regime_gate(
    market_data: pd.DataFrame,
    breadth_data: Optional[pd.DataFrame] = None,
    config: Optional[Dict[str, Any]] = None,
    date: Optional[str] = None,
) -> RegimeFilterOutput:
    """
    运行总闸门，输出市场状态。

    Parameters
    ----------
    market_data : pd.DataFrame
        指数行情数据，index-date，列至少包含 open/high/low/close/volume
    breadth_data : pd.DataFrame, optional
        全市场个股状态数据，供 market_breadth / crowding_rate 等计算使用
    config : dict, optional
        用户自定义配置，会与默认配置深度合并
    date : str, optional
        计算日期（YYYY-MM-DD），如不传入默认使用 market_data 最后一天

    Returns
    -------
    RegimeFilterOutput
    """
    cfg = merge_config(config or {})
    calc_date = date or str(market_data.index[-1])

    sub_signals: List[SubSignal] = []
    risk_flags: List[RiskFlag] = []
    raw_scores: Dict[str, float] = {}

    sig_cfg = cfg.get("signals", {})

    # 1. market_breadth
    if sig_cfg.get("market_breadth", {}).get("enabled", False):
        s = calc_market_breadth(market_data, breadth_data, sig_cfg["market_breadth"], calc_date)
        if s:
            sub_signals.append(s)
            raw_scores["market_breadth"] = s.value

    # 2. crowding_rate
    if sig_cfg.get("crowding_rate", {}).get("enabled", False):
        s = calc_crowding_rate(market_data, breadth_data, sig_cfg["crowding_rate"], calc_date)
        if s:
            sub_signals.append(s)
            raw_scores["crowding_rate"] = s.value

    # 3. new_high_ratio
    if sig_cfg.get("new_high_ratio", {}).get("enabled", False):
        s = calc_new_high_ratio(market_data, breadth_data, sig_cfg["new_high_ratio"], calc_date)
        if s:
            sub_signals.append(s)
            raw_scores["new_high_ratio"] = s.value

    # 4. volatility_regime
    if sig_cfg.get("volatility_regime", {}).get("enabled", False):
        s = calc_volatility_regime(market_data, sig_cfg["volatility_regime"], calc_date)
        if s:
            sub_signals.append(s)
            raw_scores["volatility_regime"] = s.value

    # 5. momentum_trend
    if sig_cfg.get("momentum_trend", {}).get("enabled", False):
        s = calc_momentum_trend(market_data, sig_cfg["momentum_trend"], calc_date)
        if s:
            sub_signals.append(s)
            raw_scores["momentum_trend"] = s.value

    # 6. cvix_regime
    if sig_cfg.get("cvix_regime", {}).get("enabled", False):
        s = calc_cvix_regime(market_data, sig_cfg["cvix_regime"], calc_date)
        if s:
            sub_signals.append(s)
            raw_scores["cvix_regime"] = s.value

    # 7. 风险标志解析（简化版：直接基于阈值判断）
    risk_cfg = cfg.get("risk_flags", {})
    for name, rc in risk_cfg.items():
        if not rc.get("enabled", False):
            continue
        triggered, severity, suggestion = _eval_risk_flag(
            name, rc, raw_scores, sig_cfg
        )
        risk_flags.append(
            RiskFlag(
                name=name,
                triggered=triggered,
                severity=severity,
                suggestion=suggestion,
            )
        )

    # 7. 状态合成
    regime = route_regime(sub_signals, risk_flags, cfg.get("composite", {}))

    return RegimeFilterOutput(
        date=calc_date,
        regime_state=regime,
        sub_signals=sub_signals,
        risk_flags=risk_flags,
        raw_scores=raw_scores,
        config_snapshot=cfg,
    )


def _eval_risk_flag(
    name: str,
    rc: Dict[str, Any],
    raw_scores: Dict[str, float],
    sig_cfg: Dict[str, Any],
) -> tuple:
    """简化风险标志求值"""
    cond = rc.get("condition", "")
    severity = rc.get("severity", "low")
    suggestion = rc.get("suggestion", "")

    # 解析形如 "market_breadth < 20" 或 "volatility_regime > threshold_high" 的条件
    triggered = False
    parts = cond.split()
    if len(parts) == 3:
        var, op, val_str = parts
        val = _resolve_val(val_str, sig_cfg.get(var, {}))
        score = raw_scores.get(var)
        if score is not None:
            triggered = _compare(score, op, val)

    return triggered, severity, suggestion


def _resolve_val(val_str: str, var_cfg: Dict[str, Any]) -> float:
    if val_str in var_cfg:
        return float(var_cfg[val_str])
    try:
        return float(val_str)
    except ValueError:
        return 0.0


def _compare(score: float, op: str, val: float) -> bool:
    if op == "<":
        return score < val
    if op == "<=":
        return score <= val
    if op == ">":
        return score > val
    if op == ">=":
        return score >= val
    if op == "==":
        return score == val
    return False
