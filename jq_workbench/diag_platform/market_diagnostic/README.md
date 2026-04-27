# Market Diagnostic System - Usage Guide

## Overview

The Market Diagnostic System provides comprehensive A-share market analysis through structured diagnostic reports, regime classification, and strategy mapping.

## Quick Start

### 1. Run Diagnostic

```bash
# Navigate to the project directory
cd /Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility/jq_workbench

# Run diagnostic for a specific date
python -m platform.market_diagnostic.cli run --date 2026-04-25 --output ./output

# Run for today's date
python -m platform.market_diagnostic.cli run
```

### 2. Query Historical Reports

```bash
# Query all reports from the last 30 days
python -m platform.market_diagnostic.cli query

# Query by regime
python -m platform.market_diagnostic.cli query --regime balanced_rotation

# Query with date range
python -m platform.market_diagnostic.cli query --start-date 2026-01-01 --end-date 2026-04-25

# Query with minimum confidence
python -m platform.market_diagnostic.cli query --min-confidence 0.7

# Output as JSON
python -m platform.market_diagnostic.cli query --format json
```

### 3. View Regime Timeline

```bash
# Show last 30 days timeline
python -m platform.market_diagnostic.cli timeline --days 30

# Show last 7 days
python -m platform.market_diagnostic.cli timeline --days 7

# Custom width
python -m platform.market_diagnostic.cli timeline --days 60 --width 100
```

### 4. Show Regime Statistics

```bash
# Show statistics for last 30 days
python -m platform.market_diagnostic.cli stats

# Show statistics with date range
python -m platform.market_diagnostic.cli stats --start-date 2026-01-01 --end-date 2026-04-25
```

### 5. Show Strategy Mappings

```bash
# Show all regime strategies
python -m platform.market_diagnostic.cli strategies

# Show specific regime
python -m platform.market_diagnostic.cli strategies --regime trend_risk_on_growth

# Show defensive dividend strategies
python -m platform.market_diagnostic.cli strategies --regime defensive_dividend
```

## The 7 Market Regimes

| Regime | Display Name | Description | Primary Strategy |
|--------|--------------|-------------|------------------|
| `trend_risk_on_growth` | 趋势进攻·成长主导 | 强趋势上行 + 成长风格 | 趋势ETF组 (50%) + 行业轮动 (30%) + 小市值 (20%) |
| `trend_risk_on_smallcap` | 趋势进攻·小盘主导 | 强趋势上行 + 小盘风格 | 趋势ETF组 (55%) + 小市值 (30%) + 行业轮动 (15%) |
| `balanced_rotation` | 均衡轮动 | 震荡整理 + 行业轮动 | 行业轮动 (40%) + 红利价值 (35%) + 股债平衡 (25%) |
| `defensive_dividend` | 防守·红利 | 趋势转弱 + 红利防御 | 红利价值 (45%) + 股债平衡 (35%) + 全天候 (20%) |
| `high_volatility_warning` | 高波动预警 | 波动率显著上升 | 高现金 (40%) + 股债平衡 (30%) + 全天候 (30%) |
| `panic_bottoming` | 恐慌探底 | 广度极弱 + 情绪冰点 | 趋势ETF小仓试探 (70%) + 小市值观察 (30%) |
| `broad_weakness_hold` | 全面弱势·持币观望 | 破位下行 + 广度偏弱 | 股债平衡 (35%) + 全天候 (35%) + 高现金 (30%) |

## Python API Usage

### Generate a Diagnostic Report

```python
from market_diagnostic.engine import MarketDiagnosticEngine
from daily_stock_analysis.src.data_provider.base import DataFetcherManager
from platform.market_diagnostic.reports import DiagnosticJsonExporter

# Initialize engine
data_manager = DataFetcherManager()
engine = MarketDiagnosticEngine(data_manager)

# Run diagnostic
report, markdown = engine.run(date="2026-04-25")

# Export to JSON
exporter = DiagnosticJsonExporter()
json_str = exporter.to_json(report, compact=False)
```

### Query Knowledge Base

```python
from platform.market_diagnostic import KnowledgeBaseManager, ReportQuery

kb = KnowledgeBaseManager()

# Query by regime
reports = kb.query_reports(ReportQuery(regime="balanced_rotation"))

# Query with filters
reports = kb.query_reports(ReportQuery(
    start_date="2026-01-01",
    end_date="2026-04-25",
    min_confidence=0.7,
    trend_state="震荡",
))

# Get recent reports
recent = kb.get_recent_reports(days=30)

# Get regime timeline
timeline = kb.get_regime_timeline(start_date="2026-01-01", end_date="2026-04-25")

# Show regime distribution
print(kb.generate_regime_distribution_text())
```

### Get Strategy Recommendations

```python
from platform.market_diagnostic import get_regime_recommendation, get_regime_summary_table

# Get specific regime recommendation
rec = get_regime_recommendation("trend_risk_on_growth")
print(f"Display Name: {rec.display_name}")
print(f"Description: {rec.description}")
for a in rec.allocations:
    print(f"  {a.strategy_group}: {a.allocation_weight*100:.0f}%")

# Get summary table
summary = get_regime_summary_table()
for row in summary:
    print(f"{row['display_name']}: {row['strategy_count']} strategies")
```

## Output Files

Reports are saved to:
- **JSON**: `diagnostic_reports/YYYY-MM/YYYY-MM-DD_regime_report.json`
- **Markdown**: `diagnostic_reports/YYYY-MM/YYYY-MM-DD_regime_report.md`

## File Structure

```
jq_workbench/
├── platform/
│   └── market_diagnostic/
│       ├── __init__.py
│       ├── cli.py              # Command-line interface
│       ├── engine.py           # MarketDiagnosticEngine
│       ├── reports/            # Report generation
│       │   ├── __init__.py
│       │   ├── markdown_report.py
│       │   └── json_exporter.py
│       ├── strategy_mapping.py # Regime → Strategy mapping
│       └── knowledge_base_manager.py
└── knowledge/
    ├── diagnostic_reports/      # Historical reports
    ├── regime_patterns/        # Regime pattern definitions
    └── strategy_mapping/        # Strategy mapping rules
```

## Integration with Existing System

The `MarketDiagnosticEngine` reuses existing components:
- `DataFetcherManager` for data fetching
- `AkShare` interfaces for market data
- `GeminiAnalyzer` for LLM narrative generation (optional)

See `daily_stock_analysis/src/market_diagnostic/engine.py` for the main implementation.