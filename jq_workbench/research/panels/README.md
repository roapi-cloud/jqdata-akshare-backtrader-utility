# Panels

Store research input panels here.

## Panel Types

| Type | Description | Required Columns |
|------|-------------|------------------|
| `pool_panel` | Pre-filtered stock pool with scores and ranks | date, code, score, rank |
| `score_panel` | Cross-sectional factor scores | date, code, score |
| `prediction_frame` | Execution-ready target weights | date, code, weight |

## Naming Convention

```
<strategy_id>__<version>__<panel_type>.csv
```

### Components

- `strategy_id`: snake_case identifier matching strategy_card
- `version`: semver (v1.0, v1.1, v1.2)
- `panel_type`: one of pool_panel, score_panel, prediction_frame

### Examples

```
value_quality_momentum__v1.0__pool_panel.csv
small_cap_rotate__v2.1__score_panel.csv
ml_alpha_v1__v1.0__prediction_frame.csv
```

## Validation

Use strategy_kits validators before committing:

```python
from strategy_kits.integrations.factorhub import (
    validate_factorhub_pool_panel,
    validate_factorhub_score_panel,
    pool_panel_to_prediction_frame,
    score_panel_to_prediction_frame,
)
from strategy_kits.contracts import validate_prediction_frame

# Validate input
panel = pd.read_csv("value_quality_momentum__v1.0__pool_panel.csv")
validated = validate_factorhub_pool_panel(panel)

# Convert to prediction frame
pred = pool_panel_to_prediction_frame(panel, top_n=20, weight_mode="score")
```

## Column Normalization

### Stock Code

- Zero-padded to 6 digits
- Examples: `1` → `000001`, `600519` → `600519`

### Date

- Normalized to midnight (00:00:00)
- Examples: `2024-01-05`, `01/05/2024` → `2024-01-05 00:00:00`

## Contract Reference

See `jq_workbench/governance/standards/panel_contracts.md` for full specification.

## Typical Workflow

1. Generate panel from research or factor computation
2. Validate with appropriate validator
3. Save with correct naming convention
4. Reference in task_spec via `panel_path`
5. Run strategy_kits execution