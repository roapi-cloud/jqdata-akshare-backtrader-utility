# Task Specs

Frozen, reproducible experiment inputs for strategy execution.

## Directory Location

```
jq_workbench/research/task_specs/
```

## Naming Convention

File naming pattern:

```
<strategy_id>__<version>.json
```

Examples:

| File | Meaning |
|------|---------|
| `value_quality_momentum__v1.0.json` | Initial version of value_quality_momentum strategy |
| `value_quality_momentum__v1.1.json` | Second iteration, one parameter changed |
| `small_cap_rotate__v1.0.json` | Initial version of small_cap_rotate strategy |
| `etf_weekly_rotation__v2.3.json` | Third iteration of second major version |

## Naming Rules

1. **strategy_id**: Must match `meta.strategy_id` in the associated `strategy_card.yaml`
2. **version**: Semver format (`v1.0`, `v1.1`, `v2.0`), must match `meta.version` in strategy_card
3. **Separator**: Double underscore `__` between strategy_id and version
4. **Extension**: `.json` (YAML `.yaml` also supported by strategy_kits CLI)

## Version Increment Guidance

| Change Type | Version Increment |
|-------------|-------------------|
| New strategy | `v1.0` |
| Parameter tuning (top_n, weights) | `v1.1`, `v1.2`... |
| Different backtest period | `v1.1`, `v1.2`... |
| Risk/portfolio constraint change | `v1.1`, `v1.2`... |
| New panel version (different signals) | `v2.0` (major change) |
| Template change | `v2.0` (major change) |

## File Contents

Each task_spec is a JSON file validated by `strategy_kits/orchestration/task_schema.py`.

Required sections:

1. `task`: task_id, strategy_name
2. `data`: panel_type, start_date, end_date, panel_path (conditional)
3. `backtest`: template, initial_cash

Optional sections with defaults:

1. `pipeline`: top_n, score_method, weight_mode
2. `portfolio`: max_positions, max_single, cash_target
3. `risk`: enable_constraints, max_industry, max_turnover
4. `output`: save_artifacts, artifact_dir

See `governance/standards/task_spec_profile.md` for full schema.

## Associated Files

Each task spec should reference:

| Association | Location | Example |
|-------------|----------|---------|
| Strategy card | `knowledge/strategy_cards/<strategy_id>.yaml` | `value_quality_momentum.yaml` |
| Input panel | `research/panels/<strategy_id>__<version>.csv` | `value_quality_momentum__v1.0.csv` |
| JQ strategy | `research/jq_strategies/<strategy_id>__<version>.py` | `value_quality_momentum__v1.0.py` |

## Workflow

### Creating a Task Spec

1. Start from a validated `strategy_card` in `knowledge/strategy_cards/`
2. Generate the input panel in `research/panels/`
3. Create `task_spec.json` with:
   - `task_id`: `<strategy_id>__<version>__<run_suffix>` (optional run suffix for multiple runs)
   - `data.panel_path`: absolute path to the panel file
   - Parameters derived from strategy_card fields (see mapping in `task_spec_profile.md`)
4. Save as `<strategy_id>__<version>.json`

### Running a Task Spec

```bash
python -m strategy_kits.orchestration.cli \
  --spec /abs/path/jq_workbench/research/task_specs/value_quality_momentum__v1.0.json
```

Or with JSON output:

```bash
python -m strategy_kits.orchestration.cli \
  --spec /abs/path/task_spec.json \
  --print-result-json
```

Note: Use `python3` if `python` is not available.

### After a Run

1. Check `artifacts/<task_id>/<timestamp>/` for output files
2. Review `run_report.md` for summary
3. If submitting to JoinQuant, use the associated `jq_strategies/<strategy_id>__<version>.py`

## Storage Structure

```
jq_workbench/research/task_specs/
  value_quality_momentum__v1.0.json
  value_quality_momentum__v1.1.json
  value_quality_momentum__v2.0.json
  small_cap_rotate__v1.0.json
  etf_weekly_rotation__v1.0.json
  ...
```

## Reproducibility Checklist

Before freezing a task spec:

- [ ] All required fields populated
- [ ] `panel_path` is absolute path to an existing file
- [ ] `task_id` is unique and follows naming convention
- [ ] Version matches the strategy_card version
- [ ] No placeholder values (e.g., `"TODO"`, `null` for required fields)
- [ ] Dates are valid and `start_date < end_date`

## Multiple Runs per Version

For multiple runs with the same version (e.g., different validation slices), use a run suffix in `task.task_id`:

```json
{
  "task": {
    "task_id": "value_quality_momentum__v1.0__slice_2018_2020",
    "strategy_name": "value_quality_momentum"
  },
  ...
}
```

The file name remains `<strategy_id>__<version>.json`. The run suffix is internal to task_id and distinguishes artifacts in the output directory.

## Cross-References

| Document | Purpose |
|----------|---------|
| `governance/standards/task_spec_profile.md` | Full schema and field mapping |
| `governance/standards/strategy_card_schema.md` | Source strategy definition |
| `research/panels/README.md` | Panel storage and naming |
| `strategy_kits/SKILL.md` | Execution layer documentation |
| `docs/operating_model.md` | Full lifecycle workflow |