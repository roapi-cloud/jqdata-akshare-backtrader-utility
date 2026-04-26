# Knowledge Base

This layer stores human-readable strategy knowledge, not runtime code.

## Purpose

The knowledge base captures:
1. Raw source strategies imported from external references
2. Reusable mechanisms distilled from successful strategies
3. Review notes documenting lessons learned and failure patterns

## Structure

```
knowledge/
├── strategy_cards/      # Normalized strategy definitions (authoritative)
├── source_strategies/   # Imported raw materials and source references
├── mechanisms/          # Reusable components extracted from strategies
└── reviews/             # Postmortems, failure cases, and iteration notes
```

## Indexing Model

### Primary Key

Every knowledge item must link to a `strategy_id` defined in `strategy_cards/`.

| Item Type | File Pattern | Primary Index | Secondary Index |
|-----------|-------------|---------------|-----------------|
| Strategy Card | `<strategy_id>.yaml` | `strategy_id` | `version` |
| Source Strategy | `<strategy_id>__source.md` | `strategy_id` | `source_type` |
| Mechanism | `<nn>_<name>.md` | `mechanism_id` | `tags` |
| Review | `<strategy_id>/v<version>__review.md` or `<strategy_id>__v<version>__review.md` | `strategy_id` | `version` |

### Linking Convention

All items use YAML frontmatter to declare links:

```yaml
---
strategy_id: value_quality_momentum
version: v1.0
linked_cards:
  - strategy_id: value_quality_momentum
    version: v1.0
---
```

### Version Binding

1. `strategy_cards/` defines the authoritative version
2. `source_strategies/` links to the card that originated from it
3. `mechanisms/` lists which card versions use this mechanism
4. `reviews/` always bind to a specific card version

## Ingestion Flow

1. Raw strategy material arrives in `source_strategies/`
2. Knowledge extraction produces a `strategy_card` and optionally `mechanisms`
3. Review notes are added after each iteration
4. Cross-references are updated bidirectionally

## Minimum Metadata Per Item Type

| Item | Required Fields |
|------|-----------------|
| Source Strategy | `strategy_id`, `source_type`, `ingest_date`, `source_ref` |
| Mechanism | `mechanism_id`, `category`, `used_by`, `created_from` |
| Review | `strategy_id`, `version`, `review_date`, `outcome` |

## Query Patterns

Common queries supported by the indexing:

1. "What sources contributed to strategy X?" → `source_strategies/<X>__source.md`
2. "What mechanisms does strategy X use?" → Search `mechanisms/*.md` for `used_by: X`
3. "What reviews exist for X v1.0?" → `reviews/X/v1.0__review.md` or `reviews/X__v1.0__review.md`
4. "What strategies use mechanism 05?" → Check `mechanisms/05_*.md` → `used_by`

## Subdirectories

See individual README files:
- [source_strategies/README.md](source_strategies/README.md)
- [mechanisms/README.md](mechanisms/README.md)
- [reviews/README.md](reviews/README.md)
- [strategy_cards/README.md](strategy_cards/README.md)