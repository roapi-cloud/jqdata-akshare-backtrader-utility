# Strategy Lifecycle Handbook

## Overview

This handbook defines the lifecycle from idea to production-ready strategy in this JoinQuant-first workbench. Follow these stages, checkpoints, and gates without oral explanation.

## Lifecycle States

| State | Definition | Entry Requirement |
|-------|------------|-------------------|
| `idea` | Initial concept, no validation | Strategy card created with required fields |
| `candidate` | Has task_spec and local runs | Local `strategy_kits` run completed |
| `validated` | JoinQuant platform validation passed | Platform run archived with `diff_status: consistent` |
| `production_ready` | Passed review, approved for production | Diff report reviewed, `decision: promote` |
| `retired` | No longer in use | Reason documented in strategy_card notes |

---

## Stage 1: Idea to Candidate

### Entry Criteria

| Criterion | Evidence Required |
|-----------|-------------------|
| Strategy thesis defined | `strategy_card.yaml` with `thesis.summary` and `thesis.alpha_type` |
| Universe specified | `strategy_card.yaml` with `universe.base_pool` and filters |
| Signals listed | `strategy_card.yaml` with at least one `signals.factors` entry |
| Rebalance rules set | `strategy_card.yaml` with `rebalance.frequency`, `top_n`, `weight_method` |
| Dependencies declared | `strategy_card.yaml` with explicit `dependencies.jqdata` and `dependencies.jqfactor` |

### Review Checkpoint: Strategy Card Validation

| Check | Action |
|-------|--------|
| Schema valid | Run schema validation per `strategy_card_schema.md` |
| Required fields complete | Verify all fields in `strategy_card_schema.md` Required Fields table |
| Naming convention | `strategy_id`: snake_case; version: `v1.0` |
| Failure modes documented | At least one entry in `failure_modes` (recommended) |

### Deliverables

```
jq_workbench/knowledge/strategy_cards/<strategy_id>.yaml
jq_workbench/knowledge/source_strategies/<strategy_id>_source.py (or link)
```

### Promotion Gate: Idea → Candidate

| Gate | Requirement | Verification |
|------|-------------|--------------|
| Card complete | All required fields present | Schema validation pass |
| Task spec frozen | `research/task_specs/<strategy_id>__v1.0.json` exists | File present, schema valid |
| Panel generated | `research/panels/<strategy_id>__v1.0__*.csv` exists | Non-empty CSV with required columns |
| Local run completed | `strategy_kits` execution artifacts exist | Artifacts directory present with `run_report.json` |

---

## Stage 2: Candidate to Validated

### Entry Criteria

| Criterion | Evidence Required |
|-----------|-------------------|
| Local artifacts present | `artifacts/<task_id>/<timestamp>/` with all standard artifacts |
| Task spec matches card | `task_spec` parameters derived from `strategy_card` fields |
| No contract errors | `run_report.json` shows no contract violations |

### Review Checkpoint: Local Run Review

| Check | Action |
|-------|--------|
| Artifacts complete | Verify: `task_spec.json`, `prediction_frame.csv`, `nav_series.csv`, `metrics.csv`, `trades.csv`, `run_report.md` |
| Metrics sensible | Sharpe > 0, max_drawdown < 50%, turnover within target |
| Trades match logic | Trade count consistent with `hold_days` and `top_n` |

### JoinQuant Submission Checklist

Before submitting, confirm:

- [ ] `task_spec.json` schema valid
- [ ] `jq_strategy.py` exists in `research/jq_strategies/<strategy_id>__v1.0.py`
- [ ] Panel file exists at `data.panel_path`
- [ ] Local run completed (smoke check)
- [ ] No contract errors in local artifacts

### Validation Requirements

| Requirement | Evidence |
|-------------|----------|
| Platform run completed | Status: `completed` in JoinQuant |
| Results fetched | 5 archived files: `metrics.json`, `trades.csv`, `nav.csv`, `platform_meta.json`, `run_report.md` |
| Results archived | Files stored in `run_archive/<strategy_id>/<version>/<run_date>/` |
| Diff comparison done | `diff_reports/<strategy_id>/<version>/<date>__<local_run_id>.md` exists |

### Promotion Gate: Candidate → Validated

| Gate | Requirement | Verification |
|------|-------------|--------------|
| Platform run archived | `run_archive/<strategy_id>/v1.0/<YYYY-MM-DD>/` exists | Directory and files present |
| Diff status consistent | `strategy_card.validation.diff_status: consistent` | Metrics within default tolerance (Sharpe < 0.2 delta, Return < 2% delta) |
| Key metrics recorded | `validation.platform_runs` entry with sharpe, max_dd | Values present and reasonable |

---

## Stage 3: Validated to Production Ready

### Entry Criteria

| Criterion | Evidence Required |
|-----------|-------------------|
| Diff consistent | `strategy_card.validation.diff_status: consistent` |
| Metrics acceptable | Sharpe ≥ target, max_drawdown ≤ target (per `performance_targets`) |
| Failure modes confirmed | No triggered failure conditions in validation period |

### Review Checkpoint: Diff Report Review

| Check | Action |
|-------|--------|
| Local vs platform match | Review `diff_reports/<strategy_id>/v1.0/<date>__<local_run_id>.md` |
| No anomalies | Check notes section for runtime errors or data gaps |
| Trade alignment | Trade dates and counts match between local and platform |

### Iteration Registry Entry

Create entry in `governance/iteration_registry/<strategy_id>__iterations.yaml`:

```yaml
- iteration_id: <strategy_id>__v1.0
  version: v1.0
  hypothesis: "Base version"
  change_point: "initial implementation"
  task_spec_id: <strategy_id>__v1.0
  jq_run_id: <algorithm_id>
  local_run_id: <run_id>
  key_metrics:
    sharpe: <value>
    annual_return: <value>
    max_drawdown: <value>
    turnover: <value>
  diff_outcome: consistent
  decision: promote
```

### Promotion Gate: Validated → Production Ready

| Gate | Requirement | Verification |
|------|-------------|--------------|
| Diff reviewed | Diff report analyzed, no divergent findings | Reviewer sign-off in `notes` |
| Decision recorded | `decision: promote` in iteration_registry | Registry entry exists |
| State updated | `strategy_card.meta.state: production_ready` | YAML updated |
| Changelog updated | `strategy_card.changelog` entry with decision | Version history documented |

---

## Change Discipline

Each iteration changes **only one** of:

| Change Type | task_spec Field | Version Increment |
|-------------|-----------------|-------------------|
| Stock count | `pipeline.top_n` | `v1.1` |
| Weighting | `pipeline.weight_mode` | `v1.1` |
| Position constraint | `portfolio.max_single` | `v1.1` |
| Sector constraint | `risk.max_industry` | `v1.1` |
| Turnover limit | `risk.max_turnover` | `v1.1` |
| Validation slice | `data.start_date`, `data.end_date` | `v1.1` |
| New signals (panel change) | `data.panel_path` | `v2.0` (major) |
| Template change | `backtest.template` | `v2.0` (major) |

---

## Rollback Protocol

When a version fails promotion:

1. Set `decision: rollback` in iteration_registry
2. Restore previous version's parameters in strategy_card
3. Create rollback iteration record: `change_point: "rollback from v1.x"`
4. Document reason in `notes`
5. Set `decision: promote` only after confirming restoration

---

## Quality Gates Summary

### Gate 1: Idea → Candidate

- [ ] strategy_card schema valid
- [ ] task_spec frozen and valid
- [ ] panel generated
- [ ] local run completed

### Gate 2: Candidate → Validated

- [ ] platform run archived
- [ ] diff_status: consistent
- [ ] key metrics recorded

### Gate 3: Validated → Production Ready

- [ ] diff report reviewed
- [ ] iteration_registry decision: promote
- [ ] strategy_card state: production_ready
- [ ] changelog updated

---

## File Traceability Map

| Lifecycle Stage | Files Created/Updated |
|-----------------|----------------------|
| Idea | `strategy_cards/<strategy_id>.yaml` |
| Candidate | `task_specs/<strategy_id>__v1.0.json`, `panels/<strategy_id>__v1.0__*.csv`, `artifacts/<task_id>/` |
| Validated | `run_archive/<strategy_id>/v1.0/<YYYY-MM-DD>/`, `diff_reports/<strategy_id>/v1.0/<date>__<local_run_id>.md` |
| Production Ready | `iteration_registry/<strategy_id>__iterations.yaml`, updated `strategy_card.yaml` |

---

## References

| Document | Purpose |
|----------|---------|
| `architecture.md` | Layered framework overview |
| `operating_model.md` | Workflow summary |
| `strategy_card_schema.md` | Card field definitions |
| `task_spec_profile.md` | Task spec schema and mapping |
| `iteration_registry/README.md` | Iteration record schema |
| `jq_execution_flow.md` | Platform submission lifecycle |