from __future__ import annotations

import pandas as pd
import pytest

from strategy_kits.contracts import validate_prediction_frame
from strategy_kits.core import ErrorCode, StrategyKitsError
from strategy_kits.portfolio.runtime_state import compute_rebalance_diff


def test_validate_prediction_frame_normalizes_columns():
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "code": [1, "2"],
        }
    )
    out = validate_prediction_frame(df)
    assert "weight" in out.columns
    assert out["code"].tolist() == ["000001", "000002"]
    assert str(out["date"].iloc[0].date()) == "2024-01-01"


def test_compute_rebalance_diff_validates_contracts():
    target = pd.DataFrame({"code": ["000001"], "target_weight": [0.8]})
    current = pd.DataFrame({"code": ["000001"], "weight": [0.3]})
    orders = compute_rebalance_diff(target=target, current=current, ignore_minor=0.0)
    assert len(orders) == 1
    assert orders[0]["delta_weight"] == pytest.approx(0.5)


def test_compute_rebalance_diff_raises_on_missing_columns():
    target = pd.DataFrame({"code": ["000001"], "weight": [0.8]})
    current = pd.DataFrame({"code": ["000001"], "weight": [0.3]})
    with pytest.raises(StrategyKitsError) as exc:
        compute_rebalance_diff(target=target, current=current)
    assert exc.value.code == ErrorCode.CONTRACT_MISSING_COLUMN

