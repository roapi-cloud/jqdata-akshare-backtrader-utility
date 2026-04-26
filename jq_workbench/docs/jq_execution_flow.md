# JoinQuant Execution Flow

## Overview

This document describes the step-by-step lifecycle for JoinQuant platform validation. The flow starts from a frozen task spec and ends with archived normalized outputs.

## Lifecycle Stages

```
Stage 1: Prepare    →  Stage 2: Generate   →  Stage 3: Submit
Stage 4: Wait       →  Stage 5: Fetch      →  Stage 6: Normalize
Stage 7: Archive    →  Stage 8: Report
```

---

## Stage 1: Prepare

**Purpose**: Validate inputs before generation.

### Steps

| Step | Action | Validation |
|------|--------|------------|
| 1.1 | Load `task_spec.json` from `research/task_specs/` | Schema valid per `task_spec_profile.md` |
| 1.2 | Check `jq_strategy.py` exists in `research/jq_strategies/` | File present, readable |
| 1.3 | Verify panel file exists at `task_spec.data.panel_path` | Non-empty CSV with required columns |
| 1.4 | Confirm local `strategy_kits` run completed | Artifacts in expected output directory |

### Required Fields from Task Spec

| Field | Usage |
|-------|-------|
| `task.task_id` | Unique run identifier |
| `data.start_date` | Backtest start |
| `data.end_date` | Backtest end |
| `backtest.initial_cash` | Starting capital |
| `backtest.benchmark` | Benchmark index (optional) |
| `backtest.hold_days` | Rebalance frequency |

### Exit Criteria

- All input files present and valid
- No `JQ_EXEC_001`, `JQ_EXEC_002`, `JQ_EXEC_003` errors

---

## Stage 2: Generate

**Purpose**: Transform task spec into JoinQuant-compatible strategy script.

### Steps

| Step | Action | Output |
|------|--------|--------|
| 2.1 | Read existing `jq_strategy.py` template or hand-written script | Strategy code |
| 2.2 | Inject parameters from task spec into strategy | Modified script |
| 2.3 | Validate JoinQuant API compatibility | No runtime import errors |
| 2.4 | Optionally embed panel data as in-script constant | Self-contained script |

### Generation Patterns

| Pattern | When Used | Notes |
|---------|-----------|-------|
| Template Injection | Standard strategies | Replace placeholders with task spec values |
| Panel Embedding | Small panels (<10K rows) | Embed CSV as Python dict |
| External Panel Reference | Large panels | Strategy loads panel at runtime |

### JoinQuant Script Structure

```python
def initialize(context):
    # Set parameters from task_spec
    set_params(...)

def handle_data(context, data):
    # Selection and rebalance logic
    ...

def after_trading_end(context):
    # Post-trade processing
    ...
```

### Exit Criteria

- Generated script syntactically valid
- All task spec parameters reflected in script
- Script follows JoinQuant API patterns from `jqdata.py`

---

## Stage 3: Submit

**Purpose**: Upload strategy to JoinQuant platform and trigger backtest.

### Steps

| Step | Action | Output |
|------|--------|--------|
| 3.1 | Authenticate with JoinQuant (if required) | Session established |
| 3.2 | Upload strategy file | `algorithm_id` returned |
| 3.3 | Configure backtest parameters | Run configuration stored |
| 3.4 | Trigger backtest execution | Run started |

### Submission Parameters

| Parameter | Source | JoinQuant Field |
|-----------|--------|-----------------|
| Start date | `task_spec.data.start_date` | `start` |
| End date | `task_spec.data.end_date` | `end` |
| Capital | `task_spec.backtest.initial_cash` | `capital_base` |
| Frequency | Derived from `hold_days` | `frequency` (`day`) |
| Benchmark | `task_spec.backtest.benchmark` | `benchmark` |

### Submission Methods

| Method | Notes |
|--------|-------|
| Web UI upload | Manual, for one-off tests |
| API submission | Automated, via JoinQuant SDK or internal scripts |
| Research environment | Direct execution in JoinQuant notebook |

### Exit Criteria

- `algorithm_id` obtained
- Backtest status: `running` or `completed`
- No `JQ_EXEC_004` error

---

## Stage 4: Wait

**Purpose**: Monitor backtest progress until completion.

### Steps

| Step | Action | Output |
|------|--------|--------|
| 4.1 | Poll backtest status | Status updates |
| 4.2 | Check for errors or timeouts | Error flags |
| 4.3 | Wait for completion signal | Final status |

### Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Queued, not started |
| `running` | Executing backtest |
| `completed` | Finished successfully |
| `failed` | Execution error |
| `timeout` | Exceeded time limit |

### Timeout Handling

- Default: 60 minutes for daily-frequency backtests
- On timeout: Retry once, then log `JQ_EXEC_005` error

### Exit Criteria

- Status: `completed`
- Results available for fetch

---

## Stage 5: Fetch

**Purpose**: Retrieve raw results from JoinQuant platform.

### Steps

| Step | Action | Output |
|------|--------|--------|
| 5.1 | Fetch performance metrics | Raw metrics JSON |
| 5.2 | Fetch trade log | Raw trades data |
| 5.3 | Fetch NAV history | Raw NAV data |
| 5.4 | Fetch run metadata | Algorithm info, timestamps |

### JoinQuant Result APIs

| API | Returns |
|-----|---------|
| `get_backtest_results()` | Performance summary |
| `get_backtest_trade_list()` | Trade records |
| `get_backtest_nav()` | NAV series |

### Raw Result Fields (Unnormalized)

| Field | JoinQuant Name | Notes |
|-------|----------------|-------|
| Annualized return | `annual_return` | Percentage |
| Max drawdown | `max_drawdown` | Percentage |
| Sharpe ratio | `sharpe` | Float |
| Trade count | `trade_count` | Integer |
| Win rate | `win_rate` | Percentage |

### Exit Criteria

- All 4 result types fetched
- No empty or null responses
- No `JQ_EXEC_005` error

---

## Stage 6: Normalize

**Purpose**: Convert raw platform outputs to archive contract format.

### Steps

| Step | Action | Output |
|------|--------|--------|
| 6.1 | Normalize metrics to `metrics.json` | Standard nested metric schema |
| 6.2 | Normalize trades to `trades.csv` | Standard trade columns |
| 6.3 | Normalize NAV to `nav.csv` | Standard NAV columns |
| 6.4 | Normalize positions to `positions.csv` (optional) | Standard position columns |
| 6.5 | Build `platform_meta.json` | Run metadata |

### Normalized Metrics Schema

Matches `run_archive/README.md` nested schema:

```json
{
  "run_id": "string",
  "strategy_id": "string",
  "version": "string",
  "run_date": "date",
  "source": "joinquant",
  "period": {
    "start_date": "date",
    "end_date": "date",
    "trading_days": "int"
  },
  "returns": {
    "total_return": "float",
    "annual_return": "float",
    "benchmark_return": "float?",
    "excess_return": "float?"
  },
  "risk": {
    "max_drawdown": "float",
    "annual_volatility": "float",
    "downside_deviation": "float?"
  },
  "ratios": {
    "sharpe_ratio": "float",
    "sortino_ratio": "float?",
    "calmar_ratio": "float?",
    "information_ratio": "float?"
  },
  "trade_stats": {
    "total_trades": "int",
    "win_rate": "float",
    "profit_factor": "float?",
    "avg_holding_days": "float"
  },
  "turnover": {
    "annual_turnover": "float",
    "avg_daily_turnover": "float"
  }
}
```

### Normalized Trade Columns

Matches `run_archive/README.md` schema:

| Column | Type | Description |
|--------|------|-------------|
| `trade_id` | string | Unique trade identifier |
| `date` | date | Execution date |
| `symbol` | string | Stock code |
| `action` | enum | `buy` / `sell` |
| `price` | float | Execution price |
| `shares` | int | Number of shares |
| `value` | float | Trade value |
| `commission` | float? | Commission cost |
| `slippage` | float? | Slippage cost |

### Normalized NAV Columns

Matches `run_archive/README.md` schema:

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Trading date |
| `nav` | float | Net asset value |
| `cash` | float? | Cash balance |
| `position_value` | float? | Position value |
| `benchmark_nav` | float? | Benchmark NAV for comparison |

### Normalized Position Columns

Matches `run_archive/README.md` schema (optional):

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Snapshot date |
| `symbol` | string | Stock code |
| `shares` | int | Shares held |
| `market_value` | float | Market value |
| `weight` | float | Portfolio weight |

### Platform Meta Schema

Matches `run_archive/README.md` schema:

```json
{
  "algorithm_id": "string?",
  "backtest_id": "string?",
  "submit_time": "datetime?",
  "finish_time": "datetime?",
  "account_id": "string?",
  "benchmark": "string?",
  "initial_cash": "float",
  "slippage_model": "string?",
  "commission_model": "string?",
  "frequency": "string?",
  "raw_response_path": "string?"
}
```

### Exit Criteria

- 4-5 normalized files produced (positions optional)
- Schema valid per archive contract
- No `JQ_EXEC_006` error

---

## Stage 7: Archive

**Purpose**: Store normalized outputs in run archive.

### Steps

| Step | Action | Output |
|------|--------|--------|
| 7.1 | Create archive directory | `run_archive/<strategy_id>/<version>/<run_date>/` |
| 7.2 | Write `metrics.json` | Archived metrics |
| 7.3 | Write `trades.csv` | Archived trades |
| 7.4 | Write `nav.csv` | Archived NAV |
| 7.5 | Write `positions.csv` (optional) | Archived positions |
| 7.6 | Write `platform_meta.json` | Archived metadata |
| 7.7 | Write `run_report.md` | Summary report |

### Exit Criteria

- Directory created
- 5 required files written (metrics, trades, nav, platform_meta, run_report)
- Files readable and non-empty
- `positions.csv` optional but recommended

---

## Stage 8: Report

**Purpose**: Generate summary report for diff comparison.

### Steps

| Step | Action | Output |
|------|--------|--------|
| 8.1 | Load archived outputs | All 5 files |
| 8.2 | Generate summary markdown | `run_report.md` |
| 8.3 | Link to task spec and strategy card | Traceability |

### Report Contents

| Section | Content |
|---------|---------|
| Header | Task ID, strategy name, version, run date |
| Parameters | Key backtest parameters |
| Metrics Table | Key performance metrics |
| Trade Summary | Trade count, win rate, turnover |
| Notes | Observations, anomalies |

### Report Template

```markdown
# Platform Run Report

**Task ID**: <task_id>
**Strategy**: <strategy_name> (<version>)
**Platform**: JoinQuant
**Run Date**: <YYYY-MM-DD>

## Parameters
- Start: <start_date>
- End: <end_date>
- Capital: <initial_cash>
- Benchmark: <benchmark>

## Performance Metrics
| Metric | Value |
|--------|-------|
| Annualized Return | <value> |
| Max Drawdown | <value> |
| Sharpe Ratio | <value> |
...

## Trade Summary
- Total Trades: <count>
- Win Rate: <rate>
- Turnover: <turnover>

## Notes
<Any observations or anomalies>
```

### Exit Criteria

- `run_report.md` generated
- Report links to task spec
- Report ready for diff comparison

---

## Full Flow Summary

| Stage | Input | Output | Duration |
|-------|-------|--------|----------|
| Prepare | task_spec, jq_strategy, panel | Validation status | ~1 min |
| Generate | Validated inputs | JoinQuant script | ~2 min |
| Submit | Strategy script | algorithm_id | ~1 min |
| Wait | algorithm_id | Completed status | ~10-60 min |
| Fetch | algorithm_id | Raw results | ~1 min |
| Normalize | Raw results | 4-5 normalized files | ~1 min |
| Archive | Normalized files | Archive directory | ~1 min |
| Report | Archived files | run_report.md | ~1 min |

**Total**: ~15-70 minutes (depends on backtest duration)

---

## Integration with Diff Reports

After archiving, the flow connects to `diff_reports/`:

1. Load local `strategy_kits` artifacts
2. Load platform `run_archive` artifacts
3. Compare metrics, trades, NAV
4. Generate diff report
5. Record decision in `iteration_registry`

See: `jq_workbench/platform/diff_reports/README.md`

---

## Error Recovery

| Error | Recovery Action |
|-------|-----------------|
| `JQ_EXEC_001` | Fix task spec, re-validate |
| `JQ_EXEC_002` | Generate or locate jq_strategy.py |
| `JQ_EXEC_003` | Generate panel or fix path |
| `JQ_EXEC_004` | Retry submission, check auth |
| `JQ_EXEC_005` | Retry fetch, extend timeout |
| `JQ_EXEC_006` | Fix normalization logic |

---

## References

1. `jq_workbench/platform/jq_executor/README.md` - Executor responsibilities
2. `jq_workbench/platform/run_archive/README.md` - Archive contract
3. `jq_workbench/platform/diff_reports/README.md` - Diff comparison
4. `jq_workbench/governance/standards/task_spec_profile.md` - Task spec schema
5. `ml_quant_framework/data/jqdata.py` - JQData API reference