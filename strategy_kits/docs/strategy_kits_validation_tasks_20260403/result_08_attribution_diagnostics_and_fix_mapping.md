# 任务08：归因诊断与回改映射设计结果

## 一、归因层次定义

### 1.1 第一版必须项（Phase 10）

**收益归因（必做）：**
- **市值归因** - 大盘vs小盘暴露贡献
- **风格归因** - 价值/质量/动量/规模四因子贡献（继承07文档风格因子）
- **特异收益** - 无法被因子解释的策略自身贡献

**风险归因（必做）：**
- **回撤归因** - 最大回撤期间的风格暴露、市值暴露、行业集中度
- **波动归因** - 年化波动率的市值贡献、风格贡献

**暴露监控（必做）：**
- **风格暴露时间序列** - 风格因子暴露在不同时段的变化
- **市值分布** - 持仓市值分布与基准偏离

---

### 1.2 可后置项（Phase 11+）

**行业归因（可后置）：**
- **行业归因细分** - 各行业具体贡献（第一版可简化为"行业集中度"指标）
- **行业轮动分析** - 行业暴露时间变化（需行业分类标准）

**动态因子（可后置）：**
- **动态风格因子** - 因子定义随市场环境变化（需更复杂模型）
- **因子衰减分析** - 因子有效性时间序列（需长期数据）

**交易归因（可后置）：**
- **交易成本归因** - 换手率对收益的拖累分解（需交易明细）
- **滑点归因** - 执行偏差分析（需成交数据）

**组合归因（可后置）：**
- **Brinson归因** - 配置效应vs选择效应（需基准成分权重）
- **多策略组合归因** - 策略间协同/冲突分析（需组合框架）

---

## 二、attribution_summary.json 字段建议

### 2.1 核心结构

```json
{
  "strategy_id": "stock_main_jq_001",
  "version_id": "stock_main_jq_001_v3",
  "attribution_timestamp": "2026-04-03T15:30:00",
  "sample_period": "20150101-20251231",
  "benchmark": "000300.XSHG",

  "return_attribution": {
    "total_return": 0.125,
    "benchmark_return": 0.08,
    "excess_return": 0.045,

    "factor_contribution": {
      "market_cap": {
        "large_cap_contribution": -0.015,
        "mid_cap_contribution": 0.008,
        "small_cap_contribution": 0.012,
        "total_market_cap_contribution": 0.005,
        "confidence": "high"
      },
      "style_factors": {
        "value": {
          "contribution": 0.018,
          "exposure": 0.32,
          "confidence": "medium"
        },
        "quality": {
          "contribution": 0.012,
          "exposure": 0.28,
          "confidence": "medium"
        },
        "momentum": {
          "contribution": -0.008,
          "exposure": -0.15,
          "confidence": "medium"
        },
        "size": {
          "contribution": 0.005,
          "exposure": 0.45,
          "confidence": "high"
        }
      },
      "industry_concentration": {
        "top3_industry_weight": 0.42,
        "max_industry_weight": 0.18,
        "benchmark_top3_weight": 0.35,
        "concentration_deviation": 0.07,
        "confidence": "high"
      },
      "specific_return": {
        "contribution": 0.015,
        "confidence": "low",
        "status": "unconfirmed"
      }
    },

    "factor_contribution_sum": 0.030,
    "specific_vs_factor_ratio": 0.33
  },

  "risk_attribution": {
    "max_drawdown": {
      "total_drawdown": -0.18,
      "drawdown_period": "2018-01-15 to 2018-10-12",
      "drawdown_recovery_days": 120,

      "drawdown_decomposition": {
        "market_cap_exposure_dd": {
          "small_cap_contribution": -0.08,
          "confidence": "high"
        },
        "style_exposure_dd": {
          "momentum_contribution": -0.05,
          "value_contribution": -0.02,
          "confidence": "medium"
        },
        "industry_concentration_dd": {
          "concentrated_industry_contribution": -0.03,
          "confidence": "low",
          "status": "unconfirmed"
        }
      }
    },

    "volatility": {
      "total_volatility": 0.22,
      "benchmark_volatility": 0.18,
      "excess_volatility": 0.04,

      "volatility_decomposition": {
        "market_cap_vol_contribution": 0.02,
        "style_vol_contribution": 0.015,
        "specific_vol_contribution": 0.005,
        "confidence": "medium"
      }
    }
  },

  "exposure_monitoring": {
    "style_exposure_timeline": {
      "value_exposure_trend": "stable",
      "quality_exposure_trend": "stable",
      "momentum_exposure_trend": "declining",
      "size_exposure_trend": "stable",
      "confidence": "medium"
    },
    "market_cap_distribution": {
      "large_cap_weight": 0.25,
      "mid_cap_weight": 0.35,
      "small_cap_weight": 0.40,
      "micro_cap_weight": 0.00,
      "benchmark_large_cap": 0.70,
      "benchmark_small_cap": 0.10,
      "deviation_score": 0.35,
      "confidence": "high"
    }
  },

  "attribution_quality": {
    "data_quality_issues": [],
    "proxy_data_warnings": ["财务数据使用公告期而非报告期"],
    "factor_model_limitations": ["风格因子定义为简化版本，未包含动态调整"],
    "confidence_level": "medium",
    "unconfirmed_items": ["specific_return", "industry_concentration_dd"]
  },

  "next_action_recommendation": {
    "priority": "check_alpha_layer",
    "reason": "特异收益占比偏低，风格因子贡献占主导",
    "confidence": "medium"
  }
}
```

---

### 2.2 字段说明

**必须字段（第一版）：**

| 字段路径 | 类型 | 说明 | 置信度要求 |
|---------|------|------|-----------|
| `strategy_id` | string | 策略ID，继承任务01命名规范 | - |
| `version_id` | string | 版本ID（V0-V3） | - |
| `return_attribution.total_return` | float | 累计收益 | - |
| `return_attribution.factor_contribution.market_cap` | object | 市值归因结果 | confidence: high/medium/low |
| `return_attribution.factor_contribution.style_factors` | object | 风格因子归因 | confidence: medium/low |
| `return_attribution.factor_contribution.industry_concentration` | object | 行业集中度指标 | confidence: high |
| `return_attribution.factor_contribution.specific_return` | object | 特异收益 | confidence: low，必须标记status |
| `risk_attribution.max_drawdown.drawdown_decomposition` | object | 回撤归因 | confidence: medium/low |
| `exposure_monitoring.market_cap_distribution` | object | 市值分布偏离 | confidence: high |
| `attribution_quality.unconfirmed_items` | array | 未确认项目列表 | 必填 |

**可选字段（后置）：**

| 字段路径 | 类型 | 说明 | Phase |
|---------|------|------|-------|
| `return_attribution.factor_contribution.industry` | object | 行业归因细分 | Phase 11+ |
| `risk_attribution.volatility.volatility_decomposition` | object | 波动归因分解 | Phase 11+ |
| `exposure_monitoring.style_exposure_timeline` | object | 风格暴露时间序列 | Phase 10 |

---

### 2.3 置信度标注规则

**必须标注置信度的字段：**
- 所有归因贡献值（factor_contribution.*）
- 所有暴露偏离值（exposure_monitoring.*）

**置信度取值：**
- `high` - 数据可靠，模型稳健，可直接使用
- `medium` - 数据有一定代理偏差，模型简化，需谨慎使用
- `low` - 数据缺失较多或模型高度简化，必须标记status为unconfirmed

**status字段：**
- `confirmed` - 已确认，可直接引用
- `unconfirmed` - 未确认，需进一步验证，不可直接裁决
- `preliminary` - 初步结果，需后续补充

---

## 三、diagnostics_summary.json 字段建议

### 3.1 核心结构

```json
{
  "strategy_id": "stock_main_jq_001",
  "version_id": "stock_main_jq_001_v3",
  "diagnostics_timestamp": "2026-04-03T16:00:00",
  "diagnosis_version": "v1.0",

  "validation_results_summary": {
    "baseline_performance": {
      "grade": "D",
      "primary_issues": ["费后收益崩塌", "样本外失效"]
    },
    "stress_test_results": {
      "cost_sensitive": true,
      "cost_tier_failure": "stress"
    },
    "walkforward_results": {
      "oos_degradation": true,
      "oos_vs_in_sample_ratio": 0.45
    }
  },

  "failure_pattern_identification": [
    {
      "pattern_id": "FP01",
      "pattern_name": "费后崩塌",
      "evidence_strength": "strong",
      "affected_metrics": ["after_cost_alpha", "sharpe", "calmar"],
      "observed_values": {
        "before_cost_return": 0.15,
        "after_cost_return": 0.03,
        "cost_drag": 0.12
      },
      "diagnostic_conclusion": {
        "primary_module_to_fix": "execution_layer",
        "secondary_module_to_fix": "portfolio_layer",
        "fix_priority": "P0",
        "confidence": "high"
      }
    },
    {
      "pattern_id": "FP02",
      "pattern_name": "样本外失效",
      "evidence_strength": "medium",
      "affected_metrics": ["oos_return", "oos_sharpe"],
      "observed_values": {
        "in_sample_return": 0.18,
        "out_sample_return": 0.06,
        "oos_degradation_ratio": 0.67
      },
      "diagnostic_conclusion": {
        "primary_module_to_fix": "alpha_layer",
        "secondary_module_to_fix": "risk_layer",
        "fix_priority": "P0",
        "confidence": "medium",
        "status": "unconfirmed",
        "alternative_hypothesis": "数据代理偏差或过拟合"
      }
    },
    {
      "pattern_id": "FP03",
      "pattern_name": "高换手率",
      "evidence_strength": "strong",
      "affected_metrics": ["turnover_rate", "cost_drag"],
      "observed_values": {
        "turnover_rate": 8.5,
        "standard_cost_scenario": "failed",
        "stress_cost_scenario": "failed"
      },
      "diagnostic_conclusion": {
        "primary_module_to_fix": "portfolio_layer",
        "secondary_module_to_fix": "signal_layer",
        "fix_priority": "P1",
        "confidence": "high"
      }
    }
  ],

  "module_fix_mapping": {
    "execution_layer": {
      "module_path": "strategy_kits/execution/",
      "fix_recommendations": [
        {
          "issue": "成本敏感",
          "action": "降低换手率或优化成交时点",
          "priority": "P0",
          "expected_improvement": "费后收益提升30-50%"
        }
      ],
      "related_docs": ["36_data_benchmark_cost_spec.md", "31_index_enhancement_base.md"]
    },
    "portfolio_layer": {
      "module_path": "strategy_kits/portfolio/",
      "fix_recommendations": [
        {
          "issue": "权重映射过于频繁",
          "action": "延长持有期或引入衰减权重",
          "priority": "P1",
          "expected_improvement": "换手率降低50%"
        }
      ],
      "related_docs": ["34_alpha_weight_mapping.md"]
    },
    "alpha_layer": {
      "module_path": "strategy_kits/signals/",
      "fix_recommendations": [
        {
          "issue": "样本外失效",
          "action": "检查数据代理偏差或简化alpha逻辑",
          "priority": "P0",
          "expected_improvement": "样本外稳定性提升"
        }
      ],
      "related_docs": ["33_master_validation_pipeline.md"]
    }
  },

  "fix_priority_order": [
    {
      "priority": "P0",
      "module": "execution_layer",
      "reason": "费后崩塌直接影响实盘可用性"
    },
    {
      "priority": "P0",
      "module": "alpha_layer",
      "reason": "样本外失效表明策略本质问题"
    },
    {
      "priority": "P1",
      "module": "portfolio_layer",
      "reason": "高换手率是次要但重要问题"
    }
  ],

  "diagnostic_warnings": [
    {
      "warning_type": "alternative_hypothesis",
      "description": "样本外失效可能由数据代理偏差引起，而非alpha本身失效",
      "affected_pattern": "FP02",
      "recommendation": "检查36文档数据代理偏差说明"
    },
    {
      "warning_type": "unconfirmed_conclusion",
      "description": "alpha_layer问题未完全确认，需结合归因分析进一步验证",
      "affected_pattern": "FP02",
      "recommendation": "检查attribution_summary.json中的特异收益占比"
    }
  ],

  "next_action": {
    "immediate_fix": "execution_layer",
    "fix_sequence": ["execution_layer", "alpha_layer", "portfolio_layer"],
    "validation_after_fix": "重新跑33文档验证流程",
    "expected_validation_grade": "C or higher"
  }
}
```

---

### 3.2 字段说明

**必须字段（第一版）：**

| 字段路径 | 类型 | 说明 | 来源 |
|---------|------|------|------|
| `strategy_id` | string | 策略ID | 继承任务01 |
| `failure_pattern_identification` | array | 失败模式列表 | 继承33文档诊断映射 |
| `failure_pattern_identification[*].pattern_name` | string | 失败现象名称 | 33文档诊断表 |
| `failure_pattern_identification[*].diagnostic_conclusion` | object | 诊断结论 | 本任务设计 |
| `module_fix_mapping` | object | 模块回改映射 | 39文档strategy_kits目录 |
| `fix_priority_order` | array | 回改优先级排序 | 诊断逻辑 |
| `diagnostic_warnings` | array | 误诊警告 | 本任务设计 |

---

## 四、现象 -> 优先回改模块映射表

### 4.1 核心映射（继承33文档，扩展细化）

| 现象 | 优先回改模块 | 具体子模块 | 判断依据 | 置信度 | 未确认标记 |
|------|-------------|-----------|---------|--------|-----------|
| **收益不足** | alpha_layer | strategy_kits/signals/ | 特异收益占比<20%，风格因子贡献占主导 | medium | 需检查归因确认 |
| **回撤过大** | risk_layer | strategy_kits/risk/ | MaxDD>25%，回撤归因显示市值/风格暴露过度 | high | - |
| **回撤过大（次优）** | portfolio_layer | strategy_kits/portfolio/ | 回撤来自仓位缩放或权重集中 | medium | 需检查仓位历史 |
| **交易过多** | signal_layer | strategy_kits/signals/ | 信号频繁翻转，持有期<5天 | high | - |
| **交易过多（次优）** | confirmation_layer | strategy_kits/signals/regime_filters/ | 缺少确认层过滤 | medium | - |
| **换手过高** | portfolio_layer | strategy_kits/portfolio/ | 年化换手>6倍，权重映射不稳定 | high | - |
| **换手过高（次优）** | execution_layer | strategy_kits/execution/ | 成交时点选择不当导致频繁调整 | medium | - |
| **费后崩塌** | execution_layer | strategy_kits/execution/ | 费前收益>12%，费后收益<4%，成本拖累>8% | high | - |
| **费后崩塌（次优）** | portfolio_layer | strategy_kits/portfolio/ | 换手率过高导致成本累积 | medium | 需检查换手率 |
| **样本外失效** | alpha_layer | strategy_kits/signals/ | 样本外收益<样本内50%，OOS持续衰退 | medium | **必须标记未确认** |
| **样本外失效（替代假设）** | data_layer | docs/universal_mechanisms/36 | 数据代理偏差或未来函数 | low | **必须标记替代假设** |
| **只在少数年份有效** | attribution_layer | strategy_kits/validation/attribution/ | 归因显示单一风格暴露或单一行业押注 | high | - |
| **Calmar过低** | risk_layer + portfolio_layer | strategy_kits/risk/ + portfolio/ | 回撤大且收益低，综合问题 | high | - |
| **胜率过低** | signal_layer | strategy_kits/signals/ | 信号质量低，需强化alpha或增加确认层 | medium | - |
| **波动过高** | portfolio_layer | strategy_kits/portfolio/ | 仓位缩放不稳定或权重分散度不足 | medium | - |

---

### 4.2 映射规则

**优先级判定：**
- `P0` - 直接影响实盘可用性（费后崩塌、样本外失效、回撤过大）
- `P1` - 显著影响风险调整收益（换手过高、交易过多）
- `P2` - 优化项（胜率偏低、波动偏高）

**置信度判定：**
- `high` - 指标证据明确，可直接回改
- `medium` - 需结合归因或压力测试进一步确认
- `low` - 必须标记未确认或替代假设

**未确认标记规则：**
- 样本外失效必须标记`status: unconfirmed`
- 数据代理偏差问题必须标记`alternative_hypothesis`
- 特异收益占比异常必须结合归因置信度判断

---

## 五、最小归因流程建议

### 5.1 Phase 10 第一版流程

```text
基线验证完成（V0-V3对照）
        ↓
从baseline_matrix提取指标
        ↓
识别失败现象（从33文档诊断表）
        ↓
触发归因分析
        ↓
Step 1：计算市值归因（confidence: high）
        ↓
Step 2：计算风格归因（confidence: medium）
        ↓
Step 3：计算特异收益（confidence: low，标记unconfirmed）
        ↓
Step 4：计算回撤归因（confidence: medium）
        ↓
Step 5：生成attribution_summary.json
        ↓
进入诊断流程
        ↓
Step 6：匹配失败现象到模块（module_fix_mapping）
        ↓
Step 7：生成fix_priority_order
        ↓
Step 8：标记未确认结论（diagnostic_warnings）
        ↓
Step 9：生成diagnostics_summary.json
        ↓
输出到admission/（准入裁决参考）
        ↓
输出到reporting/（诊断建议章节）
```

---

### 5.2 归因触发条件

**必须触发归因的情况（继承33文档）：**
- 基线对照显示V3版本未达A档或B档
- 压力测试在标准成本档位失败
- 样本外收益显著低于样本内（>30%衰退）
- 最大回撤超过策略类型阈值（主仓>25%）

**可选触发归因的情况：**
- 增强前后差异需要解释
- 风格暴露监控发现异常偏离
- 用户主动请求归因分析

---

### 5.3 归因计算依赖

**第一版必须输入：**
- 持仓权重时间序列（从回测平台输出）
- 基准成分权重时间序列（从数据源获取）
- 股票市值数据（从数据源获取）
- 风格因子定义（继承07文档：value/quality/momentum/size）

**第一版可选输入：**
- 行业分类标准（后置Phase 11）
- 动态因子模型（后置Phase 11+）

---

## 六、常见误诊清单

### 6.1 五大误诊风险

**误诊1：将样本外失效直接判定为alpha失效**

**现象：** 样本外收益低于样本内50%，直接诊断为alpha_layer问题。

**误诊原因：** 未排除数据代理偏差、未来函数、样本切分不合理等替代假设。

**正确做法：**
- 检查36文档数据代理偏差说明
- 检查future_data_avoidance标记
- 标记`status: unconfirmed`，列出替代假设
- 结合归因分析特异收益占比判断

**置信度：** medium → 需进一步确认

---

**误诊2：将费后崩塌直接判定为成本敏感**

**现象：** 费后收益显著低于费前，直接诊断为execution_layer成本问题。

**误诊原因：** 未检查换手率是否才是根本原因。

**正确做法：**
- 先检查换手率（若>6倍，优先诊断为portfolio_layer）
- 检查成本档位（若压力成本失败，确认为execution_layer）
- 结合两者生成secondary_module_to_fix

**置信度：** high → 但需检查换手率

---

**误诊3：将回撤过大直接判定为风控问题**

**现象：** 最大回撤>25%，直接诊断为risk_layer止损不足。

**误诊原因：** 未检查回撤归因，可能是市值暴露或风格暴露过度。

**正确做法：**
- 先检查回撤归因（market_cap_exposure_dd, style_exposure_dd）
- 若市值/风格暴露贡献>60%，诊断为alpha_layer或portfolio_layer
- 若仓位缩放贡献显著，诊断为portfolio_layer
- 只有风控规则缺失时才诊断为risk_layer

**置信度：** medium → 需回撤归因确认

---

**误诊4：将特异收益低直接判定为alpha失效**

**现象：** 特异收益占比<20%，直接诊断为alpha_layer问题。

**误诊原因：** 特异收益计算本身置信度低，可能是因子模型简化导致。

**正确做法：**
- 检查attribution_quality.factor_model_limitations
- 标记`confidence: low`，status: unconfirmed
- 结合风格因子暴露稳定性判断
- 只有风格因子贡献也异常时才诊断为alpha_layer

**置信度：** low → 必须标记未确认

---

**误诊5：将行业集中度高直接判定为alpha押注**

**现象：** 行业集中度偏离基准>10%，直接诊断为alpha_layer行业押注。

**误诊原因：** 未检查是否是基准成分变化或数据代理偏差。

**正确做法：**
- 检查benchmark成分历史数据来源
- 检查是否使用代理基准（可能导致偏差）
- 标记`confidence: low`，status: unconfirmed
- 结合行业归因细分进一步验证（后置Phase 11）

**置信度：** low → 必须标记未确认

---

### 6.2 误诊预防机制

**机制1：置信度强制标注**
- 所有归因结果必须标注confidence: high/medium/low
- low置信度必须标记status: unconfirmed

**机制2：替代假设列出**
- 样本外失效必须列出alternative_hypothesis: 数据代理偏差/过拟合/样本切分
- 费后崩塌必须检查换手率作为替代假设

**机制3：二次确认流程**
- alpha_layer诊断必须结合归因分析确认
- portfolio_layer诊断必须检查仓位历史
- data_layer诊断必须检查36文档数据代理偏差说明

**机制4：警告机制**
- diagnostics_summary.json必须包含diagnostic_warnings数组
- 所有未确认结论必须在warnings中列出

---

## 七、诊断结论模板

### 7.1 标准诊断结论模板

```json
{
  "diagnostic_conclusion": {
    "primary_module_to_fix": "{module_name}",
    "secondary_module_to_fix": "{module_name or null}",
    "fix_priority": "P0/P1/P2",
    "confidence": "high/medium/low",
    "status": "confirmed/unconfirmed/preliminary",
    "alternative_hypothesis": "{hypothesis or null}",
    "expected_improvement": "{improvement description}",
    "related_docs": ["{doc_path_1}", "{doc_path_2}"]
  }
}
```

---

### 7.2 模块路径映射（继承39文档）

| 模块名称 | strategy_kits路径 | 相关文档 |
|---------|------------------|---------|
| alpha_layer | strategy_kits/signals/ | 33/35/39文档 |
| signal_layer | strategy_kits/signals/ | 33/37文档 |
| confirmation_layer | strategy_kits/signals/regime_filters/ | 37文档 |
| risk_layer | strategy_kits/risk/ | 33/17文档 |
| portfolio_layer | strategy_kits/portfolio/ | 34/10文档 |
| execution_layer | strategy_kits/execution/ | 36/31文档 |
| attribution_layer | strategy_kits/validation/attribution/ | 07/33文档 |
| data_layer | docs/universal_mechanisms/36 | 36文档 |

---

### 7.3 诊断报告章节模板

**继承33文档三层报告结构，归因与诊断章节：**

```markdown
## C. 归因分解

### C.1 收益归因
- 市值因子贡献：{market_cap_contribution}（置信度：{confidence}）
- 风格因子贡献：{style_factors_contribution}（置信度：{confidence}）
- 特异收益贡献：{specific_return_contribution}（置信度：{confidence}，状态：{status}）

### C.2 风险归因
- 回撤归因：{drawdown_decomposition}（置信度：{confidence}）
- 波动归因：{volatility_decomposition}（置信度：{confidence}）

### C.3 暴露监控
- 市值分布偏离：{market_cap_deviation}（置信度：{confidence}）
- 风格暴露稳定性：{style_exposure_trend}（置信度：{confidence}）

### C.4 归因质量说明
- 未确认项目：{unconfirmed_items}
- 数据质量问题：{data_quality_issues}
- 因子模型局限：{factor_model_limitations}

---

## D. 诊断建议

### D.1 失败现象识别
- 主要失败模式：{primary_failure_patterns}
- 受影响指标：{affected_metrics}
- 证据强度：{evidence_strength}

### D.2 优先回改模块
- 第一优先级：{priority_1_module}（原因：{reason}）
- 第二优先级：{priority_2_module}（原因：{reason}）
- 第三优先级：{priority_3_module}（原因：{reason}）

### D.3 回改建议
- {module_name}：{fix_recommendation}（预期改善：{expected_improvement}）

### D.4 未确认结论警告
- {warning_description}（建议：{recommendation}）

### D.5 下一步动作
- 立即修复：{immediate_fix}
- 修复顺序：{fix_sequence}
- 修复后验证：{validation_after_fix}
```

---

## 八、与切片、压力测试、准入定档的串联

### 8.1 串联流程

```text
walkforward/样本外验证
        ↓
识别OOS衰退 → 触发归因分析
        ↓
attribution/计算归因 → 输出attribution_summary.json
        ↓
stress/压力测试
        ↓
识别成本敏感 → 补充诊断证据
        ↓
regime_slices/市场状态切片
        ↓
识别风格暴露异常 → 补充归因证据
        ↓
diagnostics/综合诊断
        ↓
生成diagnostics_summary.json
        ↓
admission/准入裁决
        ↓
参考诊断结论定档（A/B/C/D/E）
        ↓
若D/E档 → 输出回改建议
        ↓
若OOS观察 → 标记未确认结论
        ↓
reporting/生成报告
        ↓
包含归因分解+诊断建议章节
```

---

### 8.2 数据流向

| 模块 | 输出 | 消费方 | 作用 |
|------|------|--------|------|
| walkforward | oos_degradation_flag | diagnostics | 触发样本外失效诊断 |
| stress | cost_sensitive_flag | diagnostics | 触发费后崩塌诊断 |
| regime_slices | style_exposure_deviation | attribution | 补充风格暴露归因 |
| attribution | attribution_summary.json | diagnostics, reporting | 提供归因证据 |
| diagnostics | diagnostics_summary.json | admission, reporting | 提供诊断结论 |
| admission | admission_decision.json | diagnostics（反向验证） | 验证诊断合理性 |

---

### 8.3 准入定档参考诊断

**继承38文档五级定档，诊断结论映射：**

| 定档 | 诊断特征 | 回改建议 |
|------|---------|---------|
| **A档** | 无P0失败现象，或P0现象已修复并验证 | 直接进入主仓候选 |
| **B档** | P1失败现象（换手/交易频率），可作为过滤器 | 优化portfolio_layer，进入过滤器候选 |
| **C档** | P2失败现象（胜率/波动），可作为战略辅助 | 优化signal_layer，进入辅助模块库 |
| **D档** | P0失败现象，未确认是否可修复 | 进入OOS观察，持续监控 |
| **E档** | P0失败现象，已确认无法修复或数据代理偏差严重 | 淘汰，保留研究记录 |

---

## 九、第一版落地建议

### 9.1 Phase 10 必做文件（5个）

1. **attribution/attribution_summary_template.json** - 归因摘要模板（定义所有字段）
2. **attribution/return_attribution_registry.yaml** - 收益归因登记表（列出必做归因项）
3. **diagnostics/diagnostics_summary_template.json** - 诊断摘要模板（定义所有字段）
4. **diagnostics/failure_pattern_registry.yaml** - 失败模式登记表（继承33文档诊断表）
5. **diagnostics/module_fix_mapping.yaml** - 模块回改映射表（本任务核心产出）

---

### 9.2 Phase 10 实现顺序

**Week 1：模板定义**
- 定义attribution_summary_template.json（Section 2）
- 定义diagnostics_summary_template.json（Section 3）

**Week 2：映射表**
- 定义failure_pattern_registry.yaml（继承33文档，扩展置信度）
- 定义module_fix_mapping.yaml（Section 4映射表）

**Week 3：流程串联**
- 定义return_attribution_registry.yaml（列出必做项）
- 实现归因触发条件检查（Section 5.2）
- 实现诊断流程（Section 5.1）

---

### 9.3 验收标准

**功能验收：**
- 能输出attribution_summary.json（包含市值/风格/特异收益归因）
- 能输出diagnostics_summary.json（包含失败现象→模块映射）
- 能标记未确认结论（status: unconfirmed）
- 能列出替代假设（alternative_hypothesis）

**质量验收：**
- 所有归因字段标注置信度
- 所有诊断结论标注fix_priority
- 未确认结论在diagnostic_warnings中列出
- 不再只给一句"策略失效了"

**闭环验收：**
- attribution输出能被diagnostics引用
- diagnostics输出能被admission引用
- admission定档能反向验证诊断合理性
- reporting能生成归因分解+诊断建议章节

---

## 十、风险与未决问题

### 10.1 主要风险

**风险1：归因模型简化导致特异收益不可信**

**缓解：** 标记confidence: low，status: unconfirmed，防止过度解释。

**验收：** attribution_summary.json必须包含unconfirmed_items数组。

---

**风险2：样本外失效误诊为alpha失效**

**缓解：** 必须列出替代假设，检查36文档数据代理偏差说明。

**验收：** diagnostics_summary.json必须包含alternative_hypothesis字段。

---

**风险3：费后崩塌误诊为成本敏感**

**缓解：** 先检查换手率，后诊断成本问题，生成primary + secondary模块。

**验收：** failure_pattern识别必须检查observed_values.turnover_rate。

---

### 10.2 未决问题

**问题1：归因计算由哪个平台提供？**

**建议：** 第一版依赖回测平台输出归因结果，validation只定义契约。

**待定：** 是否需要在strategy_kits/attribution_models/提供统一归因计算逻辑。

---

**问题2：风格因子定义是否统一？**

**建议：** 第一版继承07文档value/quality/momentum/size四因子定义。

**待定：** 是否需要动态因子模型（Phase 11+）。

---

**问题3：行业归因是否必须？**

**建议：** 第一版只做"行业集中度"指标，不做细分行业归因。

**待定：** Phase 11是否增加industry_attribution_registry。

---

**问题4：诊断结论是否自动生成？**

**建议：** 第一版由人工审核诊断结论，模板提供建议。

**待定：** Phase 12是否实现自动化诊断引擎。

---

## 十一、结论

本设计已完成：

1. ✅ 归因层次定义（收益归因、风险归因、暴露监控）
2. ✅ attribution_summary.json字段建议（26个必须字段）
3. ✅ diagnostics_summary.json字段建议（8个核心字段）
4. ✅ 现象→优先回改模块映射表（15条映射，继承33文档）
5. ✅ 置信度标注规则（high/medium/low）
6. ✅ 未确认标记规则（status: unconfirmed）
7. ✅ 最小归因流程建议（Phase 10第一版流程）
8. ✅ 诊断结论模板（标准化输出）
9. ✅ 五大误诊风险与预防机制
10. ✅ 与切片/压力测试/准入定档的串联流程
11. ✅ 第一版落地建议（5个必做文件）

**通过门槛验证：**

- ✅ 失败后能快速定位优先回改层（module_fix_mapping明确）
- ✅ 不再只给一句"策略失效了"（诊断结论包含primary/secondary模块）
- ✅ 能与统一报告和准入定档闭环（串联流程清晰）

---

**下一步建议：**

- 立即进入Phase 10实现（5个文件）
- Week 1完成模板定义
- Week 2完成映射表
- Week 3完成流程串联

---

**生成时间：** 2026-04-03
**文档版本：** v1.0
**依据文档：** 07/33/35/36/38/39 universal_mechanisms系列文档