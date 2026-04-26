# Panel Contracts

Panel contracts define the input DataFrame schemas for strategy research runs.

## Panel Types

| Type | Purpose | Use Case |
|------|---------|----------|
| `pool_panel` | Pre-filtered and ranked stock pool | Strategies with explicit stock selection |
| `score_panel` | Cross-sectional scores without pre-filtering | Factor scoring, ML prediction outputs |
| `prediction_frame` | Final execution-ready target weights | Direct strategy execution |

---

## 1. pool_panel

Pre-filtered stock pool with scores and ranks. Used when stock selection is already determined upstream.

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `date` | datetime/date | Trading date (normalized to midnight) |
| `code` | string | 6-digit stock code (zero-padded) |
| `score` | float | Numeric score for weighting |
| `rank` | int | Integer rank for selection (1 = best) |

### Normalization Rules

- `date`: Converted to `pd.Timestamp` at midnight (00:00:00)
- `code`: Zero-padded to 6 characters (e.g., `1` → `000001`)
- `score`: Must be numeric, no NaN allowed
- `rank`: Must be integer, no NaN allowed, sorted ascending

### Validation

```python
# strategy_kits/contracts/dataframe_contracts.py
validate_pool_panel(df)
# strategy_kits/integrations/factorhub/contracts.py
validate_factorhub_pool_panel(df)
```

### Example

```csv
date,code,score,rank
2024-01-05,000001,0.85,1
2024-01-05,600519,0.72,2
2024-01-05,000858,0.68,3
```

---

## 2. score_panel

Cross-sectional factor scores. Used for factor-based strategies where selection happens downstream.

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `date` | datetime/date | Trading date (normalized to midnight) |
| `code` | string | 6-digit stock code (zero-padded) |
| `score` | float | Numeric score for ranking/weighting |

### Optional Columns

| Column | Type | Description |
|--------|------|-------------|
| `rank` | int | Pre-computed rank (computed if absent) |
| `ts_score` | float | Alias for `score` (auto-renamed) |

### Normalization Rules

- `date`: Converted to `pd.Timestamp` at midnight (00:00:00)
- `code`: Zero-padded to 6 characters
- `score`: Must be numeric, no NaN allowed
- `ts_score`: Renamed to `score` if present

### Validation

```python
# strategy_kits/integrations/factorhub/contracts.py
validate_factorhub_score_panel(df)
```

### Example

```csv
date,code,score
2024-01-05,000001,0.85
2024-01-05,600519,0.72
2024-01-05,000858,0.68
```

---

## 3. prediction_frame

Execution-ready DataFrame with target weights. The final output before strategy execution.

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `date` | datetime/date | Trading date (normalized to midnight) |
| `code` | string | 6-digit stock code (zero-padded) |
| `weight` | float | Target position weight (sum to 1.0 per date) |

### Optional Columns

| Column | Type | Description |
|--------|------|-------------|
| `score` | float | Original score (preserved from panel) |
| `rank` | int | Original rank (preserved from pool_panel) |

### Normalization Rules

- `date`: Converted to `pd.Timestamp` at midnight (00:00:00)
- `code`: Zero-padded to 6 characters
- `weight`: Default to `1.0` if column absent (equal weight fallback)

### Validation

```python
# strategy_kits/contracts/dataframe_contracts.py
validate_prediction_frame(df)
```

### Example

```csv
date,code,weight,score
2024-01-05,000001,0.05,0.85
2024-01-05,600519,0.042,0.72
2024-01-05,000858,0.040,0.68
```

---

## Conversion Flow

```
pool_panel ──┬──> prediction_frame
              │
score_panel ──┘
```

Both `pool_panel` and `score_panel` convert to `prediction_frame` via:

```python
# strategy_kits/integrations/factorhub/adapter.py
pool_panel_to_prediction_frame(panel, top_n=20, weight_mode="score")
score_panel_to_prediction_frame(panel, top_n=20, weight_mode="equal")
```

### Conversion Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `top_n` | int | 20 | Number of top stocks to select per date |
| `weight_mode` | str | "score" | "equal" or "score"-weighted allocation |

---

## File Naming Convention

Panels stored in `jq_workbench/research/panels/` follow this pattern:

```
<strategy_id>__<version>__<panel_type>.csv
```

### Components

| Component | Format | Example |
|-----------|--------|---------|
| `strategy_id` | snake_case | `value_quality_momentum` |
| `version` | semver | `v1.0`, `v1.1` |
| `panel_type` | panel_type | `pool_panel`, `score_panel`, `prediction_frame` |

### Examples

```
value_quality_momentum__v1.0__pool_panel.csv
small_cap_rotate__v2.1__score_panel.csv
ml_alpha_v1__v1.0__prediction_frame.csv
```

---

## Task Spec Integration

Panels are referenced in task specs:

```json
{
  "task": {
    "task_id": "value_quality_momentum__v1.0__run001",
    "strategy_name": "value_quality_momentum"
  },
  "data": {
    "panel_type": "pool_panel",
    "panel_path": "jq_workbench/research/panels/value_quality_momentum__v1.0__pool_panel.csv",
    "start_date": "2020-01-01",
    "end_date": "2023-12-31"
  },
  "pipeline": {
    "top_n": 20,
    "weight_mode": "score"
  }
}
```

---

## Code Normalization Details

All panels normalize stock codes to 6-digit zero-padded strings:

| Input | Normalized |
|-------|------------|
| `1` | `000001` |
| `600519` | `600519` |
| `000001.XSHG` | `000001` (strip suffix) |
| `000001.XSHE` | `000001` (strip suffix) |

Unconfirmed: Suffix stripping is not yet implemented in current validators.

---

## Date Normalization Details

All panels normalize dates to midnight timestamps:

| Input | Normalized |
|-------|------------|
| `2024-01-05` | `2024-01-05 00:00:00` |
| `2024-01-05 14:30:00` | `2024-01-05 00:00:00` |
| `01/05/2024` | `2024-01-05 00:00:00` |

---

## Validation Error Codes

| Code | Description |
|------|-------------|
| `CONTRACT_MISSING_COLUMN` | Required column not found |
| `CONTRACT_INVALID_VALUE` | Value validation failed (NaN, wrong type) |

Reference: `strategy_kits/core/errors.py`