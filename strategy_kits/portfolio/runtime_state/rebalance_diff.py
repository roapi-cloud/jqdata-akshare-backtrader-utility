"""Research-oriented rebalance diff utility."""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ...contracts import validate_current_weights_frame, validate_target_weights_frame
from ...core import get_logger, log_kv


_logger = get_logger("portfolio.rebalance_diff")


def compute_rebalance_diff(
    target: pd.DataFrame,
    current: pd.DataFrame,
    ignore_minor: float = 0.001,
) -> List[Dict[str, Any]]:
    """Compute target-current delta list by weight.

    Expected columns:
    - target: ``code``, ``target_weight``
    - current: ``code``, ``weight``
    """
    target = validate_target_weights_frame(target)
    if not current.empty:
        current = validate_current_weights_frame(current)

    cur = current.set_index("code").weight if not current.empty else pd.Series(dtype=float)
    tgt = target.set_index("code").target_weight
    codes = sorted(set(cur.index.tolist()) | set(tgt.index.tolist()))

    orders: List[Dict[str, Any]] = []
    for code in codes:
        w_cur = float(cur.get(code, 0.0))
        w_tgt = float(tgt.get(code, 0.0))
        delta = w_tgt - w_cur
        if abs(delta) < ignore_minor:
            continue
        orders.append(
            {
                "code": code,
                "delta_weight": delta,
                "current_weight": w_cur,
                "target_weight": w_tgt,
            }
        )
    log_kv(
        _logger,
        20,  # logging.INFO
        "rebalance_diff_computed",
        target_count=len(target),
        current_count=len(current),
        orders_count=len(orders),
        ignore_minor=ignore_minor,
    )
    return orders


__all__ = ["compute_rebalance_diff"]
