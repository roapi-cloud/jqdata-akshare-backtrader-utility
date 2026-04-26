from __future__ import annotations

import pytest

from strategy_kits.core.errors import StrategyKitsError
from strategy_kits.orchestration import validate_strategy_task_spec


def test_validate_strategy_task_spec_with_defaults():
    spec = {
        "task": {"task_id": "t1", "strategy_name": "demo"},
        "data": {
            "panel_type": "pool_panel",
            "panel_path": "/tmp/pool.csv",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        },
        "backtest": {"template": "WeightedTopNStrategy", "initial_cash": 1_000_000},
    }
    out = validate_strategy_task_spec(spec)
    assert out["pipeline"]["top_n"] == 20
    assert out["pipeline"]["weight_mode"] == "score"
    assert out["portfolio"]["max_positions"] >= out["pipeline"]["top_n"]
    assert out["backtest"]["hold_days"] == 1
    assert out["output"]["save_artifacts"] is True


def test_validate_strategy_task_spec_requires_panel_path():
    spec = {
        "task": {"task_id": "t1", "strategy_name": "demo"},
        "data": {
            "panel_type": "score_panel",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        },
        "backtest": {"template": "WeightedTopNStrategy", "initial_cash": 1_000_000},
    }
    with pytest.raises(StrategyKitsError):
        validate_strategy_task_spec(spec)


def test_validate_strategy_task_spec_rejects_unknown_template():
    spec = {
        "task": {"task_id": "t1", "strategy_name": "demo"},
        "data": {
            "panel_type": "local_features",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        },
        "backtest": {"template": "UnknownStrategy", "initial_cash": 1_000_000},
    }
    with pytest.raises(StrategyKitsError):
        validate_strategy_task_spec(spec)


def test_validate_strategy_task_spec_rejects_bad_ranges():
    spec = {
        "task": {"task_id": "t1", "strategy_name": "demo"},
        "data": {
            "panel_type": "local_features",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        },
        "backtest": {
            "template": "WeightedTopNStrategy",
            "initial_cash": 1_000_000,
            "rebalance_threshold": 1.2,
        },
    }
    with pytest.raises(StrategyKitsError):
        validate_strategy_task_spec(spec)
