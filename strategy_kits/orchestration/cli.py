from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..core.errors import ErrorCode, StrategyKitsError


def load_task_spec(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    suffix = file_path.suffix.lower()

    if suffix == ".json":
        return json.loads(file_path.read_text(encoding="utf-8"))

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise StrategyKitsError(
                ErrorCode.CONTRACT_INVALID_VALUE,
                "PyYAML is required to load yaml task spec. Use JSON or install pyyaml.",
            ) from exc
        loaded = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise StrategyKitsError(
                ErrorCode.CONTRACT_INVALID_VALUE,
                "YAML task spec must be a mapping object",
                details={"path": str(file_path)},
            )
        return loaded

    raise StrategyKitsError(
        ErrorCode.CONTRACT_INVALID_VALUE,
        f"Unsupported task spec file suffix: {suffix}",
        details={"path": str(file_path)},
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run strategy_kits task spec.")
    parser.add_argument("--spec", required=True, help="Path to task spec JSON/YAML file.")
    parser.add_argument("--no-save-artifacts", action="store_true", help="Disable artifact persistence for this run.")
    parser.add_argument("--print-result-json", action="store_true", help="Print compact run summary as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    from .task_runner import run_strategy_task

    spec = load_task_spec(args.spec)

    result = run_strategy_task(
        spec,
        persist_artifacts=not args.no_save_artifacts,
    )

    if args.print_result_json:
        payload = {
            "engine": "local",
            "portfolio_value": float(result.get("portfolio_value", 0.0)),
            "artifact_dir": result.get("artifact_manifest", {}).get("artifact_dir") if isinstance(result.get("artifact_manifest"), dict) else None,
            "run_report_md": result.get("artifact_manifest", {}).get("run_report_md") if isinstance(result.get("artifact_manifest"), dict) else None,
            "task_id": result.get("task_spec", {}).get("task", {}).get("task_id"),
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"portfolio_value={float(result.get('portfolio_value', 0.0)):.2f}")
        if isinstance(result.get("artifact_manifest"), dict):
            print(f"artifact_dir={result['artifact_manifest'].get('artifact_dir')}")
            print(f"run_report_md={result['artifact_manifest'].get('run_report_md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())