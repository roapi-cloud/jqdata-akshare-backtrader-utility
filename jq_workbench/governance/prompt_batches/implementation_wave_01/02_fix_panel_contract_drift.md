Append this after the shared dispatch header.

Goal:
Bring panel contract docs in line with current validators and remove ambiguous statements.

Write scope:
1. `jq_workbench/governance/standards/panel_contracts.md`

Inputs:
1. `strategy_kits/contracts/dataframe_contracts.py`
2. `strategy_kits/integrations/factorhub/contracts.py`

Work:
1. separate base validator guarantees from stronger factorhub validator guarantees
2. rewrite any misleading lines about suffix stripping, NaN checks, rank behavior, and weight defaults
3. add a short “current guarantees vs future desired guarantees” section

Do not:
1. change any Python validator
2. modify task spec docs

Done when:
1. a reader can tell exactly what is guaranteed today
2. no statement over-promises current implementation
