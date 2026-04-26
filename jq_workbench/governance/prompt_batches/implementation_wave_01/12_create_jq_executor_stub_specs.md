Append this after the shared dispatch header.

Goal:
Write stub-level interface specs for the future JoinQuant executor.

Write scope:
1. `jq_workbench/platform/jq_executor/interfaces.md`

Inputs:
1. `jq_workbench/platform/jq_executor/file_layout.md`
2. `jq_workbench/docs/jq_execution_flow.md`

Work:
1. define function names, inputs, outputs, and error semantics for submit, poll, fetch, normalize, and archive operations
2. keep it language-agnostic but implementation-friendly

Do not:
1. write Python code
2. define UI workflows

Done when:
1. an implementer can translate the interface spec directly into code modules
