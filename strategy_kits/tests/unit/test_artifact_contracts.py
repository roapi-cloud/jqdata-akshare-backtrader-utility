from __future__ import annotations

import pytest

from strategy_kits.core.errors import StrategyKitsError
from strategy_kits.orchestration.artifact_contracts import (
    build_run_report_payload,
    render_run_report_markdown,
    validate_artifact_manifest,
    validate_artifact_summary,
)


def test_validate_artifact_summary_and_manifest():
    summary = {
        "artifact_schema_version": "v1.0",
        "task_id": "t1",
        "strategy_name": "demo",
        "template": "WeightedTopNStrategy",
        "start_date": "2024-01-01",
        "end_date": "2024-01-10",
        "portfolio_value": 123.4,
        "rows": {"prediction_frame": 10, "nav_series": 9, "metrics": 1, "trades": 3},
        "generated_at": "2026-04-03T12:00:00",
    }
    manifest = {
        "artifact_dir": "/tmp/a",
        "task_spec": "/tmp/a/task_spec.json",
        "prediction_frame": "/tmp/a/prediction_frame.csv",
        "nav_series": "/tmp/a/nav_series.csv",
        "metrics": "/tmp/a/metrics.csv",
        "trades": "/tmp/a/trades.csv",
        "analyzers": "/tmp/a/analyzers.json",
        "summary": "/tmp/a/summary.json",
        "run_report_json": "/tmp/a/run_report.json",
        "run_report_md": "/tmp/a/run_report.md",
    }
    validate_artifact_summary(summary)
    validate_artifact_manifest(manifest)


def test_validate_artifact_manifest_missing_field():
    with pytest.raises(StrategyKitsError):
        validate_artifact_manifest({"artifact_dir": "/tmp/a"})


def test_build_and_render_run_report():
    summary = {
        "artifact_schema_version": "v1.0",
        "task_id": "t1",
        "strategy_name": "demo",
        "template": "WeightedTopNStrategy",
        "start_date": "2024-01-01",
        "end_date": "2024-01-10",
        "portfolio_value": 123.4,
        "rows": {"prediction_frame": 10, "nav_series": 9, "metrics": 1, "trades": 3},
        "generated_at": "2026-04-03T12:00:00",
    }
    spec = {"task": {"mode": "single_strategy_research"}}
    result = {"metrics": {"annual_return": 0.12}, "trades": [{"a": 1}]}
    payload = build_run_report_payload(summary=summary, spec=spec, result=result)
    md = render_run_report_markdown(payload)
    assert payload["task_id"] == "t1"
    assert "Strategy Task Run Report" in md

