# Architecture

## Goal

Build one integrated workbench for high-quality A-share strategy R&D on top of JoinQuant.

The workbench focuses on:

1. knowledge capture
2. strategy specification
3. standardized research runs
4. JoinQuant validation
5. disciplined iteration and promotion

## Non-goals

The mainline does not:

1. build a new base data platform
2. build a new generic backtest framework
3. keep multiple competing execution cores alive

## Mainline Decision

The project mainline is:

`jq_workbench/` + `strategy_kits/` + JoinQuant platform validation

Existing repository roles:

1. `strategy_kits/`: keep as the execution and contract core for task spec, panel adaptation, artifact generation, and local smoke checks
2. `ml_quant_framework/data/jqdata.py`: keep as the reference implementation for real `jqdata` and `jqfactor` integration
3. `strategy_to_factor_pipeline/`: keep as a source extraction and structuring utility
4. `universal_mechanisms/`: keep as reusable mechanism references
5. `quant_framework/`, `rotation_strategy_framework/`, `signal_pipeline/`, `unified_quant_pipeline/`: downgrade to reference implementations, not future product mainline

## Layered Framework

### 1. Knowledge Layer

What we know about strategies, mechanisms, market regimes, and failure cases.

Directory:

`knowledge/`

### 2. Research Specification Layer

What a strategy is in a structured form before execution.

Core objects:

1. `strategy_card`
2. `task_spec`
3. `pool_panel` / `score_panel` / `prediction_frame`
4. `jq_strategy.py`

Directory:

`research/`

### 3. Platform Validation Layer

The authoritative validation loop on JoinQuant.

Core actions:

1. submit strategy
2. fetch run results
3. normalize metrics and trades
4. compare local and platform outputs

Directory:

`platform/`

### 4. Governance Layer

How versions are promoted or rolled back.

Core objects:

1. iteration registry
2. standards and schemas
3. promotion decisions
4. agent prompt library

Directory:

`governance/`

## Directory Tree

```text
jq_workbench/
  docs/
  knowledge/
    strategy_cards/
    source_strategies/
    mechanisms/
    reviews/
  research/
    task_specs/
    panels/
    jq_strategies/
    experiments/
  platform/
    jq_executor/
    run_archive/
    diff_reports/
  governance/
    iteration_registry/
    standards/
    prompt_templates/
```

## Core Flow

1. Import or summarize a strategy into a `strategy_card`
2. Produce a `pool_panel` or `score_panel`
3. Freeze a `task_spec`
4. Generate or update `jq_strategy.py`
5. Run local contract checks through `strategy_kits`
6. Submit to JoinQuant
7. Fetch results into `run_archive`
8. Write a diff report and iteration decision
9. Promote or roll back one change at a time

## Standard Artifacts

Each strategy iteration should produce:

1. `strategy_card.yaml`
2. `task_spec.json`
3. `pool_panel.csv` or `score_panel.csv`
4. `jq_strategy.py`
5. `run_report.md`
6. `metrics.json`
7. `trades.csv`
8. `decision.md`

## Naming Rules

1. Strategy id: `snake_case`
2. Version: `v1.0`, `v1.1`, `v1.2`
3. One strategy, one card, one registry entry
4. One experiment, one change point
5. Platform run directories should be date-stamped

## Quality Gate

A strategy can be considered promotion-ready only after:

1. schema-valid inputs
2. reproducible task spec
3. JoinQuant result archived
4. diff report written
5. explicit keep or rollback decision recorded
