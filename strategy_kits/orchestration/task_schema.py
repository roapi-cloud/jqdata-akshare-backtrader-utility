from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from ..core.errors import ErrorCode, StrategyKitsError


def _require_dict(spec: Mapping[str, Any], key: str) -> dict[str, Any]:
    val = spec.get(key)
    if not isinstance(val, Mapping):
        raise StrategyKitsError(
            ErrorCode.CONTRACT_MISSING_COLUMN,
            f"task spec missing object field: {key}",
        )
    return dict(val)


def _require_str(spec: Mapping[str, Any], key: str, ctx: str) -> str:
    val = spec.get(key)
    if not isinstance(val, str) or not val.strip():
        raise StrategyKitsError(
            ErrorCode.CONTRACT_MISSING_COLUMN,
            f"{ctx} missing required string field: {key}",
        )
    return val.strip()


def _require_positive_int(spec: Mapping[str, Any], key: str, ctx: str) -> int:
    val = spec.get(key)
    if not isinstance(val, int) or val <= 0:
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            f"{ctx}.{key} must be positive integer",
            details={"value": val},
        )
    return val


def _require_float_in(spec: Mapping[str, Any], key: str, ctx: str, low: float, high: float, inclusive_high: bool = True) -> float:
    val = spec.get(key)
    if isinstance(val, int):
        val = float(val)
    if not isinstance(val, float):
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            f"{ctx}.{key} must be float",
            details={"value": val},
        )
    ok = low <= val <= high if inclusive_high else low <= val < high
    if not ok:
        br = "]" if inclusive_high else ")"
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            f"{ctx}.{key} must be in range [{low}, {high}{br}",
            details={"value": val},
        )
    return val


def validate_strategy_task_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        raise StrategyKitsError(ErrorCode.CONTRACT_INVALID_VALUE, "spec must be a mapping")

    task = _require_dict(spec, "task")
    data = _require_dict(spec, "data")
    backtest = _require_dict(spec, "backtest")
    pipeline = dict(spec.get("pipeline", {}))
    portfolio = dict(spec.get("portfolio", {}))
    risk = dict(spec.get("risk", {}))
    output = dict(spec.get("output", {}))

    _require_str(task, "task_id", "task")
    _require_str(task, "strategy_name", "task")

    panel_type = _require_str(data, "panel_type", "data")
    if panel_type not in {"pool_panel", "score_panel", "local_features"}:
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "data.panel_type must be one of pool_panel/score_panel/local_features",
            details={"panel_type": panel_type},
        )

    if panel_type in {"pool_panel", "score_panel"} and not isinstance(data.get("panel_path"), str):
        raise StrategyKitsError(
            ErrorCode.CONTRACT_MISSING_COLUMN,
            "data.panel_path is required when panel_type is pool_panel/score_panel",
        )

    start_date = pd.to_datetime(_require_str(data, "start_date", "data"), errors="coerce")
    end_date = pd.to_datetime(_require_str(data, "end_date", "data"), errors="coerce")
    if pd.isna(start_date) or pd.isna(end_date):
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "data.start_date/data.end_date must be parseable dates",
        )
    if start_date > end_date:
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "data.start_date must be earlier than data.end_date",
            details={"start_date": str(start_date), "end_date": str(end_date)},
        )

    _require_str(backtest, "template", "backtest")
    if backtest["template"] not in {"WeightedTopNStrategy", "EqualWeightStrategy", "DirectExecutionStrategy"}:
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "backtest.template must be one of WeightedTopNStrategy/EqualWeightStrategy/DirectExecutionStrategy",
            details={"template": backtest["template"]},
        )
    backtest["initial_cash"] = float(backtest.get("initial_cash", 0.0))
    if backtest["initial_cash"] <= 0:
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "backtest.initial_cash must be positive",
            details={"initial_cash": backtest["initial_cash"]},
        )

    pipeline.setdefault("top_n", 20)
    pipeline.setdefault("score_method", "equal")
    pipeline.setdefault("weight_mode", "score")
    _require_positive_int(pipeline, "top_n", "pipeline")
    if pipeline["weight_mode"] not in {"equal", "score"}:
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "pipeline.weight_mode must be equal or score",
            details={"weight_mode": pipeline["weight_mode"]},
        )

    portfolio.setdefault("max_positions", max(20, pipeline["top_n"]))
    portfolio.setdefault("max_single", 0.1)
    portfolio.setdefault("cash_target", 0.05)
    _require_positive_int(portfolio, "max_positions", "portfolio")
    _require_float_in(portfolio, "max_single", "portfolio", 0.0, 1.0, inclusive_high=True)
    _require_float_in(portfolio, "cash_target", "portfolio", 0.0, 1.0, inclusive_high=True)

    backtest.setdefault("rebalance_threshold", 0.01)
    backtest.setdefault("hold_days", 1)
    _require_float_in(backtest, "rebalance_threshold", "backtest", 0.0, 1.0, inclusive_high=False)
    _require_positive_int(backtest, "hold_days", "backtest")

    risk.setdefault("enable_constraints", True)
    if not isinstance(risk["enable_constraints"], bool):
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "risk.enable_constraints must be bool",
            details={"value": risk["enable_constraints"]},
        )
    risk.setdefault("max_industry", 0.3)
    risk.setdefault("max_turnover", 0.4)
    _require_float_in(risk, "max_industry", "risk", 0.0, 1.0, inclusive_high=True)
    _require_float_in(risk, "max_turnover", "risk", 0.0, 1.0, inclusive_high=True)

    output.setdefault("save_artifacts", True)
    if not isinstance(output["save_artifacts"], bool):
        raise StrategyKitsError(
            ErrorCode.CONTRACT_INVALID_VALUE,
            "output.save_artifacts must be bool",
            details={"value": output["save_artifacts"]},
        )
    if output["save_artifacts"]:
        output.setdefault("artifact_dir", "./artifacts")

    data["start_date"] = str(start_date.date())
    data["end_date"] = str(end_date.date())

    return {
        "task": task,
        "data": data,
        "pipeline": pipeline,
        "portfolio": portfolio,
        "backtest": backtest,
        "risk": risk,
        "output": output,
    }