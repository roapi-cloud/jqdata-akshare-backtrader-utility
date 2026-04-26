# Operating Checklists

## 1. New Strategy Intake Checklist

**Trigger**: Introducing a new strategy into the workbench.

**Inputs**: Raw strategy script, thesis document, or verbal description.

| Step | Action | Done |
|------|--------|------|
| 1.1 | Assign unique `strategy_id` in snake_case | [ ] |
| 1.2 | Create `knowledge/strategy_cards/<strategy_id>.yaml` | [ ] |
| 1.3 | Fill all required fields per `strategy_card_schema.md` | [ ] |
| 1.4 | Set `meta.state = idea` | [ ] |
| 1.5 | Save raw source under `knowledge/source_strategies/` (if script exists) | [ ] |
| 1.6 | Document `thesis.summary` in one sentence | [ ] |
| 1.7 | Define `universe.base_pool` and filters | [ ] |
| 1.8 | List `signals.factors` with weights and directions | [ ] |
| 1.9 | Specify `rebalance` parameters (frequency, top_n, weight_method) | [ ] |
| 1.10 | Document `dependencies` (jqdata tables, jqfactor factors, external sources) | [ ] |
| 1.11 | Identify at least one `failure_mode` | [ ] |
| 1.12 | Validate schema against `strategy_card_schema.md` | [ ] |

**Exit Criteria**: Strategy card exists, schema valid, state = `idea`.

---

## 2. Task Spec Freeze Checklist

**Trigger**: Ready to run local validation on a strategy version.

**Inputs**: Strategy card at `idea` state (for v1.0) or `candidate`/`validated` state (for version upgrades).

| Step | Action | Done |
|------|--------|------|
| 2.1 | Confirm strategy card exists and schema valid | [ ] |
| 2.2 | Assign version: `v1.0` for new, increment for changes | [ ] |
| 2.3 | Generate or validate panel file under `research/panels/` | [ ] |
| 2.4 | Create `research/task_specs/<strategy_id>__<version>.json` | [ ] |
| 2.5 | Map `strategy_card` fields to `task_spec` per `task_spec_profile.md` | [ ] |
| 2.6 | Fill all required fields: `task_id`, `strategy_name`, `panel_type`, `start_date`, `end_date`, `template`, `initial_cash` | [ ] |
| 2.7 | Set `pipeline.top_n`, `pipeline.weight_mode` | [ ] |
| 2.8 | Set `portfolio` constraints (`max_single`, `cash_target`) | [ ] |
| 2.9 | Set `risk` parameters (`max_industry`, `max_turnover`) | [ ] |
| 2.10 | Confirm `data.panel_path` exists and is non-empty | [ ] |
| 2.11 | Validate schema using `strategy_kits` validation | [ ] |
| 2.12 | Document change point (`initial implementation` for v1.0, or single parameter change from previous version) | [ ] |
| 2.13 | Update `strategy_card.changelog` with version entry | [ ] |

**Exit Criteria**: Task spec frozen, schema valid, panel file ready.

---

## 3. JoinQuant Submission Checklist

**Trigger**: Local validation complete, ready for platform validation.

**Inputs**: Frozen task spec, local run artifacts.

| Step | Action | Done |
|------|--------|------|
| 3.1 | Confirm local run completed with artifacts persisted | [ ] |
| 3.2 | Confirm `run_report.json` shows no contract errors | [ ] |
| 3.3 | Generate or update `research/jq_strategies/<strategy_id>__<version>.py` | [ ] |
| 3.4 | Inject parameters from task spec into strategy script | [ ] |
| 3.5 | Validate JoinQuant API compatibility (imports, function signatures) | [ ] |
| 3.6 | Confirm backtest parameters: start_date, end_date, initial_cash, benchmark | [ ] |
| 3.7 | Upload strategy to JoinQuant platform | [ ] |
| 3.8 | Trigger backtest execution | [ ] |
| 3.9 | Record `algorithm_id` in local notes | [ ] |
| 3.10 | Monitor backtest status until `completed` | [ ] |
| 3.11 | Fetch raw results (metrics, trades, NAV, metadata) | [ ] |
| 3.12 | Normalize results to archive contract format | [ ] |
| 3.13 | Archive under `platform/run_archive/<strategy_id>/<version>/<run_date>/` | [ ] |
| 3.14 | Create `run_report.md` summary | [ ] |

**Exit Criteria**: Results archived under `run_archive`, `platform_meta.json` written.

---

## 4. Result Review Checklist

**Trigger**: Platform run archived, ready for diff comparison.

**Inputs**: Local artifacts, platform run archive, diff report.

| Step | Action | Done |
|------|--------|------|
| 4.1 | Load local `metrics.json` from artifacts | [ ] |
| 4.2 | Load platform `metrics.json` from run archive | [ ] |
| 4.3 | Verify `period.start_date` and `period.end_date` match | [ ] |
| 4.4 | Compare `returns.total_return` within 2% tolerance | [ ] |
| 4.5 | Compare `risk.max_drawdown` within 3% tolerance | [ ] |
| 4.6 | Compare `ratios.sharpe_ratio` within 0.2 tolerance | [ ] |
| 4.7 | Compare `trade_stats.win_rate` within 5% tolerance | [ ] |
| 4.8 | Check trade count match (exact) | [ ] |
| 4.9 | Check NAV correlation > 0.95 | [ ] |
| 4.10 | Generate diff report under `platform/diff_reports/<strategy_id>/<version>/<run_date>__<local_run_id>.md` | [ ] |
| 4.11 | Categorize divergence: `trivial`, `data_source`, `timing`, `parameter`, `implementation`, `critical` | [ ] |
| 4.12 | If `implementation` or `critical`: create bug report | [ ] |
| 4.13 | Set `diff_status` in `strategy_card.validation`: `consistent`, `divergent`, or `pending` | [ ] |
| 4.14 | Record platform run in `strategy_card.validation.platform_runs` | [ ] |

**Exit Criteria**: Diff report generated, divergence categorized, `diff_status` updated.

---

## 5. Promotion or Rollback Checklist

**Trigger**: Diff comparison complete, ready to decide iteration outcome.

**Inputs**: Strategy card, iteration record, diff report.

### 5A. Promotion Checklist

| Step | Action | Done |
|------|--------|------|
| 5A.1 | Confirm `diff_status = consistent` or justify `skipped` | [ ] |
| 5A.2 | Confirm `key_metrics` complete: sharpe, annual_return, max_drawdown, turnover | [ ] |
| 5A.3 | Check against `performance_targets` in strategy card | [ ] |
| 5A.4 | Create iteration record in `governance/iteration_registry/<strategy_id>__iterations.yaml` | [ ] |
| 5A.5 | Set `decision = promote` | [ ] |
| 5A.6 | Update `strategy_card.meta.version` to current version | [ ] |
| 5A.7 | Update `strategy_card.meta.state`: `candidate` -> `validated` -> `production_ready` | [ ] |
| 5A.8 | Add entry to `strategy_card.changelog` | [ ] |
| 5A.9 | Document outcome in `notes` | [ ] |
| 5A.10 | If `production_ready`: freeze task spec, archive final version | [ ] |

**Exit Criteria**: Iteration record created, strategy card updated, state advanced.

### 5B. Rollback Checklist

| Step | Action | Done |
|------|--------|------|
| 5B.1 | Identify reason for rollback: performance degradation or divergence | [ ] |
| 5B.2 | Create iteration record with `decision = rollback` | [ ] |
| 5B.3 | Document degradation in `key_metrics` comparison | [ ] |
| 5B.4 | Restore previous version parameters in strategy card | [ ] |
| 5B.5 | Add rollback entry to `strategy_card.changelog` | [ ] |
| 5B.6 | If divergence is `critical`: create bug ticket, do not promote | [ ] |
| 5B.7 | Set `meta.version` to rolled-back version | [ ] |
| 5B.8 | Document reason in `notes` | [ ] |

**Exit Criteria**: Rollback documented, previous version restored, changelog updated.

### 5C. Retirement Checklist

| Step | Action | Done |
|------|--------|------|
| 5C.1 | Identify reason for retirement: thesis invalidated, persistent failure, or obsolescence | [ ] |
| 5C.2 | Create iteration record with `decision = retire` | [ ] |
| 5C.3 | Set `meta.state = retired` | [ ] |
| 5C.4 | Document reason in `notes` | [ ] |
| 5C.5 | Archive final state in strategy card | [ ] |

**Exit Criteria**: Strategy retired, reason documented, no further iterations.

---

## Quick Reference: State Transitions

```
idea -> candidate -> validated -> production_ready -> retired
  |        |            |              |
  v        v            v              v
retired  retired      retired        (end)
```

| State | Required |
|-------|----------|
| `idea` | Strategy card created, schema valid |
| `candidate` | Task spec frozen, local run complete |
| `validated` | JoinQuant run archived, diff consistent |
| `production_ready` | Passed review, approved for production |
| `retired` | Documented reason, archived |

---

## Quick Reference: One Change Per Iteration

Per operating model, each iteration changes only one of:

1. `pipeline.top_n` or `pipeline.weight_mode`
2. `portfolio` constraints (`max_single`, `cash_target`)
3. `risk` parameters (`max_industry`, `max_turnover`)
4. `data` date range (different validation slice)
5. `backtest.initial_cash` or `backtest.benchmark`

Major changes (new signals, template change) require major version bump.