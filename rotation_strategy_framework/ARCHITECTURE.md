# 终极轮动策略框架 v1.0

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        主流水线 (Pipeline)                        │
│  研究模式 → 模拟盘模式 → 实盘模式                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌────────────────┐    ┌────────────────┐
│  数据层        │    │  策略引擎       │    │  交易执行层     │
│  DataLayer    │    │  Strategy      │    │  LiveTrading   │
└───────────────┘    └────────────────┘    └────────────────┘
        │                     │                     │
   ┌────┴────┐          ┌────┴────┐           ┌────┴────┐
   │ 缓存管理 │          │ 因子引擎 │           │ 订单管理 │
   │ 数据加载 │          │ 回测引擎 │           │ 仓位管理 │
   │ 数据验证 │          │ 评估排名 │           │ 券商适配 │
   └─────────┘          └─────────┘           └─────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │ 组合优化器    │    │ 风控系统      │
            │ Portfolio    │    │ RiskManager  │
            └──────────────┘    └──────────────┘
                    │                   │
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │ 监控与日志    │    │ 报警系统      │
            │ Monitor      │    │ Alert        │
            └──────────────┘    └──────────────┘
```

## 模块清单

| 模块 | 文件 | 行数 | 功能 |
|------|------|------|------|
| 数据层 | `data_layer.py` | ~1200 | 数据加载、缓存、验证、对齐 |
| 因子引擎 | `factor_engine.py` | ~1800 | 8种打分+5种配置+7种择时+6种风控 |
| 策略注册 | `strategy_registry.py` | ~1900 | 14种预设策略、参数空间、版本管理 |
| 回测引擎 | `backtest_engine.py` | ~1500 | 单策略/多策略/Walk-Forward/网格搜索 |
| 评估器 | `strategy_evaluator.py` | ~1200 | 多维度评分、排名、动态权重 |
| 组合优化 | `portfolio_optimizer.py` | ~1400 | 等权/风险平价/均值方差/BL/HRP |
| 风控系统 | `risk_manager.py` | ~1300 | 三层风控、分级熔断、风险预算 |
| 实盘交易 | `live_trading.py` | ~1400 | 模拟/实盘切换、订单/仓位管理 |
| 监控日志 | `monitor.py` | ~1700 | 结构化日志、报警、报告生成 |
| 主流水线 | `pipeline.py` | ~1200 | 一键运行、自动选策、CLI |
| **总计** | **10个模块** | **~14,600行** | **完整可运行框架** |

## 14种预设策略

| # | 策略名 | 打分模式 | 配置模式 | 择时方法 | 风险 | 预期年化 |
|---|--------|----------|----------|----------|------|---------|
| 1 | etf_momentum_rsrs | 线性回归 | TopN | RSRS | 中 | 18% |
| 2 | etf_core_asset | 对数回归 | TopN | 无 | 中 | 15% |
| 3 | etf_bias_momentum | 乖离率 | TopN | RSRS+MA | 中高 | 20% |
| 4 | etf_kalman | 卡尔曼 | TopN | RSRS | 中 | 16% |
| 5 | multi_factor_epo | 多因子 | EPO | RSRS | 中 | 20% |
| 6 | sector_heat | 板块热度 | TopN | MA交叉 | 中高 | 22% |
| 7 | min_correlation | 对数回归 | 最小相关 | 无 | 低 | 12% |
| 8 | epo_optimized | 对数回归 | EPO | 无 | 中 | 18% |
| 9 | stock_bond_balance | 线性回归 | 股债平衡 | 回撤分级 | 低 | 10% |
| 10 | grid_trading | 简单收益 | 网格 | 无 | 中 | 15% |
| 11 | t0_momentum | 简单收益 | TopN | 无 | 高 | 25% |
| 12 | chase_momentum | 线性回归 | TopN | 无 | 高 | 25% |
| 13 | ir_trend | IR趋势 | TopN | 无 | 中 | 16% |
| 14 | north_money_timing | 对数回归 | TopN | 北向Boll | 中 | 15% |

## 快速开始

### 1. 研究模式 (回测+评估+自动选策)

```bash
cd rotation_strategy_framework
python run.py --mode research
```

### 2. 指定策略回测

```bash
python run.py --mode research \
  --strategies etf_momentum_rsrs,multi_factor_epo \
  --start 2020-01-01 --end 2024-12-31 \
  --cash 1000000
```

### 3. 模拟盘模式

```bash
python run.py --mode simulation --config config.yaml
```

### 4. 实盘模式 (需配置券商接口)

```bash
python run.py --mode live --config config.yaml
```

### 5. Python API

```python
from rotation_strategy_framework import Pipeline, PipelineConfig

config = PipelineConfig.from_yaml("config.yaml")
pipeline = Pipeline(config)

# 研究模式
result = pipeline.run_research()
print(f"最优策略: {result['selected_strategies']}")
print(f"组合权重: {result['portfolio_weights']}")
```

## 核心修复 (v3.0)

| 缺陷 | 修复方式 |
|------|----------|
| 持仓判断错误 | `self.getposition(data).size` |
| 卡尔曼滤波退化 | 持久化 P 协方差状态 |
| T+0索引错误 | `d.close[-1]` = 昨天 |
| R²除零 | `if var_y < 1e-10: return 0` |
| 卖出逻辑遍历 | 正确遍历 `self.data_refs.keys()` |
| RSRS状态丢失 | 实例级 `slope_history` 持久化 |
| 缓存无版本 | `CACHE_VERSION` + hash文件名 |
| rebalance漂移 | 按交易日计数 |
| EPO signal退化 | 用动量得分替代均值 |
| T+0被限流 | 跳过 rebalance_period 判断 |

## 目录结构

```
rotation_strategy_framework/
├── __init__.py              # 包入口
├── data_layer.py            # 数据层
├── factor_engine.py         # 因子引擎
├── strategy_registry.py     # 策略注册中心
├── backtest_engine.py       # 回测引擎
├── strategy_evaluator.py    # 策略评估器
├── portfolio_optimizer.py   # 组合优化器
├── risk_manager.py          # 风控系统
├── live_trading.py          # 实盘交易
├── monitor.py               # 监控日志
├── pipeline.py              # 主流水线
├── run.py                   # 快速启动
└── config.yaml              # 配置文件示例
```

## 扩展指南

### 添加新策略

```python
from rotation_strategy_framework.strategy_registry import StrategyRegistry, StrategyConfig

StrategyRegistry.register(
    StrategyConfig(
        name="my_custom_strategy",
        scoring_mode="momentum_regression",
        allocation_mode="top_n",
        timing_method="rsrs",
        etf_pool=["510300", "510050"],
        params={"momentum_days": 20, "stock_num": 1},
    )
)
```

### 添加新因子

```python
from rotation_strategy_framework.factor_engine import FactorEngine

# 在 FactorEngine 中添加静态方法
@staticmethod
def my_custom_factor(data, **params):
    # 计算逻辑
    return score
```

### 添加券商接口

```python
from rotation_strategy_framework.live_trading import BrokerInterface

class MyBroker(BrokerInterface):
    def place_order(self, ...): ...
    def cancel_order(self, ...): ...
    def get_positions(self): ...
```
