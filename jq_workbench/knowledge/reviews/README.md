# Reviews

Store structured review outputs documenting strategy iteration outcomes.

## Purpose

Reviews capture lessons learned, failure analysis, and decisions from strategy iterations. They form the institutional memory of what worked, what failed, and why.

## File Naming

Pattern: `<strategy_id>__v<version>__review.md`

Examples:
- `value_quality_momentum__v1.0__review.md`
- `value_quality_momentum__v1.1__review.md`
- `small_cap_rotate__v1.0__review.md`

## Schema

```yaml
---
strategy_id: string           # Links to strategy_cards/<id>.yaml
version: string               # Which version this reviews
review_date: date            # YYYY-MM-DD
reviewer: string             # Who performed the review
outcome: enum                 # keep | rollback | major_change | deprecate
run_archive_ref: string       # Path to run archive
platform_run_id: string       # JoinQuant run ID if applicable
linked_card: string           # Path to strategy card
---

# Executive Summary

[2-3 sentence verdict on this iteration]

# Performance Summary

| Metric | Target | Local | Platform | Status |
|--------|--------|-------|----------|--------|
| Sharpe | 1.2 | 1.35 | 1.28 | Pass |
| Max DD | 20% | 18.2% | 19.1% | Pass |
| Turnover | 3.0 | 2.8 | 2.9 | Pass |

# Diff Analysis

[Comparison between local and platform results]

# Regime Performance

| Regime | Periods | Return | Assessment |
|--------|---------|--------|------------|
| Bull | 12 | +8.5% | As expected |
| Bear | 6 | -12.3% | Worse than expected |
| Sideways | 8 | +1.2% | Neutral |

# Failure Cases

[Documented failure scenarios from this iteration]

# What Worked

[Elements to preserve]

# What Failed

[Elements to change or remove]

# Recommendations

[Specific changes for next version]

# Decision

[Final decision with rationale]
```

## Indexing Keys

| Key | Type | Description |
|-----|------|-------------|
| `strategy_id` | string | Primary link to strategy card |
| `version` | string | Card version being reviewed |
| `review_date` | date | Chronological ordering |
| `outcome` | enum | Decision summary |

## Outcome Types

| Outcome | Description | Next Action |
|---------|-------------|-------------|
| `keep` | Good to proceed | Increment minor version or promote |
| `rollback` | Revert changes | Restore previous version |
| `major_change` | Needs significant rework | Create new version branch |
| `deprecate` | Strategy retired | Update card state to `retired` |

## Linking Back to Card

Every review must link to the specific strategy card version:

```yaml
linked_card: strategy_cards/value_quality_momentum.yaml
```

After a review, update the strategy card's `changelog`:

```yaml
# In strategy_cards/value_quality_momentum.yaml
changelog:
  - version: v1.1
    date: 2026-04-25
    change: Added CVIX regime filter based on review v1.0
    decision: keep
```

## Minimum Metadata Checklist

- [ ] `strategy_id` matches an existing card
- [ ] `version` matches a card version
- [ ] `review_date` set
- [ ] `outcome` is one of the defined enums
- [ ] `run_archive_ref` points to actual run output
- [ ] `linked_card` path is correct

## Review Types

### Iteration Review

Standard review after a version change:

```
<strategy_id>__v<version>__review.md
```

### Failure Postmortem

Deep dive after significant failure:

```
<strategy_id>__v<version>__postmortem.md
```

Additional sections:
- Root cause analysis
- Timeline of failure
- Detection mechanism
- Prevention plan

### Deprecation Note

When retiring a strategy:

```
<strategy_id>__deprecation.md
```

Required fields:
- Deprecation date
- Reason
- Migration path (if any)
- Data retention policy

## Directory Structure

```
reviews/
├── README.md
├── value_quality_momentum/
│   ├── v1.0__review.md
│   ├── v1.1__review.md
│   └── v1.2__postmortem.md
├── small_cap_rotate/
│   └── v1.0__review.md
└── deprecations/
    └── old_strategy__deprecation.md
```

Optional: Create subdirectories per strategy for cleaner organization.

## Linking to Other Artifacts

| Artifact | Link Field | Example |
|----------|-----------|---------|
| Run Archive | `run_archive_ref` | `../platform/run_archive/value_quality_momentum/v1.0/2026-04-22/` |
| Diff Report | In body | `See diff: ../platform/diff_reports/value_quality_momentum/v1.0/2026-04-22__vqm_001.md` |
| Mechanisms | In recommendations | `Consider adopting 10_volatility_position` |

## Quality Rules

1. One review per version change
2. Review date within 48 hours of run completion
3. Outcome decision must be explicit
4. Link to run archive is mandatory for `keep` or `rollback`
5. All performance metrics from card targets must be addressed
6. Failure cases must have mitigation proposals

## Query Patterns

```bash
# Find all reviews for a strategy
ls <strategy_id>__*.md

# Find all rollbacks
grep "outcome: rollback" *.md

# Find reviews in date range
grep "review_date: 2026-04" *.md

# Find strategies with multiple failures
grep -l "outcome: rollback\|outcome: major_change" *.md | sort | uniq -c
```