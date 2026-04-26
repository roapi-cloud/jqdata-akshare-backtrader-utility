Append this after the shared dispatch header.

Goal:
Create example task specs paired with the first strategy cards.

Write scope:
1. `jq_workbench/research/task_specs/value_quality_dividend__v1.0.json`
2. `jq_workbench/research/task_specs/small_cap_multi_factor__v1.0.json`
3. `jq_workbench/research/task_specs/etf_rotation_rsrs__v1.0.json`

Inputs:
1. `jq_workbench/governance/standards/task_spec_profile.md`
2. `jq_workbench/knowledge/strategy_cards/*.yaml`
3. `strategy_kits/orchestration/task_schema.py`

Work:
1. create three concrete examples that match current validator semantics
2. keep naming and artifact directories consistent

Do not:
1. create fake platform run ids
2. edit Python code

Done when:
1. each example is internally consistent and executable after panels exist
