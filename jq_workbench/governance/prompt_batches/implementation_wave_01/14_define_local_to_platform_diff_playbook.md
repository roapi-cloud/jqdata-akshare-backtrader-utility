Append this after the shared dispatch header.

Goal:
Create the first playbook for diagnosing local-vs-JoinQuant divergence.

Write scope:
1. `jq_workbench/platform/diff_reports/diff_playbook.md`

Inputs:
1. `jq_workbench/governance/standards/run_artifact_contract.md`
2. `jq_workbench/platform/diff_reports/README.md`

Work:
1. define a standard diagnosis order
2. separate data, timing, parameter, and implementation causes
3. include decision hints for keep, investigate, or rollback

Do not:
1. change tolerance values unless the docs already support it
2. invent new artifact files

Done when:
1. reviewers can investigate divergence consistently
