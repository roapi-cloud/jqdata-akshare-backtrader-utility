Append this after the shared dispatch header.

Goal:
Align `jq_workbench` task spec documentation with the real `strategy_kits` validator so future work does not propagate a false contract.

Write scope:
1. `jq_workbench/governance/standards/task_spec_profile.md`
2. `jq_workbench/docs/checklists.md`

Inputs:
1. `strategy_kits/orchestration/task_schema.py`
2. `strategy_kits/orchestration/task_runner.py`
3. `jq_workbench/governance/standards/task_spec_profile.md`

Work:
1. Correct any mismatch between documented required fields and actual validation behavior
2. Mark runtime-only requirements explicitly if they are enforced outside `validate_strategy_task_spec`
3. Tighten the checklist so it catches those gaps

Do not:
1. edit Python code
2. change panel contracts

Done when:
1. docs no longer claim a field is validator-enforced if it is only runtime-enforced
2. all cited behavior matches current code
