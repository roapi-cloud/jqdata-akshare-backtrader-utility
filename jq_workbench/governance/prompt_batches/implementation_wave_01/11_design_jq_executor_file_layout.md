Append this after the shared dispatch header.

Goal:
Turn the JoinQuant executor concept into a concrete file layout proposal.

Write scope:
1. `jq_workbench/platform/jq_executor/file_layout.md`
2. `jq_workbench/platform/jq_executor/README.md`

Inputs:
1. `jq_workbench/platform/jq_executor/README.md`
2. `jq_workbench/docs/jq_execution_flow.md`
3. `ml_quant_framework/data/jqdata.py`

Work:
1. define the proposed files for submit, poll, fetch, normalize, and archive
2. explain what each file should own

Do not:
1. implement the executor
2. change platform contracts

Done when:
1. coding agents can start implementation without redesigning ownership
