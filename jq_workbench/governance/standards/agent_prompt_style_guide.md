# Agent Prompt Style Guide

This guide defines standards for writing agent prompts in this workbench. Follow these rules to ensure parallel tasks can execute without conflict and outputs remain consistent.

## 1. Write-Scope Ownership

### Rule

Every prompt must declare an explicit write scope. The agent may only create or modify files listed in the write scope.

### Format

```
Target write scope:

1. path/to/file_a.md
2. path/to/file_b.yaml
```

### Enforcement

1. No glob patterns. Each file must be listed individually.
2. No implicit write permissions to "related" files.
3. Reading files outside write scope is allowed.
4. If a task needs to touch a file not in scope, flag it as a conflict.

### Scope Conflict Detection

Before accepting a prompt, check for overlap with other active tasks:

| Active Task | Write Scope | Your Task | Write Scope | Conflict? |
|-------------|-------------|-----------|-------------|-----------|
| Task 01 | standards/schema.md | Task 02 | standards/contracts.md | No |
| Task 01 | standards/schema.md | Task 02 | standards/schema.md | Yes |

If conflict exists, reassign one task or split the file.

## 2. Output Contracts

### Rule

Every deliverable must have an explicit output contract defining what the file contains and how it is structured.

### Required Elements

For documentation files:
1. Purpose statement
2. Required sections
3. Naming conventions for content

For schema/spec files:
1. Field names and types
2. Required vs optional fields
3. Validation rules

For code files:
1. Function signatures
2. Input/output types
3. Error handling expectations

### Example

```
Deliverables:

1. strategy_card_schema.md
   - Purpose: define the schema for strategy cards
   - Required sections: Schema, Required Fields, Naming Rules, State Transitions
   
2. value_quality_momentum.yaml
   - Purpose: example strategy card
   - Must validate against the schema
```

## 3. Naming Rules

### File Naming

| Object Type | Pattern | Example |
|-------------|---------|---------|
| Strategy card | `<strategy_id>.yaml` | `value_quality_momentum.yaml` |
| Task spec | `<strategy_id>__<version>.json` | `value_quality_momentum__v1.0.json` |
| Panel file | `<strategy_id>__<version>__<type>.csv` | `value_quality_momentum__v1.0__score.csv` |
| Run archive | `<YYYYMMDD>_<task_id>/` | `20250422_value_quality_momentum__v1.0__run001/` |
| Diff report | `<strategy_id>__<version>__diff.md` | `value_quality_momentum__v1.0__diff.md` |

### Internal Naming

1. Strategy ID: `snake_case`, lowercase, underscores only
2. Version: `v<MAJOR>.<MINOR>`, e.g., `v1.0`, `v1.1`, `v2.0`
3. Run ID: `<strategy_id>__<version>__run<NNN>`
4. Task ID: same as run ID

### Stability

Once a name is assigned in a deliverable, other agents must use the same name. Do not rename without explicit task.

## 4. Local vs JoinQuant Authority

### Authority Hierarchy

1. **JoinQuant platform**: authoritative for backtest results, order execution, factor data
2. **strategy_kits**: authoritative for task spec schema, panel format, local validation
3. **Local workbench**: authoritative for strategy cards, iteration registry, diff decisions

### Data Flow Direction

```
strategy_card -> task_spec -> panel -> local_run -> jq_strategy.py -> platform_run -> archive
```

### What to Trust

| Source | Trust Level | Notes |
|--------|-------------|-------|
| JoinQuant backtest results | Authoritative | Ground truth for performance |
| JoinQuant factor data | Authoritative | Ground truth for factors |
| strategy_kits artifact format | Authoritative | Local contract |
| Local computed signals | Validated | Must match platform after diff |
| strategy_card thesis | Documented | Not validated by execution |
| Iteration decisions | Governance | Human judgment |

### Conflict Resolution

When local and platform outputs differ:

1. Platform is authoritative for backtest metrics
2. Local is authoritative for pre-submission validation
3. Diff report documents the gap
4. Human decides to keep, rollback, or investigate

## 5. One-Change-Per-Iteration Rule

### Rule

Each iteration (version increment) must change exactly one aspect of the strategy.

### Allowed Change Categories

1. **Signal change**: factor weights, new factor, factor removal
2. **Universe change**: base pool, filters, min/max cap
3. **Rebalance change**: frequency, top_n, weight_method
4. **Risk change**: stop loss, position limits, regime filter
5. **Date range change**: start_date, end_date (different validation slice)

### Prohibited

1. Changing two factors in one version
2. Changing top_n and weight_method together
3. Changing universe filters and rebalance frequency together

### Documentation

Each version's changelog must state:
1. What changed (single change point)
2. Why it changed (hypothesis)
3. Result (keep or rollback)

### Example Changelog Entry

```yaml
changelog:
  - version: v1.1
    date: 2025-04-22
    change: Increased top_n from 20 to 30
    hypothesis: More diversification reduces single-stock risk
    decision: keep
```

## 6. Conflict Reporting

### Rule

If an agent discovers a cross-task dependency or naming conflict, it must report it in a final section.

### Format

```
## Conflicts And Recommendations

- Conflict: Task 02 expects `strategy_card_schema.md` to have `thesis.risk_premium` field.
  Current schema from Task 01 uses `thesis.expected_edge`.
  Recommendation: Unify field names before proceeding.

- Dependency: Task 03 requires panel naming convention from Task 02.
  Status: Blocked until Task 02 completes.
```

### When to Report

1. Write scope overlaps with another task
2. Naming inconsistency detected
3. Missing prerequisite file
4. Schema mismatch across files

## 7. Completion Note

### Rule

Every agent must end with a short completion note.

### Format

```
## Completion Note

Files changed:
1. jq_workbench/governance/standards/example_schema.md (created)
2. jq_workbench/knowledge/example.yaml (created)

Open conflicts:
- None

Status: Complete
```

### Required Elements

1. List of files changed (created or modified)
2. List of open conflicts (or "None")
3. Status (Complete | Partial | Blocked)

## Quick Reference

| Aspect | Rule |
|--------|------|
| Write scope | Explicit file list, no globs |
| Output contract | Define purpose and structure |
| Naming | Follow conventions, stay stable |
| Authority | JoinQuant > strategy_kits > local |
| Iteration | One change per version |
| Conflicts | Report, do not silently resolve |
| Completion | Summarize files and conflicts |