# Parallel Agent Tasks

These prompts are designed for parallel execution. Each task owns a narrow write scope.

## Task 01

### Goal

Define the `strategy_card` schema for the workbench.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/governance/standards/strategy_card_schema.md`
2. optional example file under `jq_workbench/knowledge/strategy_cards/`

Task:

Design a `strategy_card` schema for a JoinQuant-first A-share strategy workbench. The schema must cover thesis, universe, signals, rebalance, risk rules, market regime assumptions, failure modes, dependencies on `jqdata` or `jqfactor`, and version metadata.

Use the new `jq_workbench/` architecture as the mainline. Keep it compact and operational.

Deliverables:

1. schema doc
2. one filled example card for a simple strategy

Do not:

1. change `strategy_kits/`
2. build a generic factor platform
3. invent a second execution core

Done when:

1. fields are explicit
2. naming rules are clear
3. an example card can be copied into real use

## Task 02

### Goal

Define the `task_spec` standard for this workbench.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/governance/standards/task_spec_profile.md`
2. `jq_workbench/research/task_specs/README.md`

Task:

Adapt the existing `strategy_kits` task spec concept into a JoinQuant-first workbench standard. Document the required fields, optional fields, versioning rules, and the mapping between strategy card fields and task spec fields.

Deliverables:

1. task spec profile doc
2. README that explains how task specs are stored and named

Do not:

1. edit `strategy_kits/orchestration/`
2. design a new backtest engine

Done when:

1. one can create a task spec without guessing
2. mapping to existing `strategy_kits` fields is explicit

## Task 03

### Goal

Design panel standards for research inputs.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/governance/standards/panel_contracts.md`
2. `jq_workbench/research/panels/README.md`

Task:

Write the standard contracts for `pool_panel`, `score_panel`, and `prediction_frame` in this workbench. Include required columns, date and code normalization rules, naming conventions, and file naming examples.

Deliverables:

1. panel contract doc
2. storage README

Do not:

1. modify adapter code
2. design platform outputs

Done when:

1. contracts are precise
2. examples match the workbench naming system

## Task 04

### Goal

Specify the JoinQuant execution layer.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/platform/jq_executor/README.md`
2. `jq_workbench/docs/jq_execution_flow.md`

Task:

Design the JoinQuant execution layer for this workbench. Describe how a frozen task spec becomes a JoinQuant strategy file, how submission should work, how result fetching should work, and what normalized outputs must be archived.

Reference:

1. `ml_quant_framework/data/jqdata.py`
2. `strategy_kits/SKILL.md`

Deliverables:

1. executor README
2. flow doc with step-by-step lifecycle

Do not:

1. use AkShare as the mainline
2. build local backtest features

Done when:

1. execution responsibilities are explicit
2. archive outputs are clearly listed

## Task 05

### Goal

Define the run archive and diff report contracts.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/platform/run_archive/README.md`
2. `jq_workbench/platform/diff_reports/README.md`
3. `jq_workbench/governance/standards/run_artifact_contract.md`

Task:

Specify how JoinQuant run outputs should be archived and how local-vs-platform diff reports should be structured. Include directory naming, required files, summary fields, and a decision section.

Deliverables:

1. archive README
2. diff report README
3. artifact contract doc

Do not:

1. touch strategy card schema
2. define prompt libraries

Done when:

1. a run folder can be audited later
2. a diff report can support keep or rollback decisions

## Task 06

### Goal

Design the iteration registry.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/governance/iteration_registry/README.md`
2. `jq_workbench/governance/standards/iteration_registry_schema.md`

Task:

Create the workbench iteration registry design. It should track strategy id, version, hypothesis, single change point, task spec id, JoinQuant run id, key metrics, diff outcome, and decision.

Deliverables:

1. registry README
2. schema doc

Do not:

1. redefine panel contracts
2. modify executor docs

Done when:

1. each version can be traced end-to-end
2. rollback and promotion states are explicit

## Task 07

### Goal

Design the knowledge base indexing rules.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/knowledge/README.md`
2. `jq_workbench/knowledge/source_strategies/README.md`
3. `jq_workbench/knowledge/mechanisms/README.md`
4. `jq_workbench/knowledge/reviews/README.md`

Task:

Define how the knowledge base should store raw source strategies, reusable mechanisms, and review notes. Include indexing keys, minimum metadata, and how each item links back to a strategy card.

Deliverables:

1. one top-level knowledge README
2. three sub-README files with storage rules

Do not:

1. write strategy cards themselves
2. define runtime execution behavior

Done when:

1. a new source strategy can be ingested consistently
2. knowledge items can be linked to a card and a version

## Task 08

### Goal

Define prompt standards for future agents.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/governance/prompt_templates/README.md`
2. `jq_workbench/governance/standards/agent_prompt_style_guide.md`

Task:

Write a prompt style guide for future agents working in this workbench. Cover write-scope ownership, output contracts, naming rules, local vs JoinQuant authority, and the one-change-per-iteration rule.

Deliverables:

1. prompt template README
2. style guide

Do not:

1. define strategy card fields
2. define run archive fields

Done when:

1. future agent tasks can be assigned with low ambiguity
2. the style guide prevents overlapping edits

## Task 09

### Goal

Create a minimal strategy lifecycle handbook.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/docs/strategy_lifecycle_handbook.md`

Task:

Write a concise handbook that explains the lifecycle from idea to production-ready strategy in this JoinQuant-first workbench. It should define entry criteria, review checkpoints, validation requirements, and promotion gates.

Deliverables:

1. lifecycle handbook

Do not:

1. change directory README files
2. redefine the architecture

Done when:

1. a teammate can follow the lifecycle without oral explanation
2. promotion gates are concrete

## Task 10

### Goal

Produce the first operating checklist pack.

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Target write scope:

1. `jq_workbench/docs/checklists.md`

Task:

Write the first operating checklist pack for this workbench. Include:

1. new strategy intake checklist
2. task spec freeze checklist
3. JoinQuant submission checklist
4. result review checklist
5. promotion or rollback checklist

Deliverables:

1. one checklist doc

Do not:

1. introduce new schemas
2. touch executor or registry docs

Done when:

1. each checklist is short and actionable
2. the checklist pack matches the new workbench structure
