# FactorHub 到 strategy_kits 的迁移评估

日期: 2026-04-03

## 结论

`FactorHub` 里适合迁入 `strategy_kits` 的，不是整套“因子平台”，而是其中面向策略模板、验证、准入、结果台账的那一层。

更直接地说：

- 适合迁的是“策略装配与验证能力”
- 不适合迁的是“因子生命周期管理平台”
- 因子相关能力只适合以“策略输入层”的形式存在，不适合以“因子研究中心”的形式整体搬入

这和 `strategy_kits` 当前定位是一致的：它是编排层、验证层、组件层，不是执行层，也不是完整因子投研平台。

## 为什么这么判断

`strategy_kits` 的架构文档已经把边界写得很清楚：

- 核心职责是策略组装、验证流程、可复用组件
- 本地回测、数据获取、实盘交易依赖外部系统
- 因子只保留为“因子评分壳”，不保留策略专属因子列表、因子方向字典、标签定义、原始数据获取逻辑

而 `FactorHub` 自己在 README 和设计文档里的定位是：

- 因子管理
- 因子分析
- 因子挖掘
- 组合优化
- 策略回测

所以它天然比 `strategy_kits` 更重，也更偏“投研平台”。

## 适合迁入的部分

### 1. Profile Registry 和 Search Space Contract

最适合迁。

来源：

- `backend/services/factor_profile_registry_service.py`
- `config/temporal_pool_profiles.json`
- `config/cross_sectional_profiles.json`
- `config/strategy_search_space.json`

适合原因：

- 这是策略模板、搜索空间、运行时 profile 的配置契约
- 它本质上是“策略模板管理”，不是“因子平台”
- 很适合进入 `strategy_kits/strategy_templates/` 和 `strategy_kits/validation/profiles/`

迁入建议：

- 保留 `profile` / `search_space` 的文件式配置思想
- 保留热加载、运行时 inline profile、合法性校验
- 名称上尽量从 `factor_profile` 改成更中性的 `strategy_profile` 或 `signal_profile`

### 2. Walk-forward 评价和准入评分

非常适合迁，而且优先级很高。

来源：

- `backend/services/strategy_evaluation_service.py`

适合原因：

- 它做的是滚动窗口生成、稳定性总分、OOS 评价
- 这正是 `strategy_kits/validation/walkforward/`、`validation/admission/` 需要的东西
- 当前 `strategy_kits/validation/` 目录基本还是骨架，这部分可以直接补齐验证主干

迁入建议：

- 保留 walk-forward window generator
- 保留稳定性打分框架
- 把与 `TemporalFilterValidationService` 的强耦合改成注入式 evaluator 接口
- 不要把它继续绑定在 `FactorHub` 的数据目录和服务命名上

### 3. Champion Runner 和结果注册表

也很适合迁。

来源：

- `backend/services/champion_strategy_service.py`
- `backend/services/champion_registry_service.py`

适合原因：

- 这是策略准入、结果落盘、最佳配置选择的能力
- 本质是“策略版本治理”而不是“因子治理”
- 很适合进入 `strategy_kits/validation/admission/`、`validation/artifacts/`、`validation/reporting/`

迁入建议：

- 保留文件落盘和 scope 概念
- 保留 `single_stock` / `stock_group` / `cross_sectional` 这种作用域思想
- 但目录命名建议从 `champions/` 改成更中性的 `artifacts/admission/` 或 `artifacts/best_configs/`

### 4. Strategy Comparison

适合迁，但要轻量化。

来源：

- `backend/services/strategy_comparison_service.py`

适合原因：

- 这是标准的策略对比、指标表、统计检验、排名
- 很契合 `validation/baseline_matrix/` 和 `validation/reporting/`

迁入建议：

- 保留指标对比表、统计检验、综合排名
- 去掉对 `FactorHub` 内置策略注册表的耦合
- 改成接收统一的回测结果对象或收益序列

### 5. Temporal Pool 验证壳

适合部分迁入，不适合整包照搬。

来源：

- `backend/services/temporal_filter_validation_service.py`

适合原因：

- 里面的 `build_score_panel`、`TopN + threshold + rebalance` 回测逻辑，属于策略验证壳
- 这部分和 `strategy_kits` 的“时序打分后选股”范式一致

不适合整包迁的原因：

- 当前实现强依赖 `TemporalPoolService`、`data_service`、`temporal_scoring_service`
- 目录、缓存、结果路径都写死在 `FactorHub` 的运行时结构里

迁入建议：

- 只抽“验证 contract”
- 把“历史评分面板输入”改成外部注入
- 把“价格数据获取”改成通过 `execution/data_gateways/` 提供

### 6. 组合暴露和风险诊断

适合部分迁入。

来源：

- `backend/services/portfolio_analysis_service.py`

适合原因：

- 行业暴露、集中度、风险指标这些都是策略验证报告层需要的
- 很适合进入 `validation/attribution/` 或 `validation/diagnostics/`

迁入建议：

- 保留行业暴露、集中度、风险指标
- `factor_exposure` 部分只保留接口，不要绑定 `FactorHub` 的因子语义

## 可以迁，但要谨慎抽象的部分

### 7. Strategy Search Engine

可以迁，但必须先“去因子平台味”。

来源：

- `backend/services/strategy_search_service.py`

它现在做的其实很有价值：

- 模板枚举
- 受约束随机搜索
- 逐步精简

但它当前的问题也很明显：

- 搜索对象默认就是 `factor_groups`
- 候选结构默认就是 signal 因子和 risk_filter 因子
- 它还是偏向“因子组合搜索”

如果迁入 `strategy_kits`，建议这样处理：

- 保留三层搜索框架
- 把 `factor_groups` 抽象成 `signal_groups` 或 `feature_groups`
- 把评分器做成可插拔接口
- 让它服务于“策略模板搜索”，而不是“因子库搜索”

也就是说，迁的是“搜索骨架”，不是“因子搜索平台”。

### 8. StatisticsService

只适合迁一小部分。

来源：

- `backend/services/statistics_service.py`

建议只保留：

- 策略对比里的统计显著性检验辅助
- 一些通用的时序统计函数

不建议保留：

- IC 显著性
- 单调性检验
- 因子衰减
- 因子稳定性

因为这些仍然属于典型的因子研究语言，不是 `strategy_kits` 的核心母语。

## 不建议迁入的部分

### 1. 因子管理平台整层

不建议迁：

- `factor_service.py`
- `factor_version_service.py`
- `factor_import_service.py`
- `factor_library_audit_service.py`
- `factor_monitoring_service.py`

原因：

- 这些是典型的因子资产管理能力
- 它们解决的是“因子怎么被创建、版本化、审计、监控”
- 不是“策略如何装配、验证、准入”

### 2. 因子分析与研究整层

不建议迁：

- `analysis_service.py`
- `factor_validation_service.py`
- `factor_effectiveness_service.py`
- `factor_exposure_service.py`
- `factor_stability_service.py`
- `factor_attribution_service.py`

原因：

- 这些是因子研究体系
- 会把 `strategy_kits` 的边界从“策略工具包”拉回“因子研究中心”

### 3. 因子挖掘和自动发现整层

不建议迁：

- `genetic_factor_mining_service.py`
- `factor_generator_service.py`
- `recent_factor_mining_service.py`
- `single_stock_factor_research_service.py`
- `timesfm_factor_service.py`

原因：

- 这是高耦合的因子发现平台能力
- 成本高、语义重、依赖多
- 对 `strategy_kits` 来说会明显跑偏

### 4. 公式编译器和可视化公式树

不建议迁：

- `backend/services/formula_compiler_service.py`

原因：

- 这是“因子表达式创作工具”
- 不是“策略工具包组件”

如果后面真有需要，也更适合做成独立 skill 或独立工具层，不应进入 `strategy_kits` 主体。

### 5. API / DB / Frontend 整层

不建议迁：

- `backend/api/`
- `backend/models/`
- `backend/repositories/`
- `frontend/`
- `start_api.py`
- `start_all.py`

原因：

- `strategy_kits` 不是一个全栈服务
- 它不该背 `FactorHub` 的 API、数据库、前端负担

### 6. FactorHub 自带简单策略类

不建议直接迁：

- `backend/strategies/base_strategy.py`
- `equal_weight_strategy.py`
- `market_cap_strategy.py`
- `momentum_strategy.py`
- `mean_reversion_strategy.py`

原因：

- `strategy_kits` 里已经有 `strategy_templates/presets/weighting_strategies.py`
- 当前更需要的是“模板装配和验证”，不是再复制一套简化策略类

## 因子相关能力到底适不适合放进来

结论是：

- 因子“作为策略输入”适合
- 因子“作为研究对象和平台中心”不适合

### 适合保留在 strategy_kits 的因子相关能力

- 缺失值填充
- 去极值
- 标准化
- 中性化钩子
- 多因子打分合成
- profile 里的 signal / risk_filter 结构
- 用于筛股或择时的因子组配置

这些都属于“信号层”。

### 不适合保留在 strategy_kits 的因子相关能力

- 因子公式创建与验证平台
- 因子版本管理
- 因子库审计
- 因子挖掘与自动发现
- 因子研究报告中心
- 因子监控面板
- 面向因子研究员的完整分析工作流

这些都属于“因子平台层”。

## 推荐迁移顺序

### P0

先迁这些，收益最大、边界最稳：

1. `factor_profile_registry_service.py` 的契约和配置加载逻辑
2. `strategy_evaluation_service.py`
3. `champion_strategy_service.py`
4. `champion_registry_service.py`
5. `strategy_comparison_service.py`

### P1

再迁这些半抽象组件：

1. `temporal_filter_validation_service.py` 的 TopN 时序验证壳
2. `portfolio_analysis_service.py` 的暴露/集中度/风险指标

### P2

最后再考虑是否需要：

1. `strategy_search_service.py` 的搜索骨架
2. `statistics_service.py` 的少量通用检验函数

## 一个实用判断标准

如果某个模块回答的是下面这些问题，它大概率适合进 `strategy_kits`：

- 这套策略怎么定义模板
- 这套策略怎么做 walk-forward
- 这套策略怎么做准入定档
- 这套策略怎么做版本对照
- 这套策略怎么做结果落盘和报告

如果某个模块回答的是下面这些问题，它大概率不适合进 `strategy_kits`：

- 这个因子怎么被创建
- 这个因子语法是否正确
- 这个因子在历史上是否显著
- 这个因子能否通过遗传算法挖掘
- 这个因子该如何版本管理和监控

## 最终建议

按“策略视角”来定的话，我的建议是：

- `FactorHub` 里和策略模板、验证、准入、台账相关的部分，适合逐步迁入
- `FactorHub` 里和因子平台、公式平台、挖掘平台相关的部分，不建议迁入
- 因子相关能力可以保留一层“预处理 + 打分 + profile 契约”，但不要把 `strategy_kits` 做成第二个 `FactorHub`

一句话收口：

`strategy_kits` 应该吸收 `FactorHub` 的“策略外壳”，不要吸收它的“因子内核”。
