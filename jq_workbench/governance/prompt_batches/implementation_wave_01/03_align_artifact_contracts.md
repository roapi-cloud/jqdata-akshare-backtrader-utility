Append this after the shared dispatch header.

Goal:
Make the local artifact story and canonical artifact story coherent.

Write scope:
1. `jq_workbench/governance/standards/run_artifact_contract.md`
2. `jq_workbench/platform/run_archive/README.md`
3. `jq_workbench/platform/diff_reports/README.md`

Inputs:
1. `strategy_kits/orchestration/artifact_contracts.py`
2. `strategy_kits/orchestration/artifacts.py`
3. `jq_workbench/governance/standards/run_artifact_contract.md`

Work:
1. distinguish raw local files from normalized comparison files
2. state who performs normalization and where it should land
3. define the minimum archive layout for platform runs

Do not:
1. change markdown files outside this scope
2. invent unsupported local artifact names

Done when:
1. a future implementer knows exactly how to normalize local runs into the canonical archive contract
