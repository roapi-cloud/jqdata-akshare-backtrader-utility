# 消融实验矩阵与模块开关设计

**版本**: v1.0  
**日期**: 2026-04-03  
**目标**: 为 `ablation/` 设计统一的模块开关与消融实验矩阵

---

## 1. 设计原则

### 1.1 核心目标

消融实验回答的问题是：**去掉哪个模块会发生什么**，而非继续往策略里堆模块。

### 1.2 两类消融实验

| 类型 | 目的 | 命名约定 |
|------|------|----------|
| **增量加入测试 (Additive)** | 从基线开始，逐层叠加模块，看每层贡献 | `A01`, `A02`, ... |
| **移除模块测试 (Subtractive)** | 从完整配置开始，逐层移除模块，看每层的必要程度 | `S01`, `S02`, ... |

### 1.3 与参数搜索的区别

- **消融实验**: 测试"模块是否存在"对结果的影响，模块内部参数保持默认
- **参数搜索**: 在模块存在的前提下，优化模块内部参数

**禁止将消融实验写成参数搜索**。

---

## 2. 模块开关总表

### 2.1 模块族与开关命名规范

| 模块族 | 开关前缀 | 覆盖范围 | 参考文档 |
|--------|----------|----------|----------|
| `universe` | `enable_universe_*` | 基础过滤、标的池定义 | 32_master_portfolio_assembly.md Step 1 |
| `alpha` | `enable_alpha_*` | 选股逻辑、因子打分、信号生成 | 32_master_portfolio_assembly.md Step 2 |
| `router` | `enable_router_*` | 主路由、市场状态判断、择时 | 32_master_portfolio_assembly.md Step 3 |
| `confirmation` | `enable_confirmation_*` | 二级确认、投票、过滤器 | 32_master_portfolio_assembly.md Step 4, 37_signal_confirmation_interface.md |
| `risk` | `enable_risk_*` | 仓位缩放、风险预算、止损 | 32_master_portfolio_assembly.md Step 5, Step 8 |
| `portfolio` | `enable_portfolio_*` | 权重生成、组合优化 | 32_master_portfolio_assembly.md Step 6 |
| `execution` | `enable_execution_*` | 执行假设、成本、滑点 | 32_master_portfolio_assembly.md Step 7, 36_data_benchmark_cost_spec.md |

### 2.2 具体开关清单

#### 2.2.1 Universe 模块族

| 开关名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_universe_base_filter` | bool | true | 基础过滤（ST/停牌/次新） |
| `enable_universe_sector_limit` | bool | false | 行业限制 |
| `enable_universe_market_cap_filter` | bool | false | 市值过滤 |
| `enable_universe_liquidity_filter` | bool | true | 流动性过滤 |

#### 2.2.2 Alpha 模块族

| 开关名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_alpha_ffscore` | bool | true | FFScore 价值打分 |
| `enable_alpha_dividend_quality` | bool | false | 红利质量过滤 |
| `enable_alpha_momentum` | bool | false | 动量因子 |
| `enable_alpha_sector_rotation` | bool | false | 行业轮动 |
| `enable_alpha_event_boost` | bool | false | 事件增强 |

#### 2.2.3 Router 模块族

| 开关名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_router_state` | bool | true | 状态路由（03_state_router） |
| `enable_router_rsrs` | bool | true | RSRS 择时（08_rsrs_timing） |
| `enable_router_diffusion` | bool | false | 扩散指数（微盘分支） |

#### 2.2.4 Confirmation 模块族

| 开关名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_confirmation_signalmaker` | bool | true | SignalMaker 统一投票 |
| `enable_confirmation_dual_confirm` | bool | true | 双确认机制 |
| `enable_confirmation_reentry` | bool | true | 再进场状态机 |
| `enable_confirmation_emotion` | bool | false | 情绪开关（01_emotion_switch） |
| `enable_confirmation_consistency` | bool | false | 一致性风控（微盘） |
| `enable_confirmation_crowding` | bool | false | 拥挤度检测 |

#### 2.2.5 Risk 模块族

| 开关名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_risk_volatility_scaling` | bool | true | 波动率仓位缩放（10_volatility_position） |
| `enable_risk_trailing_stop` | bool | true | 移动止盈止损（17_trailing_stop） |
| `enable_risk_position_stop` | bool | true | 个股止损 |
| `enable_risk_market_stop` | bool | false | 市场级止损/熔断 |
| `enable_risk_time_stop` | bool | false | 时间止损 |

#### 2.2.6 Portfolio 模块族

| 开关名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_portfolio_index_enhancement` | bool | true | 指数增强底座（31_index_enhancement_base） |
| `enable_portfolio_epo` | bool | false | EPO 权重优化（25_epo_portfolio） |
| `enable_portfolio_es_risk_parity` | bool | false | ES 风险平价（27_es_risk_parity） |
| `enable_portfolio_single_stock_limit` | bool | true | 单票上限 |
| `enable_portfolio_sector_limit` | bool | true | 行业上限 |
| `enable_portfolio_cash_buffer` | bool | true | 现金缓冲 |

#### 2.2.7 Execution 模块族

| 开关名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_execution_cost_model` | bool | true | 成本模型（滑点+手续费） |
| `enable_execution_price_model` | bool | true | 成交价格模型（next_open/vwap/close） |
| `enable_execution_capacity_limit` | bool | false | 容量限制 |

---

## 3. 消融矩阵模板 (ablation_matrix.csv)

### 3.1 CSV 字段定义

```csv
experiment_id,experiment_type,experiment_name,description,baseline_config,target_module,switch_states,expected_behavior,metrics_focus,run_flag,notes
```

#### 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `experiment_id` | 实验唯一标识 | `A01`, `S03` |
| `experiment_type` | 实验类型 | `additive`, `subtractive`, `cross` |
| `experiment_name` | 实验名称 | 如 "+主路由" |
| `description` | 实验描述 | 详细说明实验目的 |
| `baseline_config` | 基线配置引用 | `baseline_v0`, `full_stack` |
| `target_module` | 目标模块 | 本次实验操作的核心模块 |
| `switch_states` | 开关状态 JSON | `{"enable_router_state": true, ...}` |
| `expected_behavior` | 预期行为 | 描述期望看到的变化 |
| `metrics_focus` | 重点关注指标 | `return,drawdown,calmar,turnover` |
| `run_flag` | 是否必跑 | `mandatory`, `recommended`, `optional` |
| `notes` | 备注 | 依赖、风险提示 |

### 3.2 消融矩阵示例

#### 3.2.1 增量加入序列 (Additive)

| experiment_id | experiment_type | experiment_name | target_module | run_flag |
|---------------|-----------------|-----------------|---------------|----------|
| A00 | additive | 纯基线 | none | mandatory |
| A01 | additive | +基础过滤 | universe | mandatory |
| A02 | additive | +Alpha层 | alpha | mandatory |
| A03 | additive | +主路由 | router | mandatory |
| A04 | additive | +二级确认 | confirmation | mandatory |
| A05 | additive | +风险缩放 | risk_scaling | mandatory |
| A06 | additive | +权重生成 | portfolio | mandatory |
| A07 | additive | +统一底座 | execution | mandatory |
| A08 | additive | 完整增强 | full_stack | mandatory |

#### 3.2.2 移除模块序列 (Subtractive)

| experiment_id | experiment_type | experiment_name | target_module | run_flag |
|---------------|-----------------|-----------------|---------------|----------|
| S00 | subtractive | 完整配置 | full_stack | mandatory |
| S01 | subtractive | -确认层 | confirmation | mandatory |
| S02 | subtractive | -主路由 | router | mandatory |
| S03 | subtractive | -风险缩放 | risk_scaling | mandatory |
| S04 | subtractive | -退出保护 | risk_exit | mandatory |
| S05 | subtractive | -权重约束 | portfolio_constraints | recommended |
| S06 | subtractive | -成本模型 | execution_cost | recommended |

---

## 4. 依赖与互斥规则

### 4.1 依赖约束表

| 模块 | 依赖前置 | 说明 |
|------|----------|------|
| `confirmation_dual_confirm` | `confirmation_signalmaker` | 双确认需要先有投票信号 |
| `confirmation_reentry` | `confirmation_dual_confirm` | 再进场需要双确认状态机 |
| `risk_trailing_stop` | `portfolio_index_enhancement` | 个股退出需要先有持仓 |
| `portfolio_epo` | `alpha_*` | 权重优化需要先有打分 |
| `portfolio_es_risk_parity` | `alpha_*` | 风险平价需要先有资产评分 |

### 4.2 互斥规则表

| 模块A | 模块B | 互斥原因 |
|-------|-------|----------|
| `router_diffusion` | `router_state` | 微盘扩散指数与状态路由二选一 |
| `portfolio_epo` | `portfolio_es_risk_parity` | EPO与ES风险平价权重算法互斥 |
| `enable_confirmation_consistency` | `router_state` | 一致性风控专为微盘设计，不混用 |

### 4.3 非法组合检测

```python
# 伪代码示例
def validate_switch_combination(switches):
    errors = []
    
    # 检测：微盘模块与普通主仓模块混用
    if switches.get('router_diffusion') and switches.get('router_state'):
        errors.append("微盘扩散指数与状态路由不可同时启用")
    
    # 检测：双确认依赖 SignalMaker
    if switches.get('confirmation_dual_confirm') and not switches.get('confirmation_signalmaker'):
        errors.append("双确认机制依赖 SignalMaker 投票接口")
    
    # 检测：再进场依赖双确认
    if switches.get('confirmation_reentry') and not switches.get('confirmation_dual_confirm'):
        errors.append("再进场状态机依赖双确认机制")
    
    # 检测：EPO 和 ES 风险平价互斥
    if switches.get('portfolio_epo') and switches.get('portfolio_es_risk_parity'):
        errors.append("EPO 与 ES 风险平价不可同时启用")
    
    # 检测：至少一个 Alpha 源
    alpha_switches = [k for k in switches if k.startswith('enable_alpha_') and switches[k]]
    if not alpha_switches and switches.get('portfolio_index_enhancement'):
        errors.append("指数增强需要至少一个 Alpha 源")
    
    return errors
```

---

## 5. 结果汇总结构

### 5.1 单实验结果字段

```json
{
  "experiment_id": "A03",
  "experiment_type": "additive",
  "module_delta": "+router_state",
  "metrics": {
    "return": {
      "annual_return": 0.15,
      "cumulative_return": 0.45,
      "alpha": 0.08,
      "excess_return": 0.06
    },
    "risk": {
      "max_drawdown": -0.12,
      "sharpe": 1.2,
      "calmar": 1.25,
      "sortino": 1.5,
      "drawdown_recovery_days": 45
    },
    "trading": {
      "win_rate": 0.55,
      "trade_count": 120,
      "avg_holding_days": 25,
      "turnover": 0.8,
      "profit_loss_ratio": 1.3
    },
    "cost": {
      "slippage_impact": -0.02,
      "fee_impact": -0.01,
      "post_cost_return": 0.12
    }
  },
  "delta_from_baseline": {
    "annual_return": 0.03,
    "max_drawdown": -0.05,
    "calmar": 0.25
  },
  "contribution_score": {
    "return_contribution": 0.25,
    "risk_reduction_contribution": 0.40,
    "efficiency_contribution": 0.20
  },
  "timestamp": "2026-04-03T10:00:00Z"
}
```

### 5.2 汇总报告结构

```json
{
  "ablation_summary": {
    "strategy_name": "stock_main_lowfreq",
    "strategy_type": "stock_main",
    "baseline_version": "v0",
    "full_stack_version": "v3",
    "experiment_count": {
      "additive": 9,
      "subtractive": 7,
      "cross": 0
    }
  },
  "module_effectiveness": [
    {
      "module": "router_state",
      "additive_experiment": "A03",
      "subtractive_experiment": "S02",
      "contribution_rank": 1,
      "key_benefit": "回撤控制",
      "key_metric_delta": {
        "max_drawdown": -0.08,
        "calmar": 0.35
      }
    }
  ],
  "layer_contribution": {
    "universe": {"score": 0.10, "primary_benefit": "数据质量"},
    "alpha": {"score": 0.30, "primary_benefit": "收益来源"},
    "router": {"score": 0.25, "primary_benefit": "回撤控制"},
    "confirmation": {"score": 0.15, "primary_benefit": "交易效率"},
    "risk": {"score": 0.10, "primary_benefit": "风险调整"},
    "portfolio": {"score": 0.05, "primary_benefit": "组合稳定性"},
    "execution": {"score": 0.05, "primary_benefit": "可比性"}
  },
  "illegal_combinations_encountered": [],
  "recommendations": {
    "must_keep": ["router_state", "alpha_ffscore", "risk_trailing_stop"],
    "optional": ["confirmation_emotion", "risk_time_stop"],
    "strategy_profile": "适合作为低频股票主仓"
  }
}
```

---

## 6. 默认实验序列

### 6.1 增量实验默认序列

```
A00: 纯买入持有（或等权基准）
A01: +universe 基础过滤
A02: +alpha 选股逻辑
A03: +router 主路由（状态路由）
A04: +confirmation 二级确认（SignalMaker + 双确认）
A05: +risk 波动率缩放
A06: +portfolio 权重约束
A07: +execution 统一底座（含成本）
A08: +risk 退出保护（移动止盈止损）
```

### 6.2 移除实验默认序列

```
S00: 完整配置（A08 结果）
S01: -confirmation（去掉二级确认）
S02: -router（去掉主路由，保留确认层）
S03: -risk_scaling（去掉波动率缩放）
S04: -risk_exit（去掉退出保护）
S05: -portfolio_constraints（去掉权重约束）
S06: -execution_cost（成本=0，看成本敏感度）
S07: -universe_filter（去掉基础过滤）
```

---

## 7. 适配不同 Strategy Profile

### 7.1 低频股票主仓 (stock_main_lowfreq)

**推荐消融重点**:
- 必须测试：router_state, confirmation_signalmaker, risk_trailing_stop
- 次要测试：alpha 层不同来源（FFScore vs 红利质量）
- 不建议测试：router_diffusion（微盘专用）

**默认序列**: 使用 6.1 和 6.2 的标准序列

### 7.2 ETF/多资产主仓 (etf_multi_asset)

**推荐消融重点**:
- 必须测试：router_rsrs, portfolio_epo/es_risk_parity
- 替换 router_state 为 router_rsrs
- 重点关注 portfolio 层不同算法的差异

**调整后的序列**:
```
A00: 纯买入持有
A01: +universe 资产池定义
A02: +alpha 资产评分
A03: +router RSRS 择时（替代状态路由）
A04: +confirmation 二级确认（可选）
A05: +portfolio EPO/ES 权重优化
A06: +execution 统一底座
```

### 7.3 微盘/小市值分支 (microcap)

**推荐消融重点**:
- 必须测试：router_diffusion, confirmation_consistency, confirmation_crowding
- 替换 router_state 为 router_diffusion
- 重点关注拥挤度检测和一致性风控

**调整后的序列**:
```
A00: 纯买入持有
A01: +universe 基础过滤（含市值）
A02: +alpha MAC动量
A03: +router 扩散指数（替代状态路由）
A04: +confirmation 情绪开关 + 一致性风控
A05: +confirmation 拥挤度检测
A06: +risk 波动率缩放 + 退出保护
```

### 7.4 不适合全量消融的策略类型

| 策略类型 | 原因 | 建议做法 |
|----------|------|----------|
| 事件驱动 | 信号稀疏、时间窗口短 | 只做 `+事件模块` 的增量测试，不做全量消融 |
| 宏观底部/极端信号 | 低频触发、战略属性 | 只做存在性测试，不做逐层消融 |
| 竞价/短线 | 主仓体系不支持 | 独立验证，不纳入主仓消融矩阵 |
| 单一因子实验 | 研究性质 | 只做因子本身的效果验证 |

---

## 8. 第一版最小实现建议

### 8.1 最小开关集合 (MVP)

为快速验证，第一版只需实现以下 12 个核心开关：

```python
# universe
enable_universe_base_filter

# alpha
enable_alpha_ffscore

# router
enable_router_state

# confirmation
enable_confirmation_signalmaker
enable_confirmation_dual_confirm
enable_confirmation_reentry

# risk
enable_risk_volatility_scaling
enable_risk_trailing_stop

# portfolio
enable_portfolio_index_enhancement

# execution
enable_execution_cost_model
```

### 8.2 最小实验集合

必跑的 5 个默认消融实验：

| 实验 | 类型 | 目的 |
|------|------|------|
| A00 | 基线 | 建立基准 |
| A03 | 增量 | 验证主路由价值 |
| A04 | 增量 | 验证确认层价值 |
| S01 | 移除 | 验证确认层必要性 |
| S04 | 移除 | 验证退出保护必要性 |

### 8.3 文件结构建议

```
strategy_kits/
├── ablation/
│   ├── __init__.py
│   ├── config/
│   │   ├── module_switches.yaml       # 开关定义
│   │   ├── dependency_rules.yaml      # 依赖规则
│   │   └── experiment_matrix.csv      # 实验矩阵
│   ├── core/
│   │   ├── switch_validator.py        # 开关组合验证
│   │   ├── experiment_runner.py       # 实验执行器
│   │   └── result_aggregator.py       # 结果汇总
│   └── templates/
│       ├── additive_sequence.yaml     # 增量序列模板
│       └── subtractive_sequence.yaml  # 移除序列模板
```

---

## 9. 关键结论

### 9.1 必须支持开关化的模块

1. **主路由** (`router_state`, `router_rsrs`, `router_diffusion`) - 决定"做不做"
2. **确认层** (`confirmation_signalmaker`, `confirmation_dual_confirm`, `confirmation_reentry`) - 决定"何时恢复"
3. **退出保护** (`risk_trailing_stop`) - 决定"何时退出"
4. **Alpha 源** (`alpha_ffscore`, `alpha_dividend_quality`, `alpha_momentum`) - 决定"选什么"
5. **成本模型** (`execution_cost_model`) - 决定"实盘可行性"

### 9.2 最危险的非法组合

| 排名 | 非法组合 | 风险 |
|------|----------|------|
| 1 | `reentry=true` + `dual_confirm=false` | 再进场机制无状态机支撑，可能过早恢复 |
| 2 | `router_state=true` + `router_diffusion=true` | 微盘与主仓路由逻辑冲突，信号混乱 |
| 3 | `confirmation_signalmaker=false` + `dual_confirm=true` | 双确认无信号源，永远处于 waiting 状态 |
| 4 | `alpha_*=all_false` + `portfolio_index_enhancement=true` | 无 Alpha 源却做指数增强，结果不可解释 |

### 9.3 消融与参数搜索的边界

| 场景 | 消融实验 | 参数搜索 |
|------|----------|----------|
| 测试"有无某模块" | ✓ | ✗ |
| 测试"模块A vs 模块B" | ✓ | ✗ |
| 优化模块内部阈值 | ✗ | ✓ |
| 优化权重/超参数 | ✗ | ✓ |
| 比较不同算法实现 | ✓ | ✗ |

---

## 10. 与现有文档的衔接

| 本文档 | 衔接文档 | 衔接点 |
|--------|----------|--------|
| 模块开关总表 | 32_master_portfolio_assembly.md | Step 0-8 的每个层级对应开关 |
| 增量实验序列 | 35_enhancement_replay_checklist.md | 默认实验矩阵的 V0→V3 对应 A00→A08 |
| 确认层开关 | 37_signal_confirmation_interface.md | 投票接口、双确认、再进场的开关化 |
| 验证模板 | 39_strategy_factory_execution_checklist.md | validation/ 目录的消融实验模板 |
| 结果汇总 | 33_master_validation_pipeline.md | 统一输出指标格式 |

---

**结论**: 本文档为 `ablation/` 提供了完整的模块开关设计与消融实验矩阵框架。后续任何策略都能复用同一套消融语言，区分"模块有效"与"参数偶然"，避免因组合依赖混乱导致结论失真。
