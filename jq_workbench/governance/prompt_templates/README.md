# Prompt Templates

This directory stores reusable prompts for assigning bounded work to agents.

## Usage

Every agent prompt must be prefixed with the shared dispatch header from `shared_dispatch_header.md`.

## Prompt Structure

Each prompt must define six sections:

### 1. Goal

One sentence stating what the prompt achieves.

Example:
```
### Goal
Define the strategy_card schema for the workbench.
```

### 2. Write Scope

Explicit list of files the agent is authorized to create or modify. No other files may be touched.

Example:
```
Target write scope:
1. jq_workbench/governance/standards/strategy_card_schema.md
2. jq_workbench/knowledge/strategy_cards/example.yaml
```

### 3. Task

Clear description of what to produce. Use bullet points for multiple deliverables.

Example:
```
Task:
Design a strategy_card schema for a JoinQuant-first A-share strategy workbench.
The schema must cover thesis, universe, signals, rebalance, risk rules, market regime
assumptions, failure modes, dependencies, and version metadata.
```

### 4. Deliverables

Numbered list of concrete outputs.

Example:
```
Deliverables:
1. schema doc
2. one filled example card
```

### 5. Non-goals

Explicit boundaries to prevent scope creep.

Example:
```
Do not:
1. change strategy_kits/
2. build a generic factor platform
3. invent a second execution core
```

### 6. Done Criteria

Conditions that signal completion.

Example:
```
Done when:
1. fields are explicit
2. naming rules are clear
3. an example card can be copied into real use
```

## Template File

```
## Task XX

### Goal

<one sentence>

### Prompt

You are working inside `/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility`.

Global constraints:
1. This project is a JoinQuant-first A-share strategy R&D workbench.
2. Do not build a new base data platform.
3. Do not build a new generic backtest framework.
4. Treat JoinQuant as the authoritative validation platform.
5. Treat strategy_kits as the local orchestration and contract core.
6. Only write inside the file paths assigned to you.
7. Do not edit files owned by other parallel tasks.
8. If you find a cross-task dependency or naming conflict, write it under a final section named "Conflicts And Recommendations".
9. Prefer concise, operational documents over broad theory.
10. If something is not confirmed from the repository context, say "Unconfirmed".

Output expectation:
1. Make the assigned files internally consistent.
2. Keep naming stable across all outputs.
3. End with a short completion note summarizing files changed and open conflicts.

Target write scope:

1. <file_path_1>
2. <file_path_2>

Task:

<description of work>

Deliverables:

1. <output_1>
2. <output_2>

Do not:

1. <boundary_1>
2. <boundary_2>

Done when:

1. <criterion_1>
2. <criterion_2>
```

## Principles

1. One prompt, one bounded task
2. Write scope must be explicit and limited
3. Non-goals prevent overlap with other agents
4. Done criteria must be objectively verifiable
5. Conflicts are surfaced, not silently resolved