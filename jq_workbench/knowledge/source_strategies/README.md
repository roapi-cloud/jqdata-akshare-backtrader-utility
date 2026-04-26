# Source Strategies

Store imported source materials here or store index files pointing to them.

## Purpose

This directory captures raw strategy material before normalization into strategy cards. It preserves the original source for reference, attribution, and audit trail.

## File Naming

Pattern: `<strategy_id>__source.md`

Examples:
- `value_quality_momentum__source.md`
- `small_cap_rotate__source.md`
- `high_dividend__source.md`

## Schema

```yaml
---
strategy_id: string           # Links to strategy_cards/<id>.yaml
source_type: enum             # jq_community | paper | book | internal | external_code
source_ref: string            # URL, file path, or citation
ingest_date: date            # YYYY-MM-DD when ingested
ingest_by: string            # Who performed the ingestion
status: enum                  # raw | extracted | deprecated
linked_card_version: string   # Which card version this produced
---

# Source Summary

[Brief description of the original strategy]

# Original Logic

[Preserved logic, formulas, or code snippets from source]

# Extraction Notes

[What was extracted, what was adapted, what was omitted]

# Gaps and Assumptions

[What was unclear and how assumptions were made]
```

## Indexing Keys

| Key | Type | Description |
|-----|------|-------------|
| `strategy_id` | string | Primary link to strategy card |
| `source_type` | enum | Origin category for filtering |
| `ingest_date` | date | Timeline tracking |
| `status` | enum | Processing state |

## Source Types

| Type | Description | Example `source_ref` |
|------|-------------|---------------------|
| `jq_community` | JoinQuant community post | `https://www.joinquant.com/view/community/detail/xxxxx` |
| `paper` | Academic or research paper | `SSRN 12345` or DOI |
| `book` | Published book | `Active Portfolio Management, Ch. 12` |
| `internal` | Internal research note | `docs/internal/momentum_research_2024.md` |
| `external_code` | Code from other platforms | `backtrader_contrib/xxx.py` |

## Minimum Metadata Checklist

- [ ] `strategy_id` matches an existing or planned card
- [ ] `source_type` is one of the defined enums
- [ ] `source_ref` is verifiable
- [ ] `ingest_date` is set
- [ ] `linked_card_version` updated after card creation

## Linking Back to Card

After creating the strategy card, update `linked_card_version`:

```yaml
linked_card_version: v1.0
```

If the source produces multiple card versions over time, record the first version that derived from it.

## Status Transitions

```
raw -> extracted -> deprecated
```

- `raw`: Ingested but not yet processed
- `extracted`: Strategy card created from this source
- `deprecated`: Source superseded by better material

## Directory Structure

```
source_strategies/
├── README.md
├── value_quality_momentum__source.md
├── small_cap_rotate__source.md
└── attachments/               # Optional: supporting files
    └── xxx_paper.pdf
```

## Quality Rules

1. One source file per strategy_id
2. Preserve original logic even if not used
3. Document all assumptions explicitly
4. Link back to card within 24 hours of card creation
5. Mark as `deprecated` if a better source replaces it