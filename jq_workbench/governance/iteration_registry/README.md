# Iteration Registry

## Purpose

The iteration registry provides end-to-end traceability for every strategy version change. Each record captures one controlled experiment: hypothesis, change, execution, outcome, and decision.

## Directory Structure

```
jq_workbench/governance/iteration_registry/
  <strategy_id>__iterations.yaml
```

One file per strategy, containing all iterations in chronological order.

## Record Schema

Each iteration is a single record with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `iteration_id` | string | yes | Unique identifier: `<strategy_id>__v<version>` |
| `strategy_id` | string | yes | Matches `strategy_card.meta.strategy_id` |
| `version` | string | yes | Semver: `v1.0`, `v1.1`, `v2.0` |
| `hypothesis` | string | yes | What this iteration intends to test or improve |
| `change_point` | string | yes | Single parameter or component changed (one change per iteration) |
| `task_spec_id` | string | yes | Reference to frozen task spec file |
| `jq_run_id` | string? | no | JoinQuant algorithm run ID (if submitted) |
| `local_run_id` | string? | no | Local strategy_kits run ID |
| `key_metrics` | object | yes | Performance summary |
| `diff_outcome` | enum | yes | `consistent` \| `divergent` \| `pending` \| `skipped` |
| `decision` | enum | yes | `promote` \| `rollback` \| `pending` \| `retire` |
| `notes` | string? | no | Additional context |

## Key Metrics Object

```yaml
key_metrics:
  sharpe: float?
  annual_return: float?
  max_drawdown: float?
  turnover: float?
  win_rate: float?
  profit_factor: float?
```

## State Transitions

### Decision Flow

```
pending --> promote --> (next iteration)
    |          |
    |          v
    |       rollback --> (previous version)
    |          |
    v          v
  retire     retire
```

### Decision Definitions

| Decision | Meaning | Next Action |
|----------|---------|-------------|
| `pending` | Awaiting results or review | Complete metrics and diff_outcome |
| `promote` | Version validated, advance to next iteration | Create next version or submit to production |
| `rollback` | Change degraded performance, revert to previous | Restore previous version's parameters |
| `retire` | Strategy no longer viable | Document reason, archive |

### Diff Outcome Definitions

| Outcome | Meaning |
|---------|---------|
| `consistent` | Local and JoinQuant results match within tolerance |
| `divergent` | Significant difference between local and JoinQuant |
| `pending` | Diff comparison not yet performed |
| `skipped` | No JoinQuant run, local-only iteration |

## File Example

`value_quality_momentum__iterations.yaml`:

```yaml
strategy_id: value_quality_momentum
iterations:
  - iteration_id: value_quality_momentum__v1.0
    version: v1.0
    hypothesis: "Base version: value + quality + momentum composite"
    change_point: "initial implementation"
    task_spec_id: value_quality_momentum__v1.0
    local_run_id: "run_20250115_143052"
    jq_run_id: "algo_78901"
    key_metrics:
      sharpe: 1.42
      annual_return: 0.186
      max_drawdown: -0.152
      turnover: 2.8
    diff_outcome: consistent
    decision: promote
    notes: "Base case validated"

  - iteration_id: value_quality_momentum__v1.1
    version: v1.1
    hypothesis: "Increasing top_n improves diversification and reduces turnover"
    change_point: "pipeline.top_n: 20 -> 30"
    task_spec_id: value_quality_momentum__v1.1
    local_run_id: "run_20250118_092145"
    jq_run_id: "algo_78934"
    key_metrics:
      sharpe: 1.35
      annual_return: 0.172
      max_drawdown: -0.148
      turnover: 2.1
    diff_outcome: consistent
    decision: rollback
    previous_version: v1.0
    notes: "Lower sharpe, not worth the diversification benefit"

  - iteration_id: value_quality_momentum__v1.2
    version: v1.2
    hypothesis: "Tightening sector constraint reduces concentration risk"
    change_point: "risk.max_industry: 0.30 -> 0.20"
    task_spec_id: value_quality_momentum__v1.2
    local_run_id: "run_20250120_110523"
    jq_run_id: null
    key_metrics:
      sharpe: 1.38
      annual_return: 0.179
      max_drawdown: -0.141
      turnover: 2.9
    diff_outcome: skipped
    decision: pending
    notes: "Awaiting JoinQuant validation"
```

## End-to-End Traceability

Each iteration links to:

| Link | Target | Path |
|------|--------|------|
| Strategy definition | Strategy card | `knowledge/strategy_cards/<strategy_id>.yaml` |
| Execution contract | Task spec | `research/task_specs/<task_spec_id>.json` |
| Local artifacts | Run archive | `artifacts/<local_run_id>/` |
| Platform results | Run archive | `platform/run_archive/<strategy_id>/<version>/<run_date>/` |
| Diff analysis | Diff report | `platform/diff_reports/<strategy_id>__<version>.md` |

## Traceability Query

To trace any iteration:

1. Find iteration record by `iteration_id`
2. Open task spec at `research/task_specs/<task_spec_id>.json`
3. Check metrics and decision
4. If `diff_outcome = divergent`, review `platform/diff_reports/`
5. If `decision = rollback`, confirm previous version is restored

## Change Discipline

Per operating model and task_spec_profile, each iteration must change **only one** of:

1. `pipeline.top_n` or `pipeline.weight_mode`
2. `data.start_date` / `end_date` (different validation slice)
3. `portfolio` constraints (max_single, cash_target, max_positions)
4. `risk` parameters (max_industry, max_turnover)
5. `backtest.template` (triggers major version bump)

Major changes requiring **v2.0** or higher:
- `backtest.template` change
- `data.panel_path` change (different signals/factors)
- Universe change (different base_pool)

## Naming Rules

1. `iteration_id`: `<strategy_id>__v<version>` (matches task_spec naming)
2. `strategy_id`: snake_case, matches strategy_card
3. `version`: semver format
4. File name: `<strategy_id>__iterations.yaml`

## Rollback Protocol

When `decision = rollback`:

1. The iteration record is marked `decision: rollback` (no new version created)
2. Update strategy_card `meta.version` back to `previous_version`
3. Restore strategy_card parameters to match `previous_version` task_spec
4. Document reason in iteration record `notes`
5. Next iteration continues from restored version (e.g., v1.0 -> v1.1 rollback -> v1.2 from v1.0)

No rollback iteration record is created - the failed version itself carries the rollback decision.

## Promotion Protocol

When `decision = promote`:

1. Ensure `diff_outcome = consistent` (or `skipped` with justification)
2. Update strategy_card `meta.version` to current version
3. If transitioning to `production_ready`, update `meta.state`
4. Document outcome in strategy_card `changelog`

## Quality Gate

Before setting `decision = promote`:

- [ ] `key_metrics` complete with all performance fields
- [ ] `diff_outcome` not `pending`
- [ ] Task spec exists and is frozen
- [ ] If `jq_run_id` present: diff report reviewed
- [ ] Change point is single and well-defined
- [ ] Hypothesis matches the change

## Cross-References

| Document | Purpose |
|----------|---------|
| `standards/iteration_registry_schema.md` | Full schema specification |
| `standards/strategy_card_schema.md` | Strategy definition |
| `standards/task_spec_profile.md` | Execution contract |
| `platform/run_archive/README.md` | Platform output storage |
| `platform/diff_reports/README.md` | Local-platform comparison |