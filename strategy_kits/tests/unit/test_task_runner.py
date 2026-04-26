from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

bt = pytest.importorskip("backtrader")

from strategy_kits.orchestration import run_strategy_task


def _make_feed(name: str, start: str = "2024-01-01", periods: int = 8) -> bt.feeds.PandasData:
    dates = pd.date_range(start=start, periods=periods, freq="D")
    base = 10.0 + hash(name) % 7
    df = pd.DataFrame(
        {
            "datetime": dates,
            "open": [base + i * 0.1 for i in range(periods)],
            "high": [base + i * 0.1 + 0.2 for i in range(periods)],
            "low": [base + i * 0.1 - 0.2 for i in range(periods)],
            "close": [base + i * 0.1 + 0.05 for i in range(periods)],
            "volume": [100000 + i * 100 for i in range(periods)],
            "openinterest": [0 for _ in range(periods)],
        }
    )
    return bt.feeds.PandasData(
        dataname=df,
        datetime="datetime",
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest="openinterest",
        name=name,
    )


def test_run_strategy_task_pool_panel_with_data_bundle(tmp_path):
    pool = pd.DataFrame(
        {
            "date": ["2024-01-04", "2024-01-05", "2024-01-05"],
            "code": ["000001", "000001", "000002"],
            "score": [0.2, 0.6, 0.4],
            "rank": [1, 1, 2],
        }
    )
    pool_path = tmp_path / "pool_panel.csv"
    pool.to_csv(pool_path, index=False)

    spec = {
        "task": {"task_id": "demo_task_1", "strategy_name": "demo_pool"},
        "data": {
            "panel_type": "pool_panel",
            "panel_path": str(pool_path),
            "start_date": "2024-01-01",
            "end_date": "2024-01-10",
        },
        "pipeline": {"top_n": 1, "weight_mode": "equal"},
        "backtest": {
            "template": "WeightedTopNStrategy",
            "initial_cash": 1_000_000,
            "rebalance_threshold": 0.0,
            "hold_days": 1,
        },
        "output": {"save_artifacts": False},
    }

    data_bundle = {"sz000001": _make_feed("sz000001"), "sz000002": _make_feed("sz000002")}
    result = run_strategy_task(spec, data_bundle=data_bundle)

    assert result["portfolio_value"] > 0
    pred_df = result["pred_df"]
    assert set(pred_df.columns) >= {"date", "code", "weight"}
    assert pred_df["code"].str.len().eq(6).all()


def test_run_strategy_task_persists_artifacts(tmp_path):
    pool = pd.DataFrame(
        {
            "date": ["2024-01-05", "2024-01-05"],
            "code": ["000001", "000002"],
            "score": [0.6, 0.4],
            "rank": [1, 2],
        }
    )
    pool_path = tmp_path / "pool_panel.csv"
    pool.to_csv(pool_path, index=False)

    spec = {
        "task": {"task_id": "demo_task_artifacts", "strategy_name": "demo_pool"},
        "data": {
            "panel_type": "pool_panel",
            "panel_path": str(pool_path),
            "start_date": "2024-01-01",
            "end_date": "2024-01-10",
        },
        "pipeline": {"top_n": 1, "weight_mode": "equal"},
        "backtest": {
            "template": "WeightedTopNStrategy",
            "initial_cash": 1_000_000,
            "rebalance_threshold": 0.0,
            "hold_days": 1,
        },
        "output": {"save_artifacts": True, "artifact_dir": str(tmp_path / "artifacts")},
    }

    data_bundle = {"sz000001": _make_feed("sz000001"), "sz000002": _make_feed("sz000002")}
    result = run_strategy_task(spec, data_bundle=data_bundle)
    manifest = result.get("artifact_manifest")
    assert isinstance(manifest, dict)
    assert "artifact_dir" in manifest
    assert (tmp_path / "artifacts").exists()
    assert (Path(manifest["summary"])).exists()
    assert (Path(manifest["run_report_json"])).exists()
    assert (Path(manifest["run_report_md"])).exists()

    summary = json.loads(Path(manifest["summary"]).read_text(encoding="utf-8"))
    assert summary["artifact_schema_version"] == "v1.0"
    run_report_md = Path(manifest["run_report_md"]).read_text(encoding="utf-8")
    assert "Strategy Task Run Report" in run_report_md
