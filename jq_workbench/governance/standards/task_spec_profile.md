# Task Spec Profile

## Purpose

A `task_spec` is a frozen, reproducible experiment input that drives strategy execution through `strategy_kits`. One task spec per experiment version, immutable after freeze.

The task spec is the execution contract derived from a `strategy_card`. It contains all runtime parameters needed by the local validation layer and JoinQuant submission.

## File Location

```
jq_workbench/research/task_specs/<strategy_id>__<version>.json
```

## Relation to strategy_kits

The task spec format is defined and validated by `strategy_kits/orchestration/task_schema.py`. The workbench standard adapts this format for JoinQuant-first R&D workflow.

Execution entry point:

```
strategy_kits/orchestration/cli.py --spec /path/to/task_spec.json
```

## Schema

```json
{
  "task": {
    "task_id": "string",
    "strategy_name": "string",
    "mode": "string?"
  },
  "data": {
    "panel_type": "enum",
    "panel_path": "string?",
    "prediction_path": "string?",
    "start_date": "date",
    "end_date": "date"
  },
  "pipeline": {
    "top_n": "int",
    "score_method": "string",
    "weight_mode": "enum"
  },
  "portfolio": {
    "max_positions": "int",
    "max_single": "float",
    "cash_target": "float"
  },
  "backtest": {
    "template": "enum",
    "initial_cash": "float",
    "benchmark": "string?",
    "rebalance_threshold": "float",
    "hold_days": "int",
    "printlog": "bool?",
    "tradehistory": "bool?"
  },
  "risk": {
    "enable_constraints": "bool",
    "max_industry": "float",
    "max_turnover": "float"
  },
  "output": {
    "save_artifacts": "bool",
    "artifact_dir": "string?"
  }
}
```

## Required Fields

| Section | Field | Type | Notes |
|---------|-------|------|-------|
| `task` | `task_id` | string | Unique identifier for this run |
| `task` | `strategy_name` | string | Human-readable strategy name |
| `data` | `panel_type` | enum | `pool_panel` \| `score_panel` \| `local_features` |
| `data` | `start_date` | date | Backtest start, YYYY-MM-DD |
| `data` | `end_date` | date | Backtest end, YYYY-MM-DD |
| `backtest` | `template` | enum | `WeightedTopNStrategy` \| `EqualWeightStrategy` \| `DirectExecutionStrategy` |
| `backtest` | `initial_cash` | float | Must be positive |

## Conditional Required Fields

| Condition | Section | Field | Type |
|-----------|---------|-------|------|
| `panel_type = pool_panel` | `data` | `panel_path` | string |
| `panel_type = score_panel` | `data` | `panel_path` | string |
| `panel_type = local_features` | `data` | `prediction_path` | string |

## Optional Fields with Defaults

Defaults are applied by `validate_strategy_task_spec()`:

| Section | Field | Default | Constraint | Source |
|---------|-------|---------|------------|--------|
| `task` | `mode` | `"single_strategy_research"` | not validated by task_schema | artifact_contracts.py:131 |
| `pipeline` | `top_n` | 20 | positive int | task_schema.py:120 |
| `pipeline` | `score_method` | `"equal"` | not validated by task_schema | task_schema.py:121 |
| `pipeline` | `weight_mode` | `"score"` | `"equal"` \| `"score"` | task_schema.py:122 |
| `portfolio` | `max_positions` | max(20, top_n) | positive int | task_schema.py:131 |
| `portfolio` | `max_single` | 0.1 | [0.0, 1.0] | task_schema.py:132 |
| `portfolio` | `cash_target` | 0.05 | [0.0, 1.0] | task_schema.py:133 |
| `backtest` | `rebalance_threshold` | 0.01 | [0.0, 1.0) | task_schema.py:138 |
| `backtest` | `hold_days` | 1 | positive int | task_schema.py:139 |
| `backtest` | `benchmark` | None | not validated by task_schema | task_runner.py:126 |
| `backtest` | `printlog` | false | bool | task_runner.py:127 |
| `backtest` | `tradehistory` | false | bool | task_runner.py:128 |
| `risk` | `enable_constraints` | true | bool | task_schema.py:143 |
| `risk` | `max_industry` | 0.3 | [0.0, 1.0] | task_schema.py:150 |
| `risk` | `max_turnover` | 0.4 | [0.0, 1.0] | task_schema.py:151 |
| `output` | `save_artifacts` | true | bool | task_schema.py:155 |
| `output` | `artifact_dir` | `"./artifacts"` | string, if save_artifacts=true | task_schema.py:163 |

## Validation Rules

The following validation is enforced by `strategy_kits`:

1. `start_date` must be earlier than `end_date`
2. `initial_cash` must be positive
3. `top_n`, `max_positions`, `hold_days` must be positive integers
4. `max_single`, `cash_target`, `max_industry`, `max_turnover`, `rebalance_threshold` must be valid floats in specified ranges
5. `panel_type` must be one of the three allowed values
6. `template` must be one of the three allowed values
7. `weight_mode` must be `"equal"` or `"score"`

## Versioning Rules

1. Version format: `v1.0`, `v1.1`, `v1.2` (semver-style)
2. Increment version on any parameter change that affects reproducibility
3. File naming: `<strategy_id>__<version>.json`
4. Once frozen, a task spec should not be modified; create a new version instead
5. Version history should be documented in the associated `strategy_card` changelog

## Mapping: strategy_card to task_spec

| strategy_card Field | task_spec Field | Notes |
|---------------------|-----------------|-------|
| `meta.strategy_id` | `task.task_id` (prefix) | Combine with version for unique task_id |
| `meta.version` | File name suffix | `<strategy_id>__<version>.json` |
| `meta.strategy_id` | `task.strategy_name` | Human-readable name |
| `universe.base_pool` | Not directly mapped | Used to generate `pool_panel` or `score_panel` |
| `universe.filters` | Not directly mapped | Applied during panel generation |
| `rebalance.top_n` | `pipeline.top_n` | Direct mapping |
| `rebalance.weight_method` | `pipeline.weight_mode` | `equal` -> `"equal"`; `rank_weight` -> `"score"`; others -> Unconfirmed |
| `rebalance.frequency` | `backtest.hold_days` | Daily=1, Weekly=5, Monthly=20 (approximate) |
| `risk.position_rules.max_position_pct` | `portfolio.max_single` | Direct mapping |
| `risk.position_rules.min_cash_pct` | `portfolio.cash_target` | Direct mapping |
| `risk.position_rules.max_sector_pct` | `risk.max_industry` | Direct mapping |
| `performance_targets.turnover` | `risk.max_turnover` | Approximate mapping, may need adjustment |
| `thesis.time_horizon` | `backtest.hold_days` | Intraday -> 1; Daily -> 1; Weekly -> 5; Monthly -> 20 |
| `signals.composite_method` | `pipeline.score_method` | Unconfirmed, may need custom preprocessing |
| `risk.regime_filter` | Not directly mapped | Applied at signal/prediction layer before task_spec |
| `market_regime` | Not directly mapped | Used for validation slices, not task_spec parameters |
| `failure_modes` | Not directly mapped | Used for diagnostic checks after run |
| `dependencies` | `data.panel_type` | Determines how data is loaded |

### Fields Not in task_spec

The following strategy_card fields are handled outside the task_spec execution contract:

| strategy_card Field | Handling Layer |
|---------------------|----------------|
| `thesis` | Knowledge layer (documentation only) |
| `signals.factors` | Panel generation layer (`research/panels/`) |
| `market_regime` | Validation slices (`validation/regime_slices/`) |
| `failure_modes` | Post-run diagnostics |
| `validation` | Governance layer (run archive) |
| `changelog` | Governance layer (iteration registry) |

## Example task_spec

```json
{
  "task": {
    "task_id": "value_quality_momentum__v1.0__run001",
    "strategy_name": "value_quality_momentum",
    "mode": "single_strategy_research"
  },
  "data": {
    "panel_type": "score_panel",
    "panel_path": "/path/to/research/panels/value_quality_momentum__v1.0.csv",
    "start_date": "2020-01-01",
    "end_date": "2024-12-31"
  },
  "pipeline": {
    "top_n": 30,
    "score_method": "weighted_sum",
    "weight_mode": "score"
  },
  "portfolio": {
    "max_positions": 30,
    "max_single": 0.08,
    "cash_target": 0.05
  },
  "backtest": {
    "template": "WeightedTopNStrategy",
    "initial_cash": 1000000,
    "benchmark": "000300.XSHG",
    "rebalance_threshold": 0.02,
    "hold_days": 5
  },
  "risk": {
    "enable_constraints": true,
    "max_industry": 0.25,
    "max_turnover": 0.3
  },
  "output": {
    "save_artifacts": true,
    "artifact_dir": "./artifacts/value_quality_momentum"
  }
}
```

## Execution Contract

When a task_spec is executed through `strategy_kits`, the following artifacts are produced:

| Artifact | Path in output directory |
|----------|--------------------------|
| `task_spec.json` | Frozen copy of input spec |
| `prediction_frame.csv` | Normalized prediction input |
| `nav_series.csv` | Net asset value history |
| `metrics.csv` | Performance metrics |
| `trades.csv` | Trade log |
| `analyzers.json` | Analyzer output |
| `summary.json` | Run summary contract |
| `run_report.json` | Full run report payload |
| `run_report.md` | Markdown report |

Output directory structure:

```
./artifacts/<task_id>/<YYYYMMDD_HHMMSS>/
```

## Integration Points

1. **Panel generation**: `strategy_card.universe` + `strategy_card.signals` -> `pool_panel` or `score_panel` -> `data.panel_path`
2. **Local validation**: `task_spec.json` -> `strategy_kits` -> artifacts
3. **JoinQuant submission**: `task_spec` + `jq_strategy.py` -> platform run
4. **Diff comparison**: local artifacts vs platform run archive

## Change Discipline

Per operating model, each iteration should change only one of:

1. `pipeline.top_n` or `pipeline.weight_mode`
2. `data.start_date` / `end_date` (different validation slice)
3. `portfolio` constraints
4. `risk` parameters
5. `backtest.template`

Changes to `data.panel_path` indicate a new panel version, which should be a separate iteration with updated `strategy_card` signals.

## Quality Gate

Before using a task_spec for JoinQuant submission:

- [ ] Schema valid per `validate_strategy_task_spec()`
- [ ] All required fields present
- [ ] Panel file exists and matches `data.panel_path`
- [ ] `task_id` follows naming convention
- [ ] Associated `strategy_card` exists with matching version
- [ ] Local run completed with artifacts persisted
- [ ] Run report shows no contract errors