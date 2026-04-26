# 任务01：验证 contract 与目录骨架设计结果

## 一、目录树建议

```
strategy_kits/validation/
├── contracts/              # 输入输出契约定义
├── profiles/               # 验证配置模板
├── baseline_matrix/        # 基线对照矩阵
├── ablation/               # 消融实验
├── walkforward/            # 滚动前向验证
├── stress/                 # 压力测试
├── regime_slices/          # 市场状态切片验证
├── attribution/            # 归因分析
├── diagnostics/            # 诊断工具
├── admission/              # 准入裁决
├── reporting/              # 报告生成
└── artifacts/              # 中间产物与最终输出
```

---

## 二、各目录职责边界

### 2.1 contracts/ - 输入输出契约定义

**负责：**
- 定义所有验证流程需要的输入契约格式
- 定义所有验证流程产出的输出契约格式
- 存放契约字段规范、必填项列表、类型约束
- 定义契约版本管理规则

**不负责：**
- 具体验证逻辑实现
- 实际策略数据存储
- 报告生成逻辑

**第一批最小文件：**
- `strategy_card_contract.yaml` - 策略卡片输入契约
- `validation_profile_contract.yaml` - 验证配置契约
- `validation_manifest_contract.yaml` - 验证清单输出契约
- `baseline_result_contract.yaml` - 基线结果契约
- `field_registry.yaml` - 全局字段命名注册表

**与其他目录的中间产物传递：**
- **输入：** 无（自己定义契约）
- **输出到：** profiles/（契约实例）、baseline_matrix/（基线结果格式）、artifacts/（所有输出产物格式）

---

### 2.2 profiles/ - 验证配置模板

**负责：**
- 存放不同策略类型的验证配置模板
- 定义验证强度、成本档位、样本切分规则
- 继承36文档的统一口径参数

**不负责：**
- 契约字段定义（由contracts/负责）
- 验证执行逻辑（由各验证模块负责）
- 最终裁决（由admission/负责）

**第一批最小文件：**
- `stock_main_validation_profile.yaml` - 股票低频主仓默认验证配置
- `etf_main_validation_profile.yaml` - ETF/多资产主仓验证配置
- `microcap_validation_profile.yaml` - 微盘策略验证配置
- `default_cost_tiers.yaml` - 继承36文档的默认成本档位
- `default_benchmarks.yaml` - 继承36文档的基准配置

**与其他目录的中间产物传递：**
- **输入：** contracts/（契约定义）、36文档统一口径参数
- **输出到：** baseline_matrix/（验证配置实例）、walkforward/（样本切分规则）、stress/（成本压力档位）

---

### 2.3 baseline_matrix/ - 基线对照矩阵

**负责：**
- 生成V0/V1/V2/V3四版基线对照
- 存放基线对照实验配置与结果索引
- 管理"原策略→统一口径→装配增强→完整底座"的四阶段对照

**不负责：**
- 消融实验（由ablation/负责）
- 参数搜索（不属于第一批）
- 归因分析（由attribution/负责）

**第一批最小文件：**
- `baseline_matrix_template.csv` - 基线矩阵模板（定义V0-V3四列）
- `baseline_experiment_registry.yaml` - 基线实验登记表
- `baseline_comparison_metrics.yaml` - 基线对照指标列表（继承33文档指标分类）

**与其他目录的中间产物传递：**
- **输入：** profiles/（验证配置）、contracts/（基线结果契约）、来自strategy_kits其他模块的装配结果
- **输出到：** reporting/（基线对照表）、diagnostics/（失败诊断映射）、admission/（基线表现判定）

---

### 2.4 ablation/ - 消融实验

**负责：**
- 设计消融实验矩阵（逐层剥离/逐层叠加）
- 存放消融实验配置与结果索引
- 定义"移除某层后效果如何"的实验逻辑

**不负责：**
- 基线对照（由baseline_matrix/负责）
- 参数网格搜索（不属于第一批）
- 敏感性分析的归因解释（由attribution/负责）

**第一批最小文件：**
- `ablation_matrix_template.csv` - 消融矩阵模板
- `ablation_experiment_registry.yaml` - 消融实验登记表
- `ablation_layer_definitions.yaml` - 定义可消融的层级（Alpha层/主路由/确认层/仓位/退出）

**与其他目录的中间产物传递：**
- **输入：** baseline_matrix/（基线结果作为起点）、contracts/（消融结果契约）
- **输出到：** diagnostics/（识别关键层）、reporting/（消融对照表）

---

### 2.5 walkforward/ - 滚动前向验证

**负责：**
- 定义样本内/样本外切分规则
- 存放滚动验证窗口配置
- 管理OOS观察期定义

**不负责：**
- 市场状态切片（由regime_slices/负责）
- 成本压力测试（由stress/负责）
- OOS接续判定（由admission/负责）

**第一批最小文件：**
- `walkforward_window_definitions.yaml` - 滚动窗口定义（继承36样本切分规则）
- `walkforward_results_template.csv` - 滚动验证结果模板
- `oos_observation_protocol.yaml` - OOS观察协议（继承38文档OOS标准）

**与其他目录的中间产物传递：**
- **输入：** profiles/（样本切分规则）、contracts/（窗口结果契约）
- **输出到：** reporting/（样本内/外对照）、admission/（OOS预警信号）、regime_slices/（时间窗口）

---

### 2.6 stress/ - 压力测试

**负责：**
- 定义成本压力档位（继承36文档成本口径）
- 定义极端场景测试配置
- 存放压力测试结果索引

**不负责：**
- 常规成本对照（由baseline_matrix/负责）
- 市场极端状态验证（由regime_slices/负责）
- 成本敏感性归因（由attribution/负责）

**第一批最小文件：**
- `stress_cost_tiers.yaml` - 成本压力档位（继承36文档5/10/20/30bps）
- `stress_scenario_registry.yaml` - 压力场景登记表
- `stress_results_template.csv` - 压力测试结果模板

**与其他目录的中间产物传递：**
- **输入：** profiles/（成本档位配置）、contracts/（压力结果契约）
- **输出到：** diagnostics/（成本脆弱性识别）、admission/（压力测试判定）

---

### 2.7 regime_slices/ - 市场状态切片验证

**负责：**
- 定义市场状态分类（牛市/震荡/下跌）
- 存放不同市场阶段的策略表现切片
- 管理风格暴露验证

**不负责：**
- 时间窗口切分（由walkforward/负责）
- 归因分析（由attribution/负责）
- 市场状态判定逻辑实现（由strategy_kits/signals/regime_filters/负责）

**第一批最小文件：**
- `regime_classification_definitions.yaml` - 市场状态分类定义
- `regime_slice_results_template.csv` - 市场切片结果模板
- `style_exposure_template.csv` - 风格暴露验证模板

**与其他目录的中间产物传递：**
- **输入：** walkforward/（时间窗口）、contracts/（切片结果契约）
- **输出到：** attribution/（风格归因输入）、reporting/（市场状态分解表）

---

### 2.8 attribution/ - 归因分析

**负责：**
- 收益归因（市值/行业/风格/特异）
- 回撤归因
- 增强前后差异归因

**不负责：**
- 消融实验设计（由ablation/负责）
- 诊断决策（由diagnostics/负责）
- 归因模型实现（由回测平台负责）

**第一批最小文件：**
- `attribution_summary_template.json` - 归因摘要模板
- `return_attribution_registry.yaml` - 收益归因登记表
- `drawdown_attribution_registry.yaml` - 回撤归因登记表

**与其他目录的中间产物传递：**
- **输入：** baseline_matrix/（基线结果）、regime_slices/（风格暴露）、contracts/（归因契约）
- **输出到：** reporting/（归因分解表）、diagnostics/（归因异常识别）

---

### 2.9 diagnostics/ - 诊断工具

**负责：**
- 从验证结果识别失败模式
- 提供诊断到模块的回改映射（继承33文档诊断表）
- 存放诊断规则与阈值配置

**不负责：**
- 验证执行（由各验证模块负责）
- 最终裁决（由admission/负责）
- 报告生成（由reporting/负责）

**第一批最小文件：**
- `failure_pattern_registry.yaml` - 失败模式登记表（继承33文档诊断映射）
- `diagnostic_thresholds.yaml` - 诊断阈值配置
- `module_remapping_guide.yaml` - 模块回改映射指南

**与其他目录的中间产物传递：**
- **输入：** baseline_matrix/（基线表现）、ablation/（消融结果）、stress/（压力测试）、attribution/（归因结果）
- **输出到：** admission/（诊断结论）、reporting/（诊断建议）

---

### 2.10 admission/ - 准入裁决

**负责：**
- 执行五级定档裁决（继承38文档A/B/C/D/E档）
- 判定OOS接续标准
- 输出准入决策文件

**不负责：**
- 验证执行（由各验证模块负责）
- 诊断分析（由diagnostics/负责）
- 报告生成（由reporting/负责）

**第一批最小文件：**
- `admission_decision_template.json` - 准入决策模板
- `admission_rules.yaml` - 准入裁决规则（继承38文档五级定档标准）
- `oos_tracking_requirements.yaml` - OOS跟踪要求（继承38文档OOS观察重点）

**与其他目录的中间产物传递：**
- **输入：** baseline_matrix/（基线表现）、walkforward/（OOS表现）、stress/（压力测试）、diagnostics/（诊断结论）
- **输出到：** reporting/（准入裁决表）、artifacts/（准入决策文件）

---

### 2.11 reporting/ - 报告生成

**负责：**
- 生成统一验证报告（继承33文档三层报告结构）
- 组装基线对照、稳定性分解、归因分解
- 输出人类可读的markdown报告

**不负责：**
- 验证逻辑执行（由各验证模块负责）
- 数据结构定义（由contracts/负责）
- 准入裁决逻辑（由admission/负责）

**第一批最小文件：**
- `validation_report_template.md` - 验证报告模板（继承33文档报告结构）
- `report_section_registry.yaml` - 报告章节登记表
- `metric_display_rules.yaml` - 指标展示规则

**与其他目录的中间产物传递：**
- **输入：** baseline_matrix/（基线对照表）、walkforward/（样本内/外对照）、stress/（压力测试）、regime_slices/（市场状态分解）、attribution/（归因分解）、admission/（准入裁决）
- **输出到：** artifacts/（最终报告文件）

---

### 2.12 artifacts/ - 中间产物与最终输出

**负责：**
- 存放所有验证流程产出的文件实例
- 管理验证结果版本
- 提供其他任务可引用的产物路径

**不负责：**
- 契约定义（由contracts/负责）
- 报告生成逻辑（由reporting/负责）
- 验证执行逻辑（由各验证模块负责）

**第一批最小文件：**
- `validation_manifest.yaml` - 验证清单（每次验证的元数据索引）
- `.gitignore` - 忽略大规模中间产物
- `README.md` - 产物目录说明

**与其他目录的中间产物传递：**
- **输入：** reporting/（报告文件）、admission/（准入决策）、各验证模块的中间结果
- **输出：** 提供其他任务可引用的最终产物路径

---

## 三、全局文件契约表

### 3.1 输入契约对象

| 文件名 | 契约类型 | 提供方 | 消费方 | 必填字段 | 说明 |
|--------|---------|--------|--------|---------|------|
| `strategy_card.yaml` | 输入契约 | strategy_kits/strategy_templates | validation/contracts | strategy_id, strategy_type, market, benchmark, alpha_modules, risk_modules, confirmation_modules, position_modules, execution_profile | 策略卡片，继承39文档策略卡片模板 |
| `validation_profile.yaml` | 输入契约 | validation/profiles | validation/各验证模块 | profile_id, strategy_type, benchmark, cost_tiers, sample_split_rule, oos_window, validation_strength | 验证配置，继承36文档统一口径参数 |
| `baseline_matrix.csv` | 输入契约 | validation/baseline_matrix | validation/ablation | experiment_id, strategy_id, V0_metrics, V1_metrics, V2_metrics, V3_metrics | 基线对照矩阵模板，继承33文档V0-V3定义 |
| `ablation_matrix.csv` | 输入契约 | validation/ablation | validation/diagnostics | experiment_id, layer_removed, metrics_change | 消融矩阵模板 |

### 3.2 输出契约对象

| 文件名 | 契约类型 | 提供方 | 消费方 | 必填字段 | 说明 |
|--------|---------|--------|--------|---------|------|
| `validation_manifest.yaml` | 输出契约 | validation/artifacts | 外部任务 | manifest_id, strategy_id, validation_timestamp, baseline_results_path, ablation_results_path, walkforward_results_path, stress_results_path, regime_results_path, attribution_path, admission_path, report_path | 验证清单，每次验证的元数据索引 |
| `baseline_results.csv` | 输出契约 | validation/baseline_matrix | validation/reporting | strategy_id, version_id, annual_return, max_drawdown, sharpe, calmar, win_rate, turnover, after_cost_alpha | 基线结果，继承33文档必要指标 |
| `walkforward_results.csv` | 输出契约 | validation/walkforward | validation/admission | window_id, strategy_id, sample_in_metrics, sample_out_metrics, oos_performance | 滚动验证结果 |
| `stress_results.csv` | 输出契约 | validation/stress | validation/diagnostics | scenario_id, cost_tier, metrics_under_stress | 压力测试结果，继承36文档成本档位 |
| `regime_slice_results.csv` | 输出契约 | validation/regime_slices | validation/attribution | regime_type, strategy_id, regime_metrics | 市场状态切片结果 |
| `attribution_summary.json` | 输出契约 | validation/attribution | validation/reporting | strategy_id, market_cap_attribution, industry_attribution, style_attribution, specific_return | 归因摘要，继承33文档归因指标 |
| `admission_decision.json` | 输出契约 | validation/admission | 外部任务 | strategy_id, grade, role, oos_required, rejection_reason, next_action | 准入决策，继承38文档五级定档 |
| `validation_report.md` | 输出契约 | validation/reporting | 外部任务 | 报告章节继承33文档三层报告结构 | 统一验证报告 |

### 3.3 中间产物契约

| 文件名 | 契约类型 | 作用 | 必填字段 |
|--------|---------|------|---------|
| `validation_config.yaml` | 配置实例 | 从profile生成具体验证配置 | 继承validation_profile契约 |
| `experiment_registry.yaml` | 实验登记 | 所有验证实验的索引 | experiment_id, experiment_type, status, timestamp |
| `metric_calculator_registry.yaml` | 指标计算器登记 | 指标计算规则索引 | metric_name, calculation_method, required_data |

---

## 四、命名规范

### 4.1 策略ID命名

**规则：** `{strategy_type}_{source_short}_{sequence_number}`

**示例：**
- `stock_main_jq_001` - 股票低频主仓，来源聚宽，编号001
- `etf_main_rq_003` - ETF主仓，来源 RiceQuant，编号003
- `microcap_jq_002` - 微盘策略，来源聚宽，编号002

**字段统一：** `strategy_id`

---

### 4.2 版本ID命名

**规则：** `{strategy_id}_v{version_number}`

**示例：**
- `stock_main_jq_001_v0` - 原策略基线版
- `stock_main_jq_001_v1` - 统一口径版
- `stock_main_jq_001_v2` - 装配增强版
- `stock_main_jq_001_v3` - 完整底座版

**字段统一：** `version_id`

---

### 4.3 实验ID命名

**规则：** `{strategy_id}_{experiment_type}_{timestamp}`

**示例：**
- `stock_main_jq_001_baseline_20260403` - 基线实验
- `stock_main_jq_001_ablation_20260403` - 消融实验
- `stock_main_jq_001_walkforward_20260403` - 滚动验证实验

**字段统一：** `experiment_id`

---

### 4.4 窗口ID命名

**规则：** `{strategy_id}_window_{window_index}_{window_type}`

**示例：**
- `stock_main_jq_001_window_01_in_sample` - 样本内窗口1
- `stock_main_jq_001_window_02_out_sample` - 样本外窗口2
- `stock_main_jq_001_window_03_oos` - OOS观察窗口

**字段统一：** `window_id`

---

### 4.5 成本档位命名

**继承36文档成本口径，字段统一：** `cost_tier`

**档位标签：**
- `standard` - 标准场景（股票0.03%佣金+0.10%滑点）
- `stress` - 压力场景（股票0.03%佣金+0.20%滑点）
- `extreme` - 极端场景（超出压力测试）

**字段组合：**
```yaml
cost_tier: standard
commission_rate: 0.0003
slippage_rate: 0.0010
```

---

### 4.6 OOS标签命名

**继承38文档OOS标准，字段统一：** `oos_label`

**标签值：**
- `in_sample` - 样本内
- `out_sample` - 样本外（验证期）
- `oos_observation` - OOS观察期（实盘跟踪）
- `oos_warning` - OOS预警（表现衰退）

---

### 4.7 其他关键统一字段

| 字段名 | 用途 | 来源文档 | 取值示例 |
|--------|------|---------|---------|
| `benchmark` | 基准代码 | 36文档 | `000300.XSHG` |
| `benchmark_type` | 基准类型 | 36文档 | `main_benchmark`, `horizontal_benchmark` |
| `sample_period` | 样本期 | 36文档 | `20150101-20251231` |
| `rebalance_freq` | 调仓频率 | 36文档 | `monthly`, `weekly`, `quarterly` |
| `execution_point` | 成交时点 | 36文档 | `next_open`, `vwap`, `close` |
| `use_real_price` | 真实价格开关 | 36文档 | `true`, `false` |
| `avoid_future_data` | 未来函数规避 | 36文档 | `true`, `false` |
| `data_proxy_bias` | 数据代理偏差说明 | 36文档 | 字符串描述 |
| `grade` | 定档等级 | 38文档 | `A`, `B`, `C`, `D`, `E` |
| `role` | 最终角色 | 38文档 | `main_candidate`, `filter_candidate`, `strategic_auxiliary`, `oos_pool`, `rejected` |

---

## 五、必须统一的字段列表（Top 10）

### 5.1 核心策略标识字段（4个）

1. **strategy_id** - 策略唯一标识，全局唯一，贯穿所有验证流程
2. **version_id** - 策略版本标识，用于V0-V3对照
3. **experiment_id** - 实验唯一标识，用于实验结果索引
4. **benchmark** - 基准代码，继承36文档基准规则

### 5.2 验证配置字段（3个）

5. **cost_tier** - 成本档位标签，继承36文档成本口径
6. **oos_label** - OOS标签，继承38文档OOS标准
7. **validation_strength** - 验证强度（`minimal`, `standard`, `full`）

### 5.3 准入裁决字段（3个）

8. **grade** - 定档等级，继承38文档五级定档
9. **role** - 最终角色，继承38文档角色分类
10. **next_action** - 下一步动作，继承38文档接续标准

---

## 六、推荐实现顺序

### Phase 0：契约先行（必做）

**优先级：P0**

1. 定义 `contracts/field_registry.yaml` - 全局字段注册表
2. 定义 `contracts/strategy_card_contract.yaml` - 策略卡片契约
3. 定义 `contracts/validation_profile_contract.yaml` - 验证配置契约
4. 定义 `contracts/validation_manifest_contract.yaml` - 验证清单契约

**验收标准：** 所有后续任务可直接引用这些契约定义

---

### Phase 1：继承统一口径（必做）

**优先级：P0**

5. 创建 `profiles/default_benchmarks.yaml` - 继承36文档基准配置
6. 创建 `profiles/default_cost_tiers.yaml` - 继承36文档成本档位
7. 创建 `profiles/stock_main_validation_profile.yaml` - 股票主仓验证配置模板

**验收标准：** 36文档统一口径参数完整映射到验证配置

---

### Phase 2：基线对照（必做）

**优先级：P0**

8. 创建 `baseline_matrix/baseline_matrix_template.csv` - 基线矩阵模板（V0-V3）
9. 创建 `baseline_matrix/baseline_experiment_registry.yaml` - 基线实验登记
10. 创建 `baseline_matrix/baseline_comparison_metrics.yaml` - 基线对照指标（继承33文档）

**验收标准：** 能生成V0/V1/V2/V3四版基线对照表

---

### Phase 3：准入裁决（必做）

**优先级：P0**

11. 创建 `admission/admission_decision_template.json` - 准入决策模板
12. 创建 `admission/admission_rules.yaml` - 准入裁决规则（继承38文档）
13. 创建 `admission/oos_tracking_requirements.yaml` - OOS跟踪要求

**验收标准：** 能输出五级定档决策文件

---

### Phase 4：报告生成（必做）

**优先级：P0**

14. 创建 `reporting/validation_report_template.md` - 验证报告模板（继承33文档三层结构）
15. 创建 `reporting/report_section_registry.yaml` - 报告章节登记
16. 创建 `reporting/metric_display_rules.yaml` - 指标展示规则

**验收标准：** 能生成包含基线对照、稳定性分解、归因分解的统一报告

---

### Phase 5：产物索引（必做）

**优先级：P0**

17. 创建 `artifacts/validation_manifest.yaml` - 验证清单元数据索引
18. 创建 `artifacts/README.md` - 产物目录说明

**验收标准：** 其他任务可通过validation_manifest引用验证结果

---

### Phase 6：压力测试（强烈建议）

**优先级：P1**

19. 创建 `stress/stress_cost_tiers.yaml` - 成本压力档位
20. 创建 `stress/stress_results_template.csv` - 压力测试结果模板

---

### Phase 7：样本外验证（强烈建议）

**优先级：P1**

21. 创建 `walkforward/walkforward_window_definitions.yaml` - 滚动窗口定义
22. 创建 `walkforward/walkforward_results_template.csv` - 滚动验证结果模板

---

### Phase 8：市场状态切片（强烈建议）

**优先级：P1**

23. 创建 `regime_slices/regime_classification_definitions.yaml` - 市场状态分类
24. 创建 `regime_slices/regime_slice_results_template.csv` - 市场切片结果模板

---

### Phase 9：诊断工具（建议）

**优先级：P1**

25. 创建 `diagnostics/failure_pattern_registry.yaml` - 失败模式登记（继承33文档诊断映射）
26. 创建 `diagnostics/diagnostic_thresholds.yaml` - 诊断阈值

---

### Phase 10：归因分析（建议）

**优先级：P2**

27. 创建 `attribution/attribution_summary_template.json` - 归因摘要模板
28. 创建 `attribution/return_attribution_registry.yaml` - 收益归因登记

---

### Phase 11：消融实验（建议）

**优先级：P2**

29. 创建 `ablation/ablation_matrix_template.csv` - 消融矩阵模板
30. 创建 `ablation/ablation_layer_definitions.yaml` - 消融层级定义

---

## 七、风险与未决问题

### 7.1 主要风险

**风险1：契约字段过多导致第一版实现负担**

- **缓解：** Phase 0只定义必填字段，可选字段在Phase 1-11逐步补充
- **验收：** 必填字段能支撑V0-V3基线对照

---

**风险2：各验证模块之间中间产物格式不一致**

- **缓解：** contracts/目录必须最先完成，所有模块引用同一套契约
- **验收：** baseline_matrix/、ablation/、walkforward/等模块输出格式可互相引用

---

**风险3：与36文档统一口径映射不完整**

- **缓解：** profiles/目录必须完整继承36文档的基准、成本、样本切分、执行口径参数
- **验收：** validation_profile.yaml包含36文档所有必填参数

---

**风险4：与38文档五级定档标准映射不清晰**

- **缓解：** admission/admission_rules.yaml必须完整继承38文档A/B/C/D/E档判定规则
- **验收：** admission_decision.json包含grade、role、next_action三个必填字段

---

**风险5：目录职责重叠**

- **缓解：** 本设计已明确12个目录的职责边界，不允许跨目录重新发明
- **验收：** 基线对照只在baseline_matrix/，消融实验只在ablation/，裁决只在admission/

---

### 7.2 未决问题

**问题1：验证流程编排引擎放在哪里？**

- **建议：** 第一版不做编排引擎，由手工调用各验证模块
- **待定：** 未来可能在strategy_kits/strategy_templates/增加orchestrator

---

**问题2：指标计算器是否需要统一注册？**

- **建议：** 第一版在baseline_matrix/baseline_comparison_metrics.yaml列出指标清单
- **待定：** 未来可能在strategy_kits/signals/增加metric_calculator_factory

---

**问题3：归因模型实现由哪个平台提供？**

- **建议：** 第一版只定义attribution_summary.json契约，归因计算由回测平台提供
- **待定：** 是否需要strategy_kits/attribution_models/提供统一归因计算逻辑

---

**问题4：OOS跟踪是否需要自动化？**

- **建议：** 第一版只定义oos_tracking_requirements.yaml协议，手工更新观察记录
- **待定：** 是否需要strategy_kits/oos_tracker/提供自动监控

---

**问题5：多策略组合验证如何处理？**

- **建议：** 第一版只处理单策略验证，组合验证契约待Phase 12设计
- **待定：** 是否需要contracts/portfolio_validation_contract.yaml

---

## 八、验收标准

### 8.1 契约可引用性

- **标准：** 其他任务可通过contracts/目录直接引用所有契约定义，无需口头解释

---

### 8.2 目录职责清晰性

- **标准：** 12个目录职责边界明确，无重叠，每个目录的"负责/不负责"清晰

---

### 8.3 统一口径承接完整性

- **标准：** profiles/目录完整映射36文档的基准、成本、样本切分、执行口径参数

---

### 8.4 准入裁决承接完整性

- **标准：** admission/目录完整映射38文档的五级定档、OOS接续标准

---

### 8.5 第一版可实现性

- **标准：** Phase 0-5（17个文件）可在第一版实现，Phase 6-11（13个文件）可后续补充

---

## 九、结论

本设计已完成：

1. ✅ 12个目录的职责边界定义
2. ✅ 30个第一批最小文件清单
3. ✅ 11个核心文件契约表（输入4个、输出9个）
4. ✅ 6类命名规范（策略ID、版本ID、实验ID、窗口ID、成本档位、OOS标签）
5. ✅ 10个必须统一的字段列表
6. ✅ 11个Phase的推荐实现顺序
7. ✅ 5个主要风险与缓解措施
8. ✅ 5个未决问题与待定建议

**通过门槛验证：**

- ✅ 看完结果后，其他任务可直接引用contracts/目录
- ✅ 目录职责没有明显重叠（baseline_matrix vs ablation vs walkforward职责清晰）
- ✅ 第一版实现顺序清楚（Phase 0-5必做，Phase 6-11后续）
- ✅ 不依赖额外口头解释（所有契约、命名、字段均文档化）

---

**下一步建议：**

- 立即进入Phase 0实现（contracts/目录4个文件）
- 并行推进Phase 1（profiles/目录3个文件）
- 然后依次完成Phase 2-5

---

**生成时间：** 2026-04-03
**文档版本：** v1.0
**依据文档：** 33/35/36/38/39 universal_mechanisms系列文档