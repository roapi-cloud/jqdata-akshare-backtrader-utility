# Run Artifact Contract

This document specifies the contract for run artifacts produced by local validation (`strategy_kits`) and JoinQuant platform runs. Both sources must conform to this contract for diff comparison to be valid.

## Purpose

1. Enable reliable comparison between local and platform outputs
2. Ensure reproducibility of research runs
3. Provide audit trail for strategy iteration
4. Support governance decision-making (keep/rollback)

## Artifact Sources

| Source | Directory | Producer |
|--------|-----------|----------|
| Local | `./artifacts/<task_id>/<timestamp>/` | `strategy_kits` |
| Platform | `run_archive/<strategy_id>/<version>/<run_date>/` | `jq_executor` |

## Naming Convention

Per `architecture.md` standard artifacts, the canonical names are:
- `metrics.json` (not `metrics.csv`)
- `trades.csv`
- `nav.csv` (not `nav_series.csv`)

Local raw artifacts from `strategy_kits` use `metrics.csv` and `nav_series.csv` per `task_spec_profile.md`. These are normalized to the canonical format before diff comparison.

| Raw Local Artifact | Normalized Contract File |
|--------------------|--------------------------|
| `metrics.csv` | `metrics.json` |
| `nav_series.csv` | `nav.csv` |
| `trades.csv` | `trades.csv` (unchanged) |
| `summary.json` | Used to populate `metrics.json` |

## Contract Files

Both sources must produce the following files:

| File | Local | Platform | Required |
|------|-------|----------|----------|
| `metrics.json` | yes | yes | yes |
| `trades.csv` | yes | yes | yes |
| `nav.csv` | yes | yes | yes |
| `positions.csv` | optional | optional | no |
| `run_meta.json` | yes | no | local only |
| `platform_meta.json` | no | yes | platform only |
| `task_spec.json` | yes | no | local only |
| `run_report.md` | optional | yes | conditional |

## Core Schemas

### metrics.json (Required)

Both local and platform must produce this with matching schema.

```json
{
  "run_id": "string",
  "strategy_id": "string",
  "version": "string",
  "run_date": "date",
  "source": "enum: local | joinquant",
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

### Required Fields

| Field | Type | Constraint |
|-------|------|------------|
| `run_id` | string | Non-empty, unique identifier |
| `strategy_id` | string | Matches strategy_card.meta.strategy_id |
| `version` | string | Semver format (v1.0, v1.1, etc.) |
| `run_date` | date | ISO format (YYYY-MM-DD) |
| `source` | enum | `local` or `joinquant` |
| `period.start_date` | date | ISO format |
| `period.end_date` | date | ISO format, must be > start_date |
| `period.trading_days` | int | Must be positive |
| `returns.total_return` | float | Decimal (0.15 = 15%) |
| `returns.annual_return` | float | Decimal |
| `risk.max_drawdown` | float | Decimal, positive value (0.20 = 20%) |
| `risk.annual_volatility` | float | Decimal |
| `ratios.sharpe_ratio` | float | Can be negative |
| `trade_stats.total_trades` | int | Must be >= 0 |
| `trade_stats.win_rate` | float | Decimal (0.55 = 55%) |

### trades.csv (Required)

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `trade_id` | string | yes | Unique trade identifier |
| `date` | date | yes | Execution date (YYYY-MM-DD) |
| `symbol` | string | yes | Stock code (e.g., `000001.XSHE`) |
| `action` | enum | yes | `buy` or `sell` |
| `price` | float | yes | Execution price |
| `shares` | int | yes | Number of shares |
| `value` | float | yes | Trade value (price * shares) |
| `commission` | float | no | Commission cost |
| `slippage` | float | no | Slippage cost |

### nav.csv (Required)

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `date` | date | yes | Trading date (YYYY-MM-DD) |
| `nav` | float | yes | Net asset value |
| `cash` | float | no | Cash balance |
| `position_value` | float | no | Position value |
| `benchmark_nav` | float | no | Benchmark NAV for comparison |

### positions.csv (Optional)

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `date` | date | yes | Snapshot date |
| `symbol` | string | yes | Stock code |
| `shares` | int | yes | Shares held |
| `market_value` | float | yes | Market value |
| `weight` | float | yes | Portfolio weight (decimal) |

### run_meta.json (Local Only)

```json
{
  "task_id": "string",
  "task_spec_path": "string",
  "panel_path": "string?",
  "execution_time": "datetime",
  "backtrader_version": "string?",
  "strategy_kits_version": "string?",
  "python_version": "string?",
  "random_seed": "int?",
  "parameters_hash": "string?"
}
```

### platform_meta.json (Platform Only)

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

## Comparison Rules

### Direct Comparison Fields

These fields must match exactly between local and platform:

| Field | Tolerance |
|-------|-----------|
| `strategy_id` | exact |
| `version` | exact |
| `period.start_date` | exact |
| `period.end_date` | exact |

### Numerical Comparison Fields

These fields allow tolerance-based comparison:

| Field | Default Tolerance | Comparison |
|-------|-------------------|------------|
| `returns.total_return` | 2% | abs(local - platform) < 0.02 |
| `returns.annual_return` | 1% | abs(local - platform) < 0.01 |
| `risk.max_drawdown` | 3% | abs(local - platform) < 0.03 |
| `ratios.sharpe_ratio` | 0.2 | abs(local - platform) < 0.2 |
| `trade_stats.win_rate` | 5% | abs(local - platform) < 0.05 |
| `turnover.annual_turnover` | 0.5 | abs(local - platform) < 0.5 |

### Trade Alignment

| Metric | Calculation | Acceptable Threshold |
|--------|-------------|---------------------|
| Trade Count Match | local.count == platform.count | exact |
| Date Match Rate | matched_dates / total_dates | > 95% |
| Symbol Match Rate | matched_symbols / total_trades | > 90% |
| Price Deviation | avg(abs(local.price - platform.price) / platform.price) | < 1% |

### NAV Alignment

| Metric | Calculation | Acceptable Threshold |
|--------|-------------|---------------------|
| NAV Correlation | pearson(local.nav, platform.nav) | > 0.95 |
| NAV RMSE | sqrt(mean((local.nav - platform.nav)^2)) | < 0.05 * initial_cash |
| End NAV Delta | abs(local.end_nav - platform.end_nav) / platform.end_nav | < 2% |

## Contract Validation

Before diff comparison, validate:

1. **Schema Validity**: Both metrics.json conform to schema
2. **Field Coverage**: All required fields present
3. **Date Range Match**: Period matches between sources
4. **Trade Count Sanity**: Both have trades (unless expected)
5. **NAV Coverage**: NAV series covers full period

## Divergence Categories

| Category | Description | Action |
|----------|-------------|--------|
| `trivial` | Within tolerance, no impact | Keep |
| `data_source` | Local vs JQ data differences | Document, may keep |
| `timing` | Execution timing differences | Investigate, may keep |
| `parameter` | Slippage/commission model differences | Adjust parameters, re-run |
| `implementation` | Logic differences or bugs | Fix and re-run |
| `critical` | Large divergence, unknown cause | Rollback |

## Versioning

| Change Type | Version Increment | Contract Impact |
|-------------|-------------------|------------------|
| Add optional field | None | Backward compatible |
| Add required field | Major | Requires migration |
| Change field type | Major | Requires migration |
| Remove field | Major | Requires migration |
| Change tolerance | Minor | Document change |

## Related

- `platform/run_archive/README.md` for archive structure
- `platform/diff_reports/README.md` for diff report format
- `governance/standards/task_spec_profile.md` for task spec contract
- `governance/standards/strategy_card_schema.md` for strategy card schema