# 统一报告模板与结果台账设计

**版本**: v1.0  
**日期**: 2026-04-03  
**目标**: 为 `reporting/` 与 `artifacts/` 设计最终落地模板，让验证结果能自动生成统一报告并进入结果台账

---

## 1. 设计原则

### 1.1 三层报告体系

| 层级 | 报告类型 | 目标读者 | 核心用途 |
|------|----------|----------|----------|
| L1 | **单策略验证报告** | 策略研发者 | 记录单策略完整验证流程与结论 |
| L2 | **模块级验证报告** | 模块维护者 | 验证通用模块在多策略中的复用效果 |
| L3 | **批量结果索引** | 主仓管理者 | 快速比较多策略、多实验、多版本 |

### 1.2 收口原则

- 前 9 个任务的输出必须能在此收口
- 新策略跑完后能形成统一结果资产
- 主 agent 能快速比较多策略/多实验/多版本

---

## 2. 单策略验证报告模板 (validation_report.md)

### 2.1 文件命名规范

```
{strategy_id}_{strategy_type}_{version}_{timestamp}_validation_report.md

示例:
ffscore_value_stock_main_v3_20260403_validation_report.md
```

### 2.2 报告模板结构

```markdown
# 策略验证报告: {strategy_name}

## 1. 元数据 (Metadata)

| 字段 | 值 |
|------|-----|
| report_id | `{strategy_id}_{version}_{timestamp}` |
| strategy_name | 策略名称 |
| strategy_type | stock_main / etf_main / microcap / event / satellite |
| validation_version | v0 / v1 / v2 / v3 |
| created_at | 2026-04-03T10:00:00Z |
| validator | 验证者/子 agent |
| parent_report | 上级报告ID（如有） |

## 2. 策略分型 (Strategy Profile)

| 字段 | 值 |
|------|-----|
| profile_id | 引用的 profile 标识 |
| asset_class | 股票 / ETF / 多资产 |
| frequency | 日频 / 周频 / 月频 |
| expected_holding_days | 预期平均持仓天数 |
| capacity_expectation | 容量预期（大/中/小） |

## 3. 实验配置摘要 (Experiment Config)

### 3.1 模块开关状态

| 模块族 | 启用模块 | 开关状态 |
|--------|----------|----------|
| universe | base_filter | ✓ |
| alpha | ffscore | ✓ |
| router | state_router | ✓ |
| confirmation | signalmaker, dual_confirm | ✓ |
| risk | volatility_scaling, trailing_stop | ✓ |
| portfolio | index_enhancement | ✓ |
| execution | cost_model | ✓ |

### 3.2 数据与成本口径

| 字段 | 值 |
|------|-----|
| data_source | 数据来源 |
| benchmark | 基准指数 |
| start_date | 回测起始 |
| end_date | 回测结束 |
| in_sample_period | 样本内区间 |
| out_of_sample_period | 样本外区间 |
| commission_rate | 手续费率 |
| slippage_model | 滑点模型 |
| price_field | 成交价格字段 |

## 4. 核心指标结果 (Core Metrics)

### 4.1 收益类

| 指标 | 数值 | 单位 |
|------|------|------|
| cumulative_return | 0.00 | 小数 |
| annual_return | 0.00 | 小数 |
| alpha | 0.00 | 小数 |
| excess_return | 0.00 | 小数 |

### 4.2 风险类

| 指标 | 数值 | 单位 |
|------|------|------|
| max_drawdown | 0.00 | 小数 |
| annual_volatility | 0.00 | 小数 |
| sharpe_ratio | 0.00 | - |
| calmar_ratio | 0.00 | - |
| sortino_ratio | 0.00 | - |
| drawdown_recovery_days | 0 | 天 |

### 4.3 交易效率类

| 指标 | 数值 | 单位 |
|------|------|------|
| win_rate | 0.00 | 小数 |
| trade_count | 0 | 次 |
| avg_holding_days | 0 | 天 |
| turnover_annual | 0.00 | 倍 |
| profit_loss_ratio | 0.00 | - |

### 4.4 成本类

| 指标 | 数值 | 单位 |
|------|------|------|
| pre_cost_return | 0.00 | 小数 |
| post_cost_return | 0.00 | 小数 |
| fee_impact | 0.00 | 小数 |
| slippage_impact | 0.00 | 小数 |

## 5. 版本对照矩阵 (Version Comparison)

| 版本 | 年化收益 | 最大回撤 | Sharpe | Calmar | 胜率 | 换手率 | 费后Alpha | 结论 |
|------|----------|----------|--------|--------|------|--------|-----------|------|
| V0 原策略 | | | | | | | | |
| V1 统一口径 | | | | | | | | |
| V2 装配增强 | | | | | | | | |
| V3 完整底座 | | | | | | | | |

## 6. 稳定性分解 (Stability Analysis)

### 6.1 年度表现

| 年份 | 收益 | 回撤 | 超额 | 胜率 |
|------|------|------|------|------|
| 2020 | | | | |
| 2021 | | | | |
| ... | | | | |

### 6.2 市场状态表现

| 状态 | 定义 | 收益 | 回撤 | 占比 |
|------|------|------|------|------|
| 牛市 | 基准上涨>20% | | | |
| 震荡 | 基准-20%~20% | | | |
| 熊市 | 基准下跌>20% | | | |

### 6.3 样本内/外对照

| 区间 | 年化收益 | 最大回撤 | Calmar | 结论 |
|------|----------|----------|--------|------|
| 样本内 | | | | |
| 样本外 | | | | |

### 6.4 压力成本测试

| 成本假设 | 费后收益 | 影响幅度 | 结论 |
|----------|----------|----------|------|
| 5bps | | | |
| 10bps | | | |
| 20bps | | | |
| 30bps | | | |

## 7. 归因分析 (Attribution)

### 7.1 因子归因

| 因子 | 暴露 | 收益贡献 | 风险贡献 |
|------|------|----------|----------|
| 市值 | | | |
| 价值 | | | |
| 质量 | | | |
| 动量 | | | |
| 特异收益 | | | |

### 7.2 行业归因

| 行业 | 配置权重 | 收益贡献 | 回撤贡献 |
|------|----------|----------|----------|
| ... | | | |

## 8. 消融实验结果 (Ablation Results)

| 实验ID | 类型 | 模块变化 | 年化 | MaxDD | Calmar | 贡献度 |
|--------|------|----------|------|-------|--------|--------|
| A00 | 基线 | - | | | | - |
| A01 | 增量 | +universe | | | | |
| ... | | | | | | |

## 9. 诊断与回改映射 (Diagnostics)

| 观察现象 | 可能原因 | 建议回改层 | 优先级 |
|----------|----------|------------|--------|
| | | | |

## 10. 准入定档结论 (Admission Grade)

| 字段 | 值 |
|------|-----|
| grade | A / B / C / D / E |
| grade_definition | 主仓候选 / 过滤器候选 / 战略辅助 / OOS观察 / 淘汰 |
| primary_role | 策略在主仓体系中的最终角色 |
| oos_required | true / false |
| oos_tracking_period | 建议观察期 |
| next_action | 继续增强 / 进入OOS / 挂起 / 淘汰 |

## 11. 附录 (Appendix)

### 11.1 目标权重表示例
### 11.2 交易日志样本
### 11.3 异常点说明
```

---

## 3. 模块级验证报告模板

### 3.1 与整策略报告的区别

| 维度 | 模块级报告 | 整策略报告 |
|------|------------|------------|
| **验证对象** | 单个通用模块 | 完整策略装配 |
| **实验方式** | 多策略挂载对比 | 单策略版本对照 |
| **成功标准** | 改善某项指标 | 综合达标 |
| **归宿判断** | 是否可复用 | 是否可主仓 |
| **报告重点** | 跨策略一致性 | 单策略完整性 |

### 3.2 模块验证报告结构

```markdown
# 模块验证报告: {module_name}

## 1. 模块元数据

| 字段 | 值 |
|------|-----|
| module_id | 模块唯一标识 |
| module_type | 过滤器 / 路由 / 确认 / 风险 / 权重 |
| source_doc | 来源文档 |
| version | 模块版本 |

## 2. 挂载策略列表

| 策略ID | 策略类型 | 挂载方式 | 基线版本 | 增强版本 |
|--------|----------|----------|----------|----------|
| | | 替换/叠加 | | |

## 3. 跨策略效果汇总

| 指标改善项 | 改善策略数 | 恶化策略数 | 中性策略数 | 一致性评分 |
|------------|------------|------------|------------|------------|
| 回撤控制 | | | | |
| Calmar提升 | | | | |
| 换手降低 | | | | |
| 胜率改善 | | | | |

## 4. 复用度评估

| 评估项 | 评分 | 说明 |
|--------|------|------|
| 跨策略稳定性 | 1-5 | |
| 参数敏感度 | 1-5 | |
| 计算成本 | 1-5 | |
| 维护复杂度 | 1-5 | |

## 5. 复用建议

| 建议项 | 内容 |
|--------|------|
| 推荐应用场景 | |
| 不推荐场景 | |
| 必须前置条件 | |
| 典型误用警示 | |
```

---

## 4. 结果台账模板 (results_registry.csv)

### 4.1 CSV 字段定义

```csv
registry_id,experiment_date,strategy_id,strategy_name,strategy_type,validation_version,profile_id,grade,grade_reason,status,core_metrics_json,file_path,parent_registry_id,oos_registry_id,notes
```

### 4.2 字段详细说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `registry_id` | string | 台账唯一标识 | `REG_20260403_001` |
| `experiment_date` | date | 实验日期 | `2026-04-03` |
| `strategy_id` | string | 策略标识 | `ffscore_value_v3` |
| `strategy_name` | string | 策略名称 | `FFScore价值选股` |
| `strategy_type` | enum | 策略类型 | `stock_main` |
| `validation_version` | enum | 验证版本 | `v3` |
| `profile_id` | string | 引用的 profile | `stock_main_lowfreq_default` |
| `grade` | enum | 定档 | `A/B/C/D/E` |
| `grade_reason` | string | 定档原因简述 | `费后结果可接受，回撤控制良好` |
| `status` | enum | 当前状态 | `completed/oos_pending/oos_tracking/suspended` |
| `core_metrics_json` | json | 核心指标JSON | 见下方格式 |
| `file_path` | string | 完整报告路径 | `reporting/.../xxx_validation_report.md` |
| `parent_registry_id` | string | 父版本台账ID | `REG_20260401_001` |
| `oos_registry_id` | string | 关联OOS台账ID | `REG_20260403_OOS_001` |
| `notes` | string | 备注 | |

### 4.3 core_metrics_json 格式

```json
{
  "annual_return": 0.15,
  "max_drawdown": -0.12,
  "sharpe": 1.2,
  "calmar": 1.25,
  "win_rate": 0.55,
  "turnover": 0.8,
  "post_cost_alpha": 0.08,
  "in_sample_annual": 0.16,
  "oos_annual": 0.14
}
```

### 4.4 台账索引视图

为方便主 agent 快速查询，建立以下索引视图：

**按策略类型索引**:
```
results_registry_by_type.csv
- strategy_type, registry_ids (逗号分隔), latest_registry_id
```

**按定档索引**:
```
results_registry_by_grade.csv
- grade, registry_ids (逗号分隔), count
```

**按状态索引**:
```
results_registry_by_status.csv
- status, registry_ids (逗号分隔), count
```

---

## 5. 子 Agent 回执汇总模板

### 5.1 回执文件命名

```
{task_id}_任务_{task_name}_回执.md

示例:
01_任务_01_验证contract与目录骨架_回执.md
```

### 5.2 统一回执结构

```markdown
# 任务 {task_id} 回执: {task_name}

**任务**: {task_description}  
**完成时间**: {timestamp}  
**主结果文档**: {path_to_main_result}

---

## 1. 最终结论

{1-2句话概括任务核心结论}

## 2. 关键产出

### 2.1 字段/表格

| 名称 | 说明 | 约束 |
|------|------|------|
| | | |

### 2.2 推荐配置

| 配置项 | 推荐值 | 理由 |
|--------|--------|------|
| | | |

## 3. 依赖关系

### 3.1 依赖的任务
- [ ] task_xx: {原因}

### 3.2 被依赖的任务
- [ ] task_xx: {原因}

## 4. 是否可开始实现

- [ ] 可直接进入实现
- [ ] 需要前置任务完成
- [ ] 有待决问题

### 待决问题
{如有}

## 5. 关键风险/注意事项

{实施过程中需要注意的关键点}
```

### 5.3 主 Agent 回执汇总表

主 agent 维护一张汇总表，聚合所有子 agent 回执：

```markdown
# 子 Agent 回执汇总

**汇总时间**: 2026-04-03  
**总任务数**: 10  
**已完成**: 10  
**可实施**: X  

---

| 任务ID | 任务名称 | 状态 | 核心结论 | 关键产出 | 可实施 | 依赖 | 风险 |
|--------|----------|------|----------|----------|--------|------|------|
| 01 | 验证contract | 完成 | | | ✓ | 无 | |
| 02 | validation profile | 完成 | | | ✓ | 01 | |
| ... | | | | | | | |

## 关键依赖路径

```
01/02 -> 03~09 -> 10
```

## 待决问题汇总

| 任务ID | 问题 | 建议处理方式 |
|--------|------|--------------|
| | | |

## 实施建议

{主 agent 的整体建议}
```

---

## 6. 从实验结果到最终报告的汇总流程

### 6.1 流程图

```
实验执行完成
    ↓
[1] 生成 raw_results.json (各实验原始结果)
    ↓
[2] 运行结果聚合器 (result_aggregator.py)
    ↓
    ├──> 计算跨版本指标对比
    ├──> 计算稳定性分解
    └──> 生成归因摘要
    ↓
[3] 生成 validation_summary.json (中间汇总)
    ↓
[4] 运行报告生成器 (report_generator.py)
    ↓
    ├──> 渲染 validation_report.md
    ├──> 更新 results_registry.csv
    └──> 生成可视化图表
    ↓
[5] 运行准入定档器 (admission_grader.py)
    ↓
    ├──> 应用定档规则
    ├──> 输出 grade 和原因
    └──> 标记 OOS 需求
    ↓
[6] 最终报告归档
    ↓
artifacts/
├── reports/
│   └── {strategy_id}_{version}_validation_report.md
├── summaries/
│   └── {strategy_id}_{version}_validation_summary.json
└── registry/
    └── results_registry.csv (更新)
```

### 6.2 关键转换节点

| 节点 | 输入 | 输出 | 负责组件 |
|------|------|------|----------|
| 原始结果聚合 | raw_results/ | validation_summary.json | result_aggregator |
| 报告生成 | validation_summary.json + 模板 | validation_report.md | report_generator |
| 台账更新 | validation_summary.json | results_registry.csv | registry_updater |
| 定档裁决 | validation_summary.json | grade + oos_flag | admission_grader |

### 6.3 与 Admission / OOS / Walk-forward 的接口

```
validation_report.md
    ↓ (提取核心指标)
validation_summary.json
    ↓ (定档规则)
admission_decision.json
    ├──> A/B档: 进入主仓模块库
    ├──> C档: 进入战略辅助库
    ├──> D档: 进入 OOS 观察池 ──> walkforward_tracker
    └──> E档: 挂起/淘汰
```

**Admission 接口字段**:

```json
{
  "registry_id": "REG_20260403_001",
  "strategy_id": "xxx",
  "validation_summary": { ... },
  "admission": {
    "grade": "A",
    "grade_reason": "...",
    "primary_role": "主仓alpha",
    "oos_required": false,
    "next_action": "入库"
  }
}
```

**OOS 接口字段**:

```json
{
  "registry_id": "REG_20260403_001",
  "oos_tracking": {
    "status": "tracking",
    "start_date": "2026-04-03",
    "expected_end_date": "2026-10-03",
    "checkpoints": ["2026-05-03", "2026-07-03", "2026-10-03"],
    "alert_conditions": {
      "oos_underperformance": "< -5%",
      "drawdown_worsening": "> 1.5x 样本内",
      "turnover_spike": "> 2x 平均"
    }
  }
}
```

**Walk-forward 接口字段**:

```json
{
  "parent_registry_id": "REG_20260403_001",
  "wf_window_size": "2y",
  "wf_step_size": "6m",
  "wf_runs": [
    {"window": "2020-2022", "result_ref": "REG_xxx"},
    {"window": "2020H2-2022H2", "result_ref": "REG_xxx"}
  ],
  "wf_stability_score": 0.75
}
```

---

## 7. 第一版最小实现建议

### 7.1 MVP 报告模板

第一版只需实现以下章节：

1. **元数据** (strategy_name, type, version, date)
2. **核心指标结果** (收益/风险/交易/成本 4 类基础指标)
3. **版本对照矩阵** (V0-V3 核心指标对比表)
4. **准入定档结论** (grade, reason, next_action)

### 7.2 MVP 台账字段

```csv
registry_id,experiment_date,strategy_id,strategy_name,strategy_type,validation_version,grade,status,annual_return,max_drawdown,calmar,file_path
```

### 7.3 MVP 回执模板

只保留：
- 最终结论
- 关键产出表格
- 是否可实施
- 关键风险

### 7.4 目录结构建议

```
strategy_kits/validation/
├── reporting/
│   ├── templates/
│   │   ├── validation_report_full.md      # 完整模板
│   │   ├── validation_report_minimal.md   # MVP模板
│   │   └── module_validation_report.md    # 模块报告模板
│   ├── generators/
│   │   ├── report_generator.py
│   │   └── summary_aggregator.py
│   └── validators/
│       └── report_validator.py
├── artifacts/
│   ├── registry/
│   │   ├── results_registry.csv           # 主台账
│   │   ├── registry_by_type.csv           # 类型索引
│   │   └── registry_by_grade.csv          # 定档索引
│   ├── receipts/
│   │   └── subagent_receipts/             # 子agent回执
│   └── exports/
│       └── admission_decisions/           # 定档决策导出
└── contracts/
    └── reporting_contract.yaml            # 报告契约定义
```

---

## 8. 前 9 个任务输出口总览

| 任务 | 主输出 | 在本任务中的收口方式 |
|------|--------|----------------------|
| 01 验证 contract | 目录结构、契约定义 | 报告模板字段来源、文件命名规范 |
| 02 validation profile | profile 定义 | strategy_type, profile_id 字段 |
| 03 V0/V1/V2/V3 基线矩阵 | 版本对照定义 | 报告第 5 章节 Version Comparison |
| 04 消融实验矩阵 | 模块开关定义 | 报告第 8 章节 Ablation Results |
| 05 Walk-forward | OOS 滚动规则 | OOS 接口、状态流转 |
| 06 压力测试 | 成本敏感度模板 | 报告第 6.4 节压力成本测试 |
| 07 年度/状态切片 | 切片维度定义 | 报告第 6.1/6.2 节稳定性分解 |
| 08 归因诊断 | 归因字段、回改映射 | 报告第 7/9 章节 |
| 09 准入定档 | 定档规则 | 报告第 10 章节、Admission 接口 |

---

## 9. 关键结论

### 9.1 报告章节推荐（按优先级）

| 优先级 | 章节 | 理由 |
|--------|------|------|
| P0 | 元数据 + 核心指标 | 报告身份与结果基础 |
| P0 | 版本对照矩阵 | 增强前后对比核心 |
| P0 | 准入定档结论 | 最终裁决出口 |
| P1 | 稳定性分解 | 防止单年/单状态幻觉 |
| P1 | 归因分析 | 解释收益来源 |
| P2 | 消融实验 | 模块贡献度量化 |
| P2 | 诊断与回改 | 失败时指导 |

### 9.2 results_registry.csv 最关键字段

| 排名 | 字段 | 理由 |
|------|------|------|
| 1 | `registry_id` | 唯一标识，所有关联基础 |
| 2 | `strategy_id` + `validation_version` | 定位具体策略版本 |
| 3 | `grade` | 快速筛选主仓候选 |
| 4 | `core_metrics_json` | 跨策略比较的数据基础 |
| 5 | `file_path` | 追溯完整报告 |
| 6 | `status` | 跟踪生命周期 |

### 9.3 回执最小模板

```markdown
# 任务 XX 回执

## 最终结论
{1-2句话}

## 关键产出
| 名称 | 内容 |
|------|------|
| | |

## 是否可实施
- [ ] 可直接进入实现 / 需要前置 / 有待决问题

## 关键风险
{如有}
```

### 9.4 可直接进入实现

**可直接进入实现**，但需要先完成：
- [ ] 确定报告模板渲染引擎 (Markdown/Jinja2)
- [ ] 确定台账存储格式 (CSV/JSON/数据库)
- [ ] 实现 validation_summary.json 生成器

**建议实现顺序**:
1. 实现 MVP 报告模板 (4 个核心章节)
2. 实现简单台账 CSV (8 个核心字段)
3. 实现报告生成脚本
4. 逐步完善完整模板

---

## 10. 与现有文档的衔接

| 本文档 | 衔接文档 | 衔接点 |
|--------|----------|--------|
| 报告模板 | 33_master_validation_pipeline.md | 三层报告体系、必要指标列表 |
| 准入定档章节 | 38_strategy_admission_oos.md | 五级定档、裁决逻辑 |
| 模块报告 | 39_strategy_factory_execution_checklist.md | 通用机制验证、复用度评估 |
| 台账结构 | 35_enhancement_replay_checklist.md | V0-V3 实验结果登记 |
| 回执汇总 | 00_任务总览与执行说明.md | 10 个任务的收口 |

---

**结论**: 本文档为 `reporting/` 与 `artifacts/` 提供了完整的统一报告模板与结果台账设计。前 9 个任务的输出在此收口，形成可自动生成、可比较、可追溯的验证结果资产。
