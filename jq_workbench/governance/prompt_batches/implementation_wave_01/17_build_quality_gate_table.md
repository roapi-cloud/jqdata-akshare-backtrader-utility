Append this after the shared dispatch header.

Goal:
Turn abstract quality gates into a concrete acceptance table.

Write scope:
1. `jq_workbench/docs/quality_gate_table.md`

Inputs:
1. `jq_workbench/docs/architecture.md`
2. `jq_workbench/docs/strategy_lifecycle_handbook.md`
3. `jq_workbench/docs/checklists.md`

Work:
1. define gates for idea, candidate, validated, and production_ready
2. list objective evidence required at each state

Do not:
1. change lifecycle state names
2. define new artifact contracts

Done when:
1. team members can decide promotion status with minimal ambiguity
