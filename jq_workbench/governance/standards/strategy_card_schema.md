# Strategy Card Schema

## Purpose

A `strategy_card` is the authoritative summary of a strategy's thesis, implementation contract, and known failure modes. One card per strategy, versioned and immutable after promotion.

## File Location

```
jq_workbench/knowledge/strategy_cards/<strategy_id>.yaml
```

## Schema

```yaml
meta:
  strategy_id: string          # snake_case, unique identifier
  version: string              # semver: v1.0, v1.1, v1.2
  created_at: date             # YYYY-MM-DD
  updated_at: date             # YYYY-MM-DD
  state: enum                  # idea | candidate | validated | production_ready | retired
  author: string               # owner or source
  source_ref: string?          # path to original script or document

thesis:
  summary: string              # one-sentence investment thesis
  alpha_type: enum             # value | momentum | quality | low_vol | carry | event | multi_factor
  time_horizon: enum           # intraday | daily | weekly | monthly
  expected_edge: string        # why this should work (behavioral, structural, risk_premium)

universe:
  base_pool: string            # index code: 000300.XSHG, 000905.XSHG, 000852.XSHG, all_a
  filters:                     # ordered list of pool filters
    - name: string             # filter name
      params: map              # filter parameters
      negate: bool?            # exclude rather than include
  min_cap: float?              # minimum market cap (亿)
  max_cap: float?              # maximum market cap (亿)
  exclude_st: bool             # exclude ST stocks (default true)
  exclude_kcbj: bool           # exclude 科创板/北交所 (default true)
  exclude_pause: bool          # exclude suspended stocks (default true)
  exclude_ipo_days: int        # exclude newly listed stocks for N days

signals:
  factors:                     # list of scoring factors
    - name: string
      source: enum             # jqfactor | jqdata | local | external
      formula: string?         # formula or expression (jqfactor mapped name)
      weight: float            # relative weight, should sum to 1.0
      direction: enum          # positive | negative
      preprocess: [string]?    # list: winsorize, standardize, rank, neutralize_industry, neutralize_market_cap
  composite_method: enum        # weighted_sum | rank_average | zscore_sum
  rebalance_trigger: enum      # periodic | signal_driven | hybrid

rebalance:
  frequency: enum              # daily | weekly | monthly | quarterly
  weekday: int?                # 0=Monday, 4=Friday (for weekly/monthly)
  top_n: int                   # number of stocks to hold
  weight_method: enum          # equal | rank_weight | inverse_vol | risk_parity | custom
  max_weight: float?           # single position max weight
  min_weight: float?           # single position min weight

risk:
  position_rules:
    max_position_pct: float?   # max single position % of NAV
    min_cash_pct: float?       # minimum cash buffer
    max_sector_pct: float?     # max sector concentration
  stop_loss:
    enabled: bool
    method: enum?              # trailing | fixed | atr | none
    threshold: float?          # stop loss threshold
  take_profit:
    enabled: bool
    threshold: float?          # take profit threshold
  regime_filter:               # market regime risk control
    enabled: bool
    indicator: string?         # cvix, breadth, ma_cross, etc.
    rule: string?              # filter rule expression

market_regime:
  favorable:                   # conditions where strategy works best
    - description: string
  unfavorable:                 # conditions where strategy struggles
    - description: string
  neutral:                     # conditions where strategy is flat
    - description: string

failure_modes:
  - name: string               # failure mode name
    condition: string          # when it occurs
    mitigation: string         # how to detect or mitigate
    severity: enum             # low | medium | high | critical

dependencies:
  jqdata:
    tables: [string]           # e.g., valuation, balance, income
    functions: [string]        # e.g., get_price, get_index_stocks
  jqfactor:
    factors: [string]          # e.g., earnings_to_price_ratio, roe_ttm, return_12m
  external:
    - name: string
      source: string
      refresh: string?         # daily, weekly, etc.

performance_targets:
  expected_return: float?      # annualized %
  max_drawdown: float?         # max acceptable drawdown %
  sharpe_ratio: float?         # target Sharpe
  turnover: float?             # annual turnover rate

validation:
  local_runs:                  # strategy_kits runs
    - run_id: string
      date: date
      sharpe: float
      max_dd: float
  platform_runs:               # JoinQuant runs
    - run_id: string
      date: date
      algorithm_id: string
      sharpe: float
      max_dd: float
  diff_status: enum?           # consistent | divergent | pending

notes:
  - string                     # free-form notes

changelog:
  - version: string
    date: date
    change: string
    decision: enum             # keep | rollback
```

## Naming Rules

1. `strategy_id`: snake_case, e.g., `value_quality_momentum`, `small_cap_rotate`
2. `version`: semver format, increment on any material change
3. One card per strategy; version history in `changelog`
4. File name matches `strategy_id`: `<strategy_id>.yaml`

## Required Fields

| Field | Required |
|-------|----------|
| `meta.strategy_id` | yes |
| `meta.version` | yes |
| `meta.state` | yes |
| `thesis.summary` | yes |
| `thesis.alpha_type` | yes |
| `universe.base_pool` | yes |
| `signals.factors` | yes (at least one) |
| `rebalance.frequency` | yes |
| `rebalance.top_n` | yes |
| `rebalance.weight_method` | yes |
| `risk.regime_filter.enabled` | yes |
| `dependencies` | yes (can be empty lists) |

## State Transitions

```
idea -> candidate -> validated -> production_ready -> retired
  |        |            |              |
  v        v            v              v
(retired) (retired)    (retired)      (retired)
```

- `idea`: Initial concept, no validation
- `candidate`: Has task_spec and local runs
- `validated`: Has JoinQuant platform validation with archived results
- `production_ready`: Passed diff report review, approved for production
- `retired`: No longer in use, reason documented in notes

## Validation Checklist

Before promotion to `validated`:

- [ ] Schema valid
- [ ] All required fields present
- [ ] At least one `local_runs` entry
- [ ] At least one `platform_runs` entry
- [ ] `diff_status` is `consistent`
- [ ] Failure modes documented
- [ ] Dependencies explicitly listed