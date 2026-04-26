# Diff Reports

Store local-vs-platform comparison reports here. Each report answers whether the local run matches the JoinQuant platform run and informs keep or rollback decisions.

## Directory Structure

```
diff_reports/
  <strategy_id>/
    <version>/
      <run_date>__<local_run_id>.md
```

### Example

```
diff_reports/
  value_quality_momentum/
    v1.0/
      2026-04-22__vqm_20260422_local_001.md
```

## File Naming

| Element | Format | Example |
|---------|--------|---------|
| strategy_id | snake_case | `value_quality_momentum` |
| version | semver | `v1.0` |
| run_date | ISO date | `2026-04-22` |
| local_run_id | From task_spec.task_id | `vqm_20260422_local_001` |

File name: `<run_date>__<local_run_id>.md`

## Report Template

```markdown
# Diff Report: <strategy_id> <version>

**Run Date**: YYYY-MM-DD
**Local Run ID**: <local_run_id>
**Platform Run ID**: <platform_run_id>
**Report Date**: YYYY-MM-DD

---

## Executive Summary

| Metric | Local | Platform | Delta | Acceptable? |
|--------|-------|----------|-------|-------------|
| Total Return | X.XX% | X.XX% | +/-X.XX% | yes/no |
| Sharpe Ratio | X.XX | X.XX | +/-X.XX | yes/no |
| Max Drawdown | X.XX% | X.XX% | +/-X.XX | yes/no |
| Win Rate | X.XX% | X.XX% | +/-X.XX | yes/no |
| Turnover | X.XX | X.XX | +/-X.XX | yes/no |

## Decision

**Recommendation**: keep | rollback | investigate

**Rationale**: <one-sentence reason>

---

## Detailed Comparison

### Returns Alignment

| Period | Local NAV | Platform NAV | Diff | Notes |
|--------|-----------|--------------|------|-------|
| ... | ... | ... | ... | ... |

### Trade Alignment

| Metric | Local | Platform | Match? |
|--------|-------|----------|--------|
| Total Trades | N | N | yes/no |
| Trade Date Match | N% | - | yes/no |
| Symbol Match | N% | - | yes/no |
| Price Deviation | +/-X% | - | yes/no |

### Position Alignment

| Date | Local Positions | Platform Positions | Match? |
|------|-----------------|--------------------|-------|
| ... | N | N | yes/no |

---

## Divergence Analysis

### What Changed

<Describe the single change point for this iteration>

### Root Cause

<Possible causes of divergence>

1. **Cause**: <description>
   **Likelihood**: high | medium | low
   **Evidence**: <data or observation>

2. **Cause**: <description>
   **Likelihood**: high | medium | low
   **Evidence**: <data or observation>

### Acceptability Thresholds

| Metric | Threshold | Actual | Pass? |
|--------|-----------|--------|-------|
| Return Delta | < 2% | X.XX% | yes/no |
| Sharpe Delta | < 0.2 | X.XX | yes/no |
| Max DD Delta | < 3% | X.XX% | yes/no |
| Trade Match | > 90% | X.XX% | yes/no |

---

## Artifacts Compared

| Artifact | Local Path (Normalized) | Platform Path |
|----------|-------------------------|---------------|
| metrics | ./artifacts/<local>/metrics.json | run_archive/<strategy>/<ver>/<date>/metrics.json |
| trades | ./artifacts/<local>/trades.csv | run_archive/<strategy>/<ver>/<date>/trades.csv |
| nav | ./artifacts/<local>/nav.csv | run_archive/<strategy>/<ver>/<date>/nav.csv |

Note: Local raw files (`metrics.csv`, `nav_series.csv`) are normalized to contract format before comparison. See `run_artifact_contract.md` naming convention.

---

## Resolution

**Action**: keep | rollback | re-run

**Next Steps**:
- [ ] Update strategy_card changelog
- [ ] Update iteration_registry
- [ ] Promote to next state (if keep)
- [ ] Revert to previous version (if rollback)
- [ ] Investigate divergence (if re-run)

---

## Notes

<Additional observations, context, or follow-ups>
```

## Report Sections

### Executive Summary

High-level comparison of key metrics. Must include delta calculation and acceptability judgment.

### Decision

Single recommendation with rationale. Options:

| Decision | When to Use |
|----------|-------------|
| `keep` | Divergence within acceptable thresholds |
| `rollback` | Material divergence requiring revert |
| `investigate` | Inconclusive, needs deeper analysis |

### Detailed Comparison

Quantitative comparison of:

1. Returns alignment (NAV series)
2. Trade alignment (dates, symbols, prices)
3. Position alignment (holdings over time)

### Divergence Analysis

Root cause analysis of any differences. Focus on:

1. Data source differences (local vs JQ data)
2. Timing differences (execution timing, price differences)
3. Parameter differences (slippage, commission models)
4. Implementation differences (logic bugs)

### Resolution

Concrete next steps linking to governance workflow.

## Quality Gate

Before signing off a diff report:

- [ ] Executive summary filled
- [ ] Decision stated with rationale
- [ ] All comparison tables complete
- [ ] Divergence analysis includes root cause hypotheses
- [ ] Acceptability thresholds defined
- [ ] Resolution action specified
- [ ] Artifacts paths linked

## Acceptability Thresholds (Default)

| Metric | Default Threshold |
|--------|-------------------|
| Total Return Delta | < 2% |
| Annual Return Delta | < 1% |
| Sharpe Delta | < 0.2 |
| Max DD Delta | < 3% |
| Trade Match Rate | > 90% |
| NAV Correlation | > 0.95 |

Adjust per strategy based on `thesis.alpha_type` and `performance_targets`.

## Integration Points

1. **Input**: Local artifacts from `strategy_kits`, platform artifacts from `run_archive`
2. **Output**: Decision feeds into `iteration_registry` and `strategy_card.changelog`
3. **Trigger**: After each JoinQuant run fetch

## Related

- `governance/standards/run_artifact_contract.md` for comparison baseline
- `platform/run_archive/` for platform artifact schema
- `governance/iteration_registry/` for decision recording