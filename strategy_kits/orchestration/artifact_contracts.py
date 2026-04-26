"""Frozen contracts for strategy task artifacts and reports."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..core.errors import ErrorCode, StrategyKitsError

ARTIFACT_SCHEMA_VERSION = "v1.0"

SUMMARY_REQUIRED_KEYS = (
    "artifact_schema_version",
    "task_id",
    "strategy_name",
    "template",
    "start_date",
    "end_date",
    "portfolio_value",
    "rows",
    "generated_at",
)

MANIFEST_REQUIRED_KEYS = (
    "artifact_dir",
    "task_spec",
    "prediction_frame",
    "nav_series",
    "metrics",
    "trades",
    "analyzers",
    "summary",
    "run_report_json",
    "run_report_md",
)


def _require_keys(payload: Mapping[str, Any], keys: tuple[str, ...], ctx: str) -> None:
    missing = [k for k in keys if k not in payload]
    if missing:
        raise StrategyKitsError(
            ErrorCode.ARTIFACT_CONTRACT_INVALID,
            f"{ctx} missing required keys: {missing}",
            details={"required": list(keys), "payload_keys": list(payload.keys())},
        )


def validate_artifact_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Validate frozen artifact summary contract."""
    _require_keys(summary, SUMMARY_REQUIRED_KEYS, "artifact_summary")

    rows = summary.get("rows")
    if not isinstance(rows, Mapping):
        raise StrategyKitsError(
            ErrorCode.ARTIFACT_CONTRACT_INVALID,
            "artifact_summary.rows must be an object",
            details={"rows_type": type(rows).__name__},
        )

    # Parse generated timestamp for minimal sanity check.
    generated_at = summary.get("generated_at")
    try:
        datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
    except Exception as exc:
        raise StrategyKitsError(
            ErrorCode.ARTIFACT_CONTRACT_INVALID,
            "artifact_summary.generated_at must be ISO datetime",
            details={"generated_at": generated_at},
        ) from exc

    return dict(summary)


def validate_artifact_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate frozen artifact manifest contract."""
    _require_keys(manifest, MANIFEST_REQUIRED_KEYS, "artifact_manifest")
    return dict(manifest)


def _metrics_snapshot(metrics_obj: Any) -> dict[str, float]:
    if isinstance(metrics_obj, pd.DataFrame):
        if metrics_obj.empty:
            return {}
        row = metrics_obj.iloc[0]
    elif isinstance(metrics_obj, Mapping):
        row = pd.Series(metrics_obj)
    else:
        return {}

    snap: dict[str, float] = {}
    for key, value in row.items():
        if isinstance(value, (int, float, np.integer, np.floating)) and not pd.isna(value):
            snap[str(key)] = float(value)
    return snap


def _trade_count(trades_obj: Any) -> int:
    if isinstance(trades_obj, pd.DataFrame):
        return int(len(trades_obj))
    if isinstance(trades_obj, list):
        return int(len(trades_obj))
    return 0


def build_run_report_payload(
    *,
    summary: Mapping[str, Any],
    spec: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Build frozen JSON payload for one run report."""
    validated_summary = validate_artifact_summary(summary)
    metrics = _metrics_snapshot(result.get("metrics"))
    payload = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "task_id": validated_summary["task_id"],
        "strategy_name": validated_summary.get("strategy_name"),
        "template": validated_summary.get("template"),
        "period": {
            "start_date": validated_summary.get("start_date"),
            "end_date": validated_summary.get("end_date"),
        },
        "portfolio_value": float(validated_summary.get("portfolio_value", 0.0)),
        "rows": dict(validated_summary.get("rows", {})),
        "metrics_snapshot": metrics,
        "trade_count": _trade_count(result.get("trades")),
        "generated_at": validated_summary["generated_at"],
        "task_meta": {
            "task_mode": spec.get("task", {}).get("mode", "single_strategy_research"),
        },
    }
    return payload


def render_run_report_markdown(report: Mapping[str, Any]) -> str:
    """Render one-file markdown report from run report payload."""
    metrics = report.get("metrics_snapshot", {})
    metric_lines = []
    for k in sorted(metrics.keys())[:8]:
        metric_lines.append(f"- `{k}`: {metrics[k]:.6f}")
    if not metric_lines:
        metric_lines.append("- (no numeric metrics)")

    lines = [
        "# Strategy Task Run Report",
        "",
        f"- `task_id`: {report.get('task_id')}",
        f"- `strategy_name`: {report.get('strategy_name')}",
        f"- `template`: {report.get('template')}",
        f"- `period`: {report.get('period', {}).get('start_date')} -> {report.get('period', {}).get('end_date')}",
        f"- `portfolio_value`: {float(report.get('portfolio_value', 0.0)):.4f}",
        f"- `trade_count`: {int(report.get('trade_count', 0))}",
        f"- `generated_at`: {report.get('generated_at')}",
        "",
        "## Metrics Snapshot",
        *metric_lines,
        "",
        "## Rows",
    ]
    for key, value in dict(report.get("rows", {})).items():
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    lines.append(f"- `artifact_schema_version`: {report.get('artifact_schema_version')}")
    return "\n".join(lines) + "\n"

