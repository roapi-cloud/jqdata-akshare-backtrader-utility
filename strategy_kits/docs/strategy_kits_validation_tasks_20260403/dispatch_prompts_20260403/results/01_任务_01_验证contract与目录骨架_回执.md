# 任务01回执：验证 contract 与目录骨架设计

## 推荐保留的目录（12个）

**全部保留，职责边界已清晰定义：**

1. `contracts/` - 输入输出契约定义
2. `profiles/` - 验证配置模板（继承36文档统一口径）
3. `baseline_matrix/` - 基线对照矩阵（V0-V3）
4. `ablation/` - 消融实验
5. `walkforward/` - 滚动前向验证（样本内/外）
6. `stress/` - 压力测试（成本压力）
7. `regime_slices/` - 市场状态切片验证
8. `attribution/` - 归因分析
9. `diagnostics/` - 诊断工具（继承33文档诊断映射）
10. `admission/` - 准入裁决（继承38文档五级定档）
11. `reporting/` - 报告生成（继承33文档三层报告）
12. `artifacts/` - 中间产物与最终输出

---

## 第一版立即实现的5个文件（Phase 0）

**优先级P0，必须最先完成：**

1. **contracts/field_registry.yaml** - 全局字段注册表（定义所有统一字段）
2. **contracts/strategy_card_contract.yaml** - 策略卡片输入契约（继承39文档模板）
3. **contracts/validation_profile_contract.yaml** - 验证配置契约（继承36文档口径）
4. **contracts/validation_manifest_contract.yaml** - 验证清单输出契约（元数据索引）
5. **profiles/stock_main_validation_profile.yaml** - 股票主仓验证配置模板实例

**理由：** 这5个文件完成后，其他任务可直接引用契约定义，无需重新发明字段。

---

## 最关键的10个统一字段

**必须全局统一命名，不可在各模块重复定义：**

### 核心标识字段（4个）

1. **strategy_id** - 策略唯一标识（规则：`{strategy_type}_{source_short}_{sequence_number}`）
2. **version_id** - 策略版本标识（规则：`{strategy_id}_v{version_number}`，用于V0-V3对照）
3. **experiment_id** - 实验唯一标识（规则：`{strategy_id}_{experiment_type}_{timestamp}`）
4. **benchmark** - 基准代码（继承36文档，如`000300.XSHG`）

### 验证配置字段（3个）

5. **cost_tier** - 成本档位标签（继承36文档，取值：`standard`/`stress`/`extreme`）
6. **oos_label** - OOS标签（继承38文档，取值：`in_sample`/`out_sample`/`oos_observation`/`oos_warning`）
7. **validation_strength** - 验证强度（取值：`minimal`/`standard`/`full`）

### 准入裁决字段（3个）

8. **grade** - 定档等级（继承38文档，取值：`A`/`B`/`C`/`D`/`E`）
9. **role** - 最终角色（继承38文档，取值：`main_candidate`/`filter_candidate`/`strategic_auxiliary`/`oos_pool`/`rejected`）
10. **next_action** - 下一步动作（继承38文档接续标准）

---

## 最容易重复建设的地方（5个高风险点）

### 风险1：指标字段命名不一致

**现象：** 各验证模块可能分别定义"年化收益"字段，导致`annual_return`、`annualized_return`、`yearly_return`并存。

**预防：** `contracts/field_registry.yaml`必须在Phase 0完成，所有模块强制引用同一份字段注册表。

---

### 风险2：成本口径重新定义

**现象：** stress/、baseline_matrix/可能各自定义成本档位，导致与36文档不一致。

**预防：** `profiles/default_cost_tiers.yaml`必须完整继承36文档成本口径，stress模块引用profile配置，不允许重新定义。

---

### 风险3：基准配置分散定义

**现象：** 各验证模块可能分别定义基准代码，导致`benchmark`字段取值不一致。

**预防：** `profiles/default_benchmarks.yaml`必须完整继承36文档基准规则，所有模块引用同一份基准配置。

---

### 风险4：V0-V3版本定义不一致

**现象：** baseline_matrix可能重新定义V0/V1/V2/V3含义，与33文档不对应。

**预防：** `baseline_matrix/baseline_comparison_metrics.yaml`必须完整继承33文档V0-V3定义（原策略→统一口径→装配增强→完整底座），不允许重新解释。

---

### 风险5：五级定档标准重新发明

**现象：** admission模块可能重新定义A/B/C/D/E档判定规则，与38文档不一致。

**预防：** `admission/admission_rules.yaml`必须完整继承38文档五级定档标准，不允许补充新的档位或判定逻辑。

---

## 是否可直接进入实现

**✅ 可直接进入Phase 0-5实现**

**前提条件已满足：**

1. ✅ 12个目录职责边界已明确（"负责/不负责"清晰）
2. ✅ 30个第一批文件清单已列出
3. ✅ 11个文件契约表已定义（输入输出字段明确）
4. ✅ 6类命名规范已统一（策略ID/版本ID/实验ID/窗口ID/成本档位/OOS标签）
5. ✅ 10个统一字段已锁定
6. ✅ 11个Phase实现顺序已排序
7. ✅ 与33/35/36/38/39文档的承接关系已映射
8. ✅ 不依赖额外口头解释（所有契约文档化）

**建议实现路径：**

- **Week 1：** Phase 0（contracts/目录4个文件）
- **Week 2：** Phase 1-2（profiles/目录3个文件 + baseline_matrix/目录3个文件）
- **Week 3：** Phase 3-5（admission/目录3个文件 + reporting/目录3个文件 + artifacts/目录2个文件）

**验收标准：**

- Phase 0-5完成后，能输出包含基线对照、准入裁决、验证报告的完整验证清单
- 其他任务可通过`artifacts/validation_manifest.yaml`引用验证结果路径
- 无需口头解释即可使用contracts/目录契约

---

## 生成时间

2026-04-03

---

## 依据文档

- 33_master_validation_pipeline.md
- 35_enhancement_replay_checklist.md
- 36_data_benchmark_cost_spec.md
- 38_strategy_admission_oos.md
- 39_strategy_factory_execution_checklist.md

---

## 回执版本

v1.0