# JoinQuant Executor

## Purpose

The `jq_executor` is the JoinQuant platform submission and result management layer. It bridges frozen task specs and JoinQuant strategy files, enabling authoritative platform validation.

## Core Responsibilities

| Responsibility | Description |
|----------------|-------------|
| Strategy Generation | Transform frozen `task_spec` into a JoinQuant-compatible strategy script |
| Script Validation | Ensure generated scripts match task spec contract and JoinQuant API requirements |
| Platform Submission | Submit strategy files to JoinQuant with correct parameters |
| Result Fetching | Pull metrics, trades, NAV, and run metadata from JoinQuant |
| Output Normalization | Convert platform outputs into the archive contract format |

## Non-Responsibilities

- Building a generic local backtest engine (handled by `strategy_kits`)
- Replacing JoinQuant as the authoritative validation platform
- Managing factor assets or factor scoring (handled by `FactorHub` if present)
- Strategy iteration governance (handled by `governance/iteration_registry`)

## Input Contract

The executor consumes:

| Input | Source | Format |
|-------|--------|--------|
| `task_spec.json` | `research/task_specs/` | Frozen JSON |
| `jq_strategy.py` | `research/jq_strategies/` | JoinQuant script |
| `pool_panel.csv` or `score_panel.csv` | `research/panels/` | Precomputed panel |

Reference: `jq_workbench/governance/standards/task_spec_profile.md`

## Output Contract

The executor produces artifacts for `run_archive/`:

| Artifact | Required | Description |
|----------|----------|-------------|
| `metrics.json` | yes | Normalized performance metrics (nested schema) |
| `trades.csv` | yes | Trade log with timestamps |
| `nav.csv` | yes | Net asset value time series |
| `positions.csv` | no | Position snapshots |
| `platform_meta.json` | yes | JoinQuant run metadata |
| `run_report.md` | yes | Human-readable summary |

Reference: `jq_workbench/platform/run_archive/README.md`

## Execution Lifecycle

See `jq_workbench/docs/jq_execution_flow.md` for detailed step-by-step lifecycle.

## Directory Structure

```text
jq_workbench/platform/jq_executor/
  templates/           # JoinQuant strategy templates
  generators/          # Script generation logic
  submitter/           # Platform submission client
  fetcher/             # Result fetching logic
  normalizer/          # Output normalization
  README.md
```

## Integration Points

### Upstream

| Layer | Component | Contract |
|-------|-----------|----------|
| Research | `task_specs/` | Frozen experiment spec |
| Research | `jq_strategies/` | JoinQuant strategy script |
| Research | `panels/` | Precomputed selection/score data |
| Strategy Kits | `orchestration/` | Local artifact contract |

### Downstream

| Layer | Component | Purpose |
|-------|-----------|---------|
| Run Archive | `run_archive/` | Store normalized platform outputs |
| Diff Reports | `diff_reports/` | Compare local vs platform results |
| Governance | `iteration_registry/` | Record validation outcomes |

## Key Parameters

| Parameter | Source | Notes |
|-----------|--------|-------|
| `algorithm_id` | JoinQuant platform | Unique identifier for submitted strategy |
| `start_date` | `task_spec.data.start_date` | Backtest start |
| `end_date` | `task_spec.data.end_date` | Backtest end |
| `initial_cash` | `task_spec.backtest.initial_cash` | Starting capital |
| `benchmark` | `task_spec.backtest.benchmark` | Benchmark index |
| `frequency` | Derived from `task_spec.backtest.hold_days` | Rebalance frequency |

## Quality Gate

Before submission, ensure:

- [ ] `task_spec.json` schema valid
- [ ] `jq_strategy.py` exists and matches task spec
- [ ] Panel file exists at specified path
- [ ] Local `strategy_kits` run completed (smoke check)
- [ ] No contract errors in local artifacts

After fetch, ensure:

- [ ] 5 required files produced (metrics, trades, nav, platform_meta, run_report)
- [ ] `positions.csv` optionally produced
- [ ] `metrics.json` contains nested schema fields
- [ ] `trades.csv` has `symbol` column (not `code`)
- [ ] `nav.csv` has `position_value` column
- [ ] `platform_meta.json` includes `algorithm_id` or `backtest_id`
- [ ] Run date uses ISO format (`YYYY-MM-DD`)

## Error Codes

| Code | Description |
|------|-------------|
| `JQ_EXEC_001` | Task spec schema invalid |
| `JQ_EXEC_002` | Strategy script not found |
| `JQ_EXEC_003` | Panel file missing or empty |
| `JQ_EXEC_004` | Submission failed (network or auth) |
| `JQ_EXEC_005` | Fetch timeout or missing results |
| `JQ_EXEC_006` | Normalization contract violation |

## References

1. `ml_quant_framework/data/jqdata.py` - JQData API patterns
2. `strategy_kits/SKILL.md` - Local orchestration contract
3. `jq_workbench/docs/architecture.md` - Overall architecture
4. `jq_workbench/governance/standards/task_spec_profile.md` - Task spec schema