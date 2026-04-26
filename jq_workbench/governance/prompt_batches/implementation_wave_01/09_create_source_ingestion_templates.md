Append this after the shared dispatch header.

Goal:
Create templates for ingesting raw historical strategies into the knowledge layer.

Write scope:
1. `jq_workbench/knowledge/source_strategies/intake_template.md`
2. `jq_workbench/knowledge/source_strategies/source_catalog.csv`
3. `jq_workbench/knowledge/source_strategies/README.md`

Inputs:
1. `jq_workbench/knowledge/source_strategies/README.md`
2. `strategy_to_factor_pipeline/README.md`

Work:
1. define a raw strategy intake template
2. create a source catalog CSV header
3. update README with ingestion steps and linkage rules

Do not:
1. parse all legacy strategies
2. change strategy card schema

Done when:
1. an operator can ingest one old strategy in a repeatable way
