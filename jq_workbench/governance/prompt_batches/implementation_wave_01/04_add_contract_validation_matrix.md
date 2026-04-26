Append this after the shared dispatch header.

Goal:
Create a single validation matrix showing where each contract is enforced.

Write scope:
1. `jq_workbench/docs/validation_matrix.md`

Inputs:
1. `jq_workbench/governance/standards/*.md`
2. `strategy_kits/orchestration/task_schema.py`
3. `strategy_kits/contracts/dataframe_contracts.py`
4. `strategy_kits/integrations/factorhub/contracts.py`
5. `strategy_kits/orchestration/artifact_contracts.py`

Work:
1. map each contract to schema layer, runtime layer, archive layer, and governance layer
2. list current enforcement points and missing enforcement

Do not:
1. edit existing standards
2. write implementation code

Done when:
1. the matrix makes gaps obvious enough to prioritize future coding work
