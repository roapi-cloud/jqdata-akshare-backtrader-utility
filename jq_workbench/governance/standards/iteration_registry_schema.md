# Iteration Registry Schema

## Purpose

Defines the authoritative schema for iteration records. Each record captures one controlled experiment in the strategy R&D lifecycle.

## Schema Version

Current: `1.0.0`

## File Format

YAML, one file per strategy: `<strategy_id>__iterations.yaml`

## Full Schema

```yaml
strategy_id: string                    # Required: matches strategy_card.meta.strategy_id
iterations:                            # Required: list of iteration records
  - iteration_id: string               # Required: <strategy_id>__v<version>
    strategy_id: string                # Required: matches parent strategy_id
    version: string                    # Required: semver (v1.0, v1.1, v2.0)
    hypothesis: string                 # Required: what this iteration tests
    change_point: string               # Required: single change description
    task_spec_id: string               # Required: frozen task spec reference
    jq_run_id: string?                 # Optional: JoinQuant algorithm ID
    local_run_id: string?              # Optional: local run identifier
    key_metrics:                      # Required: performance summary
      sharpe: float?                   # Optional: Sharpe ratio
      annual_return: float?            # Optional: annualized return (decimal)
      max_drawdown: float?             # Optional: max drawdown (decimal, negative)
      turnover: float?                # Optional: annual turnover ratio
      win_rate: float?                 # Optional: win rate (decimal)
      profit_factor: float?            # Optional: profit factor
      alpha: float?                    # Optional: vs benchmark
      beta: float?                      # Optional: vs benchmark
      information_ratio: float?        # Optional: IR vs benchmark
    diff_outcome: enum                 # Required: consistency status
    decision: enum                     # Required: action taken
    previous_version: string?          # Optional: parent version for rollback
    notes: string?                     # Optional: additional context
    created_at: date?                  # Optional: record creation date
    updated_at: date?                  # Optional: last update date
```

## Field Specifications

### Top-Level Fields

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `strategy_id` | string | yes | Must match file prefix and strategy_card |
| `iterations` | array | yes | At least one iteration required |

### Iteration Fields

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `iteration_id` | string | yes | Format: `<strategy_id>__v<version>` |
| `strategy_id` | string | yes | Must match top-level `strategy_id` |
| `version` | string | yes | Semver format: `v<major>.<minor>` |
| `hypothesis` | string | yes | Non-empty, describes test intent |
| `change_point` | string | yes | Non-empty, single change description |
| `task_spec_id` | string | yes | Must reference existing task spec |
| `jq_run_id` | string | no | JoinQuant algorithm ID if submitted |
| `local_run_id` | string | no | Local run identifier |
| `key_metrics` | object | yes | See metrics schema below |
| `diff_outcome` | enum | yes | `consistent`, `divergent`, `pending`, `skipped` |
| `decision` | enum | yes | `promote`, `rollback`, `pending`, `retire` |
| `previous_version` | string | no | Required if `decision = rollback` |
| `notes` | string | no | Free-form context |
| `created_at` | date | no | ISO 8601 date |
| `updated_at` | date | no | ISO 8601 date |

### Key Metrics Schema

| Field | Type | Constraint |
|-------|------|------------|
| `sharpe` | float | Can be negative |
| `annual_return` | float | Decimal format (0.15 = 15%) |
| `max_drawdown` | float | Negative decimal (-0.20 = -20%) |
| `turnover` | float | Annual turnover ratio |
| `win_rate` | float | Decimal (0.55 = 55%) |
| `profit_factor` | float | Gross profit / gross loss |
| `alpha` | float | Annualized alpha vs benchmark |
| `beta` | float | Beta vs benchmark |
| `information_ratio` | float | Information ratio vs benchmark |

At least one metric must be populated for `decision = promote` or `decision = rollback`.

## Enum Values

### diff_outcome

| Value | Definition |
|-------|------------|
| `consistent` | Local and JoinQuant results within defined tolerance |
| `divergent` | Local and JoinQuant differ beyond tolerance |
| `pending` | Diff comparison not yet performed |
| `skipped` | No JoinQuant run, local-only validation |

Note: `diff_outcome` extends `strategy_card_schema.md`'s `diff_status` enum with `skipped` for local-only iterations.

### decision

| Value | Definition | Valid Transitions |
|-------|------------|-------------------|
| `pending` | Awaiting final review | -> `promote`, `rollback`, `retire` |
| `promote` | Accepted, advance to next iteration | Terminal for this iteration |
| `rollback` | Rejected, revert to previous version | Terminal for this iteration |
| `retire` | Strategy discontinued | Terminal |

## Validation Rules

1. **Version sequence**: Iterations must be ordered by version (v1.0 -> v1.1 -> v1.2 -> v2.0)
2. **Unique iteration_id**: No duplicate `iteration_id` within a file
3. **Task spec exists**: `task_spec_id` must reference an existing file in `research/task_specs/`
4. **Rollback reference**: If `decision = rollback`, `previous_version` must exist in iterations
5. **Change point singularity**: `change_point` should describe exactly one change
6. **Metrics completeness**: If `decision` is `promote` or `rollback`, `key_metrics` must have at least 3 populated fields

## Change Point Categories

Per task_spec_profile.md, allowed change point types for minor iterations:

| Category | Example |
|----------|---------|
| Parameter tuning | `pipeline.top_n: 20 -> 30` |
| Weight adjustment | `pipeline.weight_mode: equal -> score` |
| Portfolio constraint | `portfolio.max_single: 0.10 -> 0.08` |
| Risk constraint | `risk.max_industry: 0.30 -> 0.25` |
| Validation slice | `data.start_date: 2020-01-01 -> 2018-01-01` |

Major version increments (v1.x -> v2.x) required for:
- Template change (`backtest.template`)
- Panel version change (`data.panel_path`, different signals)
- Universe change (handled at strategy_card level, not task_spec)

## Version Numbering

| Change Type | Version Increment |
|-------------|------------------|
| New strategy | v1.0 |
| Minor parameter adjustment | v1.1, v1.2, ... |
| Major structural change (template/panel) | v2.0, v3.0, ... |
| Rollback (failed iteration) | No new version, restore previous |

Version sequence continues regardless of rollback:
- v1.0 (promote) -> v1.1 (rollback) -> v1.2 (from v1.0 base, different change_point)
- v1.2's `previous_version` may reference v1.0 if v1.1 was rolled back

## State Model

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    v                                     │
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│  idea   │ -> │ pending │ -> │ promote │ -> │  next   │ │
└─────────┘    └─────────┘    └─────────┘    │ version │ │
                    │                        └─────────┘ │
                    │                                    │
                    ├──────────┐                         │
                    │          v                         │
                    │    ┌──────────┐                    │
                    └───>│ rollback │────────────────────┘
                    │    └──────────┘
                    │          │
                    │          v
                    │    ┌─────────┐
                    └───>│  retire │
                         └─────────┘
```

## Example Files

### Minimal Valid File

```yaml
strategy_id: momentum_etf_rotation
iterations:
  - iteration_id: momentum_etf_rotation__v1.0
    strategy_id: momentum_etf_rotation
    version: v1.0
    hypothesis: "Base version: weekly ETF momentum rotation"
    change_point: "initial implementation"
    task_spec_id: momentum_etf_rotation__v1.0
    key_metrics:
      sharpe: 0.95
      annual_return: 0.12
      max_drawdown: -0.18
    diff_outcome: pending
    decision: pending
```

### Complete File with History

```yaml
strategy_id: value_quality_momentum
iterations:
  - iteration_id: value_quality_momentum__v1.0
    strategy_id: value_quality_momentum
    version: v1.0
    hypothesis: "Composite scoring of value, quality, momentum factors"
    change_point: "initial implementation"
    task_spec_id: value_quality_momentum__v1.0
    jq_run_id: "algo_78901"
    local_run_id: "run_20250115_143052"
    key_metrics:
      sharpe: 1.42
      annual_return: 0.186
      max_drawdown: -0.152
      turnover: 2.8
      win_rate: 0.54
      alpha: 0.045
      beta: 0.92
    diff_outcome: consistent
    decision: promote
    notes: "Base case validated on JoinQuant"
    created_at: "2025-01-15"
    updated_at: "2025-01-16"

  - iteration_id: value_quality_momentum__v1.1
    strategy_id: value_quality_momentum
    version: v1.1
    hypothesis: "Increasing top_n improves diversification"
    change_point: "pipeline.top_n: 20 -> 30"
    task_spec_id: value_quality_momentum__v1.1
    jq_run_id: "algo_78934"
    local_run_id: "run_20250118_092145"
    key_metrics:
      sharpe: 1.35
      annual_return: 0.172
      max_drawdown: -0.148
      turnover: 2.1
    diff_outcome: consistent
    decision: rollback
    previous_version: v1.0
    notes: "Lower sharpe despite lower turnover, not beneficial"
    created_at: "2025-01-18"
    updated_at: "2025-01-19"

  - iteration_id: value_quality_momentum__v1.2
    strategy_id: value_quality_momentum
    version: v1.2
    hypothesis: "Sector constraint tightening reduces concentration risk"
    change_point: "risk.max_industry: 0.30 -> 0.20"
    task_spec_id: value_quality_momentum__v1.2
    local_run_id: "run_20250120_110523"
    key_metrics:
      sharpe: 1.48
      annual_return: 0.191
      max_drawdown: -0.138
      turnover: 2.9
    diff_outcome: pending
    decision: pending
    notes: "Local results promising, awaiting JQ validation"
    created_at: "2025-01-20"
    updated_at: "2025-01-20"
```

## Cross-Reference Integrity

Each iteration record must have valid references to:

| Field | Reference Target | Validation |
|-------|-----------------|------------|
| `strategy_id` | `knowledge/strategy_cards/<strategy_id>.yaml` | File exists |
| `task_spec_id` | `research/task_specs/<task_spec_id>.json` | File exists |
| `jq_run_id` | `platform/run_archive/<strategy_id>/<version>/` | Directory exists |
| `local_run_id` | `artifacts/<local_run_id>/` | Directory exists |

## Diff Outcome Tolerance

Default tolerance for `diff_outcome = consistent`:

| Metric | Tolerance |
|--------|-----------|
| Sharpe ratio | ±0.10 |
| Annual return | ±2% |
| Max drawdown | ±3% |
| Turnover | ±20% relative |

If any metric exceeds tolerance, `diff_outcome = divergent`.

## File Lifecycle

1. **Create**: New file when first iteration of strategy is defined
2. **Append**: New iteration record appended to `iterations` array
3. **Update**: Only `diff_outcome`, `decision`, `key_metrics`, `notes`, `updated_at` may be updated
4. **Archive**: File retained indefinitely for audit trail

## Quality Checklist

Before closing an iteration:

- [ ] `iteration_id` matches `<strategy_id>__v<version>` format
- [ ] `task_spec_id` references an existing frozen task spec
- [ ] `change_point` describes exactly one change
- [ ] `hypothesis` explains why this change was tested
- [ ] `key_metrics` has at least 3 populated fields (for promote/rollback)
- [ ] `diff_outcome` is not `pending` (for promote/rollback)
- [ ] If `decision = rollback`, `previous_version` is populated and valid
- [ ] Version sequence is maintained