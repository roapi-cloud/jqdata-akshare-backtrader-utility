from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..core import get_logger, log_kv
from ..core.errors import ErrorCode, StrategyKitsError
from .artifact_contracts import (
    ARTIFACT_SCHEMA_VERSION,
    build_run_report_payload,
    render_run_report_markdown,
    validate_artifact_manifest,
    validate_artifact_summary,
)

_logger = get_logger("orchestration.artifacts")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def _ensure_df(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, pd.Series):
        return value.to_frame(name=value.name or "value")
    if value is None:
        return pd.DataFrame()
    if isinstance(value, list):
        return pd.DataFrame(value)
    return pd.DataFrame({"value": [value]})


def persist_task_artifacts(
    result: Mapping[str, Any],
    spec: Mapping[str, Any],
    artifact_dir: str | Path,
) -> dict[str, str]:
    task = dict(spec.get("task", {}))
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = str(task.get("task_id", "task"))

    root = Path(artifact_dir).expanduser().resolve()
    out_dir = root / task_id / run_id
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise StrategyKitsError(
            ErrorCode.ARTIFACT_WRITE_FAILED,
            "failed to create artifact output directory",
            details={"artifact_dir": str(out_dir)},
        ) from exc

    manifest: dict[str, str] = {}

    task_spec_path = out_dir / "task_spec.json"
    task_spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    manifest["task_spec"] = str(task_spec_path)

    pred_df = _ensure_df(result.get("pred_df"))
    pred_path = out_dir / "prediction_frame.csv"
    pred_df.to_csv(pred_path, index=False)
    manifest["prediction_frame"] = str(pred_path)

    nav_df = _ensure_df(result.get("nav_series"))
    nav_path = out_dir / "nav_series.csv"
    nav_df.to_csv(nav_path, index=False)
    manifest["nav_series"] = str(nav_path)

    metrics_df = _ensure_df(result.get("metrics"))
    metrics_path = out_dir / "metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    manifest["metrics"] = str(metrics_path)

    trades_df = _ensure_df(result.get("trades"))
    trades_path = out_dir / "trades.csv"
    trades_df.to_csv(trades_path, index=False)
    manifest["trades"] = str(trades_path)

    analyzers_path = out_dir / "analyzers.json"
    analyzers_path.write_text(
        json.dumps(result.get("analyzers", {}), ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    manifest["analyzers"] = str(analyzers_path)

    summary = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "task_id": task_id,
        "strategy_name": task.get("strategy_name"),
        "portfolio_value": float(result.get("portfolio_value", 0.0)),
        "start_date": spec.get("data", {}).get("start_date"),
        "end_date": spec.get("data", {}).get("end_date"),
        "template": spec.get("backtest", {}).get("template"),
        "rows": {
            "prediction_frame": len(pred_df),
            "nav_series": len(nav_df),
            "metrics": len(metrics_df),
            "trades": len(trades_df),
        },
        "generated_at": datetime.now().isoformat(),
    }
    summary = validate_artifact_summary(summary)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    manifest["summary"] = str(summary_path)

    run_report = build_run_report_payload(summary=summary, spec=spec, result=result)
    run_report_json_path = out_dir / "run_report.json"
    run_report_json_path.write_text(
        json.dumps(run_report, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    manifest["run_report_json"] = str(run_report_json_path)

    run_report_md_path = out_dir / "run_report.md"
    run_report_md_path.write_text(
        render_run_report_markdown(run_report),
        encoding="utf-8",
    )
    manifest["run_report_md"] = str(run_report_md_path)

    manifest["artifact_dir"] = str(out_dir)
    manifest = validate_artifact_manifest(manifest)

    log_kv(
        _logger,
        20,
        "task_artifacts_persisted",
        task_id=task_id,
        out_dir=str(out_dir),
        files=len(manifest),
    )
    return manifest