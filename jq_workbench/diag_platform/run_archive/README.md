# Run Archive

Store authoritative JoinQuant platform outputs here for audit and comparison.

## Directory Structure

```
run_archive/
  <strategy_id>/
    <version>/
      <run_date>/
        metrics.json
        trades.csv
        nav.csv
        positions.csv
        platform_meta.json
        run_report.md
```

### Example

```
run_archive/
  value_quality_momentum/
    v1.0/
      2026-04-22/
        metrics.json
        trades.csv
        nav.csv
        positions.csv
        platform_meta.json
        run_report.md
```

## Naming Rules

| Element | Format | Example |
|---------|--------|---------|
| strategy_id | snake_case | `value_quality_momentum` |
| version | semver | `v1.0`, `v1.1`, `v1.2` |
| run_date | ISO date | `2026-04-22` |

Multiple runs on the same day append a sequence: `2026-04-22__001`, `2026-04-22__002`.

## Required Files

| File | Purpose | Required |
|------|---------|----------|
| `metrics.json` | Normalized performance metrics | yes |
| `trades.csv` | Trade log with timestamps | yes |
| `nav.csv` | Net asset value time series | yes |
| `positions.csv` | Position snapshots | no |
| `platform_meta.json` | JoinQuant run metadata | yes |
| `run_report.md` | Human-readable summary | yes |

## File Schemas

### metrics.json

Normalized performance metrics. Schema matches `run_artifact_contract.md` for diff comparison.

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

Note: `algorithm_id` and `backtest_id` are stored in `platform_meta.json`, not here.

### trades.csv

| Column | Type | Description |
|--------|------|-------------|
| `trade_id` | string | Unique trade identifier |
| `date` | date | Execution date |
| `symbol` | string | Stock code |
| `action` | enum | `buy` \| `sell` |
| `price` | float | Execution price |
| `shares` | int | Number of shares |
| `value` | float | Trade value |
| `commission` | float? | Commission cost |
| `slippage` | float? | Slippage cost |

### nav.csv

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Trading date |
| `nav` | float | Net asset value |
| `cash` | float? | Cash balance |
| `position_value` | float? | Position value |
| `benchmark_nav` | float? | Benchmark NAV for comparison |

### positions.csv

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Snapshot date |
| `symbol` | string | Stock code |
| `shares` | int | Shares held |
| `market_value` | float | Market value |
| `weight` | float | Portfolio weight |

### platform_meta.json

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

### run_report.md

```markdown
# Run Report: <strategy_id> <version>

**Run ID**: <run_id>
**Date**: <run_date>
**Source**: JoinQuant

## Summary

- Total Return: X.XX%
- Annual Return: X.XX%
- Max Drawdown: X.XX%
- Sharpe Ratio: X.XX

## Period

- Start: YYYY-MM-DD
- End: YYYY-MM-DD
- Trading Days: N

## Trade Statistics

- Total Trades: N
- Win Rate: X.XX%
- Avg Holding Days: X.X

## Notes

- Any observations or anomalies
- Data quality issues
- Execution notes
```

## Archive Workflow

1. **Submit**: `jq_executor` submits strategy to JoinQuant
2. **Fetch**: Retrieve run results when complete
3. **Normalize**: Convert JQ output to standard schema
4. **Validate**: Check required files and field coverage
5. **Write**: Persist to `<strategy_id>/<version>/<run_date>/`
6. **Link**: Update `strategy_card` validation.platform_runs

## Quality Gate

Before considering a run archived:

- [ ] All required files present
- [ ] `metrics.json` schema valid
- [ ] Date ranges match task_spec
- [ ] No null critical fields
- [ ] Trade count > 0 (non-trivial run)
- [ ] `platform_meta.json` includes `algorithm_id` or `backtest_id`

## Audit Trail

Each archive folder represents an immutable snapshot. Never modify archived files. Create a new run folder for corrections or re-runs.

## Related

- `governance/standards/run_artifact_contract.md` for contract specification
- `platform/diff_reports/` for comparison analysis
- `strategy_card` `validation.platform_runs` for registry link