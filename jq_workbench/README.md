# JQ Workbench

JoinQuant-first A-share strategy R&D workbench.

This directory is the new project mainline. It does not rebuild data infrastructure or a generic backtest engine. It standardizes:

1. strategy knowledge capture
2. strategy research inputs and task specs
3. JoinQuant submission and result collection
4. iteration governance and promotion decisions

Primary execution core:

1. `strategy_kits/` stays as the local orchestration and contract layer
2. `ml_quant_framework/data/jqdata.py` is the reference for real JQData and `jqfactor` access
3. `strategy_to_factor_pipeline/` is downgraded to an extraction tool, not the product mainline

Top-level map:

1. `docs/`: architecture, workflow, parallel task templates
2. `knowledge/`: strategy cards, raw source strategies, reusable mechanisms, review notes
3. `research/`: task specs, panels, generated JoinQuant scripts, experiments
4. `platform/`: JoinQuant execution, run archive, diff reports
5. `governance/`: standards, iteration registry, prompt templates

Start here:

1. `docs/architecture.md`
2. `docs/operating_model.md`
3. `docs/parallel_agent_tasks.md`
