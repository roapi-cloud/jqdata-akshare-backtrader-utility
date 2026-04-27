# Market Diagnostic System

大盘全维度诊断系统 - 面向策略系统的结构化市场诊断引擎。

## 功能概述

- **报告生成**: 输出结构化 JSON 和人类可读的 Markdown 报告
- **状态分类**: 7个维度 + 6个子状态 → 7种综合 Regime
- **策略映射**: Regime → 策略组推荐 (含配置权重)
- **知识库**: 索引、查询、可视化历史诊断报告

## 目录结构

```
platform/market_diagnostic/
├── __init__.py              # 主入口，导出所有公共API
├── engine.py                # MarketDiagnosticEngine 主引擎
├── config.py                # 配置 (INDEX_POOL, REGIME_STRATEGY_MAPPING 等)
├── cli.py                   # CLI 命令行工具
├── states/
│   ├── enums.py            # 状态枚举 (TrendState, CompositeRegime 等)
│   └── classifier.py        # MarketStateClassifier 分类器
├── reports/
│   ├── schema.py           # DiagnosticReport 数据类
│   ├── markdown_renderer.py # Markdown 渲染器
│   └── json_exporter.py    # JSON 导出器
├── strategy_mapping.py      # Regime → 策略组映射
└── knowledge_base_manager.py # 知识库管理器
```

## 快速开始

### 1. 运行诊断

```python
from platform.market_diagnostic import MarketDiagnosticEngine

engine = MarketDiagnosticEngine()
report, markdown = engine.run(date="2026-04-25")

print(report.one_sentence_summary)
print(f"Regime: {report.composite_regime}, Confidence: {report.confidence:.0%}")
```

### 2. 导出报告

```python
from platform.market_diagnostic import (
    DiagnosticReport,
    DiagnosticMarkdownRenderer,
    DiagnosticJsonExporter,
)

# JSON 导出
exporter = DiagnosticJsonExporter()
json_str = exporter.to_json(report)

# Markdown 渲染
renderer = DiagnosticMarkdownRenderer()
md_str = renderer.render(report)
```

### 3. 策略映射

```python
from platform.market_diagnostic import (
    get_regime_recommendation,
    get_strategy_allocations,
)

# 获取完整推荐
rec = get_regime_recommendation("trend_risk_on_growth")
print(f"Display: {rec.display_name}")
for a in rec.allocations:
    print(f"  {a.strategy_group}: {a.allocation_weight:.0%}")

# 获取简单列表
groups = get_strategy_allocations("balanced_rotation")
```

### 4. 知识库管理

```python
from platform.market_diagnostic import (
    KnowledgeBaseManager,
    ReportQuery,
    get_knowledge_base,
)

# 获取默认实例
kb = get_knowledge_base()

# 查询报告
query = ReportQuery(
    start_date="2026-01-01",
    end_date="2026-04-27",
    regime="trend_risk_on_growth",
    min_confidence=0.7,
)
results = kb.query_reports(query)

# 保存新报告
kb.save_report(report_dict, date="2026-04-27")

# 可视化
print(kb.generate_regime_timeline_ascii(days=30))
print(kb.generate_regime_distribution_text())
```

## CLI 使用

```bash
# 运行诊断
python -m platform.market_diagnostic.cli run --date 2026-04-25

# 查询报告
python -m platform.market_diagnostic.cli query --regime trend_risk_on_growth
python -m platform.market_diagnostic.cli query --start-date 2026-01-01 --end-date 2026-04-27

# 显示时间线
python -m platform.market_diagnostic.cli timeline --days 30

# 显示统计数据
python -m platform.market_diagnostic.cli stats

# 显示策略映射
python -m platform.market_diagnostic.cli strategies
python -m platform.market_diagnostic.cli strategies --regime balanced_rotation
```

## 7 种 Regime

| Regime | Display Name | Primary Strategy |
|--------|-------------|------------------|
| trend_risk_on_growth | 趋势进攻·成长主导 | 趋势ETF组 (50%) |
| trend_risk_on_smallcap | 趋势进攻·小盘主导 | 趋势ETF组 (55%) |
| balanced_rotation | 均衡轮动 | 行业轮动组 (40%) |
| defensive_dividend | 防守·红利 | 红利价值组 (45%) |
| high_volatility_warning | 高波动预警 | 高现金配置 (40%) |
| panic_bottoming | 恐慌探底 | 趋势ETF小仓试探 (70%) |
| broad_weakness_hold | 全面弱势·持币观望 | 股债平衡组 (35%) |

## 状态维度

- **趋势 (TrendState)**: 强趋势上行 / 趋势上行中的回调 / 震荡 / 趋势转弱 / 破位下行
- **广度 (BreadthState)**: 极弱 / 偏弱 / 中性 / 偏强 / 过热
- **情绪 (SentimentState)**: 冰点 / 回暖 / 中性 / 活跃 / 狂热
- **风格 (StyleState)**: 大盘防守 / 小盘进攻 / 成长主导 / 红利防守 / 风格冲突
- **板块 (SectorState)**: 无主线 / 单主线 / 双主线并行 / 高速轮动 / 退潮分化
- **风险 (RiskState)**: 低风险 / 中性风险 / 高风险 / 极端风险

## 知识库目录

```
knowledge/
├── diagnostic_reports/YYYY-MM/  # 每日诊断报告
├── regime_patterns/              # Regime模式库
└── strategy_mapping/             # 策略映射文档
```

## 参考文档

- Requirements: `.kiro/specs/market-diagnostic-system/requirements.md` (Req 18-20, 25)
- Design: `.kiro/specs/market-diagnostic-system/design.md` (Section 3.5, 4)