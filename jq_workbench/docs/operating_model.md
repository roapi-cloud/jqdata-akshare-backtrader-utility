# Operating Model

## One Strategy Lifecycle

1. Create `knowledge/strategy_cards/<strategy_id>.yaml`
2. Save raw source script or link under `knowledge/source_strategies/`
3. Prepare research input panel under `research/panels/`
4. Freeze `research/task_specs/<strategy_id>__<version>.json`
5. Generate or update `research/jq_strategies/<strategy_id>__<version>.py`
6. Run local validation through `strategy_kits`
7. Submit to JoinQuant through `platform/jq_executor/`
8. Archive fetched outputs under `platform/run_archive/`
9. Write platform diff under `platform/diff_reports/`
10. Record decision in `governance/iteration_registry/`

## Change Discipline

Every iteration changes only one of:

1. stock universe rule
2. factor or score composition
3. timing or regime control
4. portfolio sizing rule
5. risk filter or exit rule

## Promotion States

Suggested states:

1. `idea`
2. `candidate`
3. `validated`
4. `production_ready`
5. `retired`

## Main Working Rule

JoinQuant is the authority for final validation. Local runs exist to standardize inputs, reduce integration mistakes, and speed up iteration.
