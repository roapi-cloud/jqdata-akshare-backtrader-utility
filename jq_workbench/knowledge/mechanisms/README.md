# Mechanisms

Store reusable mechanism notes here for cross-strategy reuse.

## Purpose

Mechanisms are extracted, reusable components distilled from successful strategies. They include filters, timing rules, risk controls, and portfolio assembly rules that can be applied across multiple strategies.

## Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `universe_filter` | Stock pool filtering rules | ST exclusion, cap bounds, liquidity |
| `timing_gate` | Market timing and regime filters | CVIX trigger, MA cross, breadth |
| `risk_control` | Position and portfolio risk rules | Stop loss, max sector, drawdown |
| `portfolio_assembly` | Weighting and construction rules | Risk parity, rank weight, equal |
| `execution_safeguard` | Trade execution rules | Slippage control, volume limit |

## File Naming

Pattern: `<nn>_<snake_case_name>.md`

Examples:
- `01_emotion_switch.md`
- `02_pause_mechanism.md`
- `03_state_router.md`
- `10_volatility_position.md`

The `<nn>` prefix provides a stable numeric index for cross-referencing, aligned with `universal_mechanisms/` naming.

## Schema

```yaml
---
mechanism_id: string           # <nn>_<name>
category: enum                 # universe_filter | timing_gate | risk_control | portfolio_assembly | execution_safeguard
created_date: date            # YYYY-MM-DD
created_from:                 # Origin strategy
  strategy_id: string
  version: string
used_by:                      # Strategies using this mechanism
  - strategy_id: string
    version: string
    since: date
tags: [string]                # Searchable tags
---

# Mechanism Summary

[One-sentence description]

# Logic

[Detailed logic, formulas, parameters]

# Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| ... | ... | ... | ... |

# JoinQuant Implementation

[How to implement in JoinQuant context]

# Usage Conditions

[When this mechanism is appropriate]

# Known Limitations

[When not to use, failure cases]

# References

[Links to papers, posts, or other sources]
```

## Indexing Keys

| Key | Type | Description |
|-----|------|-------------|
| `mechanism_id` | string | Primary stable identifier |
| `category` | enum | Primary grouping for discovery |
| `used_by` | list | Reverse link to consuming strategies |
| `tags` | list | Free-form search keywords |

## Linking to Strategy Cards

### Created From

Every mechanism must trace its origin:

```yaml
created_from:
  strategy_id: value_quality_momentum
  version: v1.0
```

### Used By

When a strategy adopts a mechanism, add it to `used_by`:

```yaml
used_by:
  - strategy_id: value_quality_momentum
    version: v1.0
    since: 2026-04-22
  - strategy_id: small_cap_rotate
    version: v1.1
    since: 2026-04-25
```

### In Strategy Card

When a strategy uses mechanisms, reference them in the card:

```yaml
# In strategy_cards/<id>.yaml
notes:
  - Uses 01_emotion_switch for regime detection
  - Uses 10_volatility_position for sizing
```

## Minimum Metadata Checklist

- [ ] `mechanism_id` follows naming convention
- [ ] `category` is one of the defined enums
- [ ] `created_from` links to origin strategy
- [ ] `used_by` list is maintained (at minimum includes `created_from`)
- [ ] At least one `tag` for discoverability

## Discovery Query Examples

```bash
# Find all timing mechanisms
grep "category: timing_gate" *.md

# Find mechanisms used by specific strategy
grep "strategy_id: value_quality_momentum" *.md

# Find mechanisms with specific tag
grep "volatility" *.md
```

## Alignment with universal_mechanisms/

This directory's mechanisms should align with the repository's `/universal_mechanisms/` folder:

| This Directory | universal_mechanisms/ |
|---------------|----------------------|
| Knowledge format, links to cards | Reference implementation |
| Markdown with YAML frontmatter | Detailed design docs |
| Minimal, reusable patterns | Full specifications |

When extracting from `/universal_mechanisms/`:
1. Create a knowledge entry here
2. Link back to the source file
3. Track which strategies use it

## Quality Rules

1. One mechanism per file
2. Mechanism should be reusable across strategies
3. Document all parameters with defaults
4. Maintain bidirectional links (`used_by` updated on both sides)
5. Include at least one concrete JoinQuant implementation hint