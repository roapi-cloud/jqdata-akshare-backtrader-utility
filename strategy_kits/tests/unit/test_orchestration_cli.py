from __future__ import annotations

import json

from strategy_kits.orchestration import cli
from strategy_kits.orchestration import task_runner


def test_load_task_spec_json(tmp_path):
    spec = {"task": {"task_id": "t1", "strategy_name": "demo"}}
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")

    loaded = cli.load_task_spec(path)
    assert loaded["task"]["task_id"] == "t1"


def test_cli_main_with_mocked_runner(tmp_path, monkeypatch, capsys):
    spec = {
        "task": {"task_id": "t1", "strategy_name": "demo"},
        "data": {"panel_type": "local_features", "start_date": "2024-01-01", "end_date": "2024-01-10"},
        "backtest": {"template": "WeightedTopNStrategy", "initial_cash": 1000000},
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")

    def _fake_run_strategy_task(raw_spec, persist_artifacts=None, data_bundle=None):
        return {
            "portfolio_value": 123456.7,
            "task_spec": {"task": {"task_id": raw_spec["task"]["task_id"]}},
            "artifact_manifest": {"artifact_dir": str(tmp_path / "artifacts")},
        }

    monkeypatch.setattr(task_runner, "run_strategy_task", _fake_run_strategy_task)
    rc = cli.main(["--spec", str(path), "--print-result-json", "--no-save-artifacts"])
    assert rc == 0

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["task_id"] == "t1"
    assert abs(payload["portfolio_value"] - 123456.7) < 1e-8

