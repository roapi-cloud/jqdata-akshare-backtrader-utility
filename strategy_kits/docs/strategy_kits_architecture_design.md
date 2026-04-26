# Strategy Kits 核心架构设计（单策略研究版）

本文档是 `strategy_kits` 的收敛版架构说明，只聚焦一个目标：

**让一个研究中的单策略，从“想法”到“可回测策略”，更快落地。**

---

## 1. 目标与边界

### 1.1 当前目标（做什么）

`strategy_kits` 当前只做五件事：

1. 策略输入准备：股票池、交易日历、数据适配。
2. 信号与打分：指标工厂、因子预处理、状态过滤。
3. 组合构建：把分数/信号转成目标权重（含轻量约束）。
4. 回测接入与模板：快速起一个单策略并跑通回测。
5. 时序增强接入：把外部时序评分结果接进单策略研发流程。

### 1.2 当前不做（明确不做）

1. 不做实盘上线后的监控与运维。
2. 不重做回测平台已有的完整绩效报告体系。
3. 不把 `strategy_kits` 做成第二个完整 `SBS`。
4. 不把 `strategy_kits` 做成完整因子平台。
5. 不承接因子资产管理、版本治理、公式编译、挖掘与监测。

---

## 2. 三方职责分工

### 2.1 `SBS` 负责

1. 底层数据基础设施与数据服务。
2. 通用回测执行基础能力。
3. 与回测运行强绑定的执行适配。
4. 实盘执行链路（若需要）。

### 2.2 `FactorHub` 负责

1. 因子资产中心：定义、版本、profile、治理。
2. 因子研究与评分中心：时序评分、池内打分、因子分析。
3. 因子产物导出：`score_panel`、`pool_panel`、`profile_meta`。
4. 未来若扩展截面因子，也应作为与时序并列的研究引擎放在 `FactorHub`，而不是放进 `strategy_kits`。

### 2.3 `strategy_kits` 负责

1. 策略研发层的可复用组件。
2. 单策略模板与策略快速拼装。
3. 策略输入到组合输出的“中间层逻辑”。
4. 把 `SBS` 的基础设施能力和 `FactorHub` 的因子产物接到同一条单策略研发链路上。

一句话总结：

**`SBS` 是基础设施，`FactorHub` 是因子资产与评分中心，`strategy_kits` 是单策略研发装配层。**

---

## 3. 单策略研究的默认范式

### 3.1 三种常见形态

当前阶段优先支持以下三种单策略形态：

1. 纯截面单策略：先做截面选股，再做组合构建。
2. 纯时序单策略：直接使用时序池评分结果驱动 TopN 或权重分配。
3. 截面基座 + 时序增强：先有基础选股，再用时序信号做过滤、排序增强或仓位缩放。

### 3.2 推荐默认范式

默认推荐采用：

**截面基座 + 时序增强**

这是因为：

1. 截面更擅长回答“今天全市场谁更值得选”。
2. 时序更擅长回答“这只股票现在该不该持有、增强、减仓或退出”。
3. 两者混成一套统一评分平台容易边界失控，分层后更容易演进。

### 3.3 时序增强的三种接法

1. 进场过滤：截面已入选，但时序状态差，则不进。
2. 排名增强：`final_score = cs_score + lambda * ts_score`。
3. 仓位缩放：基础仓位不变，按时序状态做加仓、减仓或提前退出。

### 3.4 “双袖口”位置

“红利袖口 + 进攻袖口 + allocator”仍然是可支持模式，但它属于单策略内的扩展结构，不再作为当前文档的默认主叙事。

---

## 4. 核心能力目录（收敛后）

以下目录是当前核心能力，其他目录暂不作为主线。

### 4.1 输入与信号层

1. `universe/stock_pool_filters/`
2. `universe/trade_calendar/`
3. `execution/data_gateways/`
4. `signals/indicator_factory/`
5. `signals/regime_filters/`
6. `signals/factor_preprocess/`

### 4.2 组合与约束层

1. `portfolio/position_state/portfolio_builder.py`
2. `portfolio/runtime_state/rebalance_diff.py`
3. `risk/constraints.py`

### 4.3 单策略模板层

1. `strategy_templates/presets/prediction_file_template.py`
2. `strategy_templates/presets/weighting_strategies.py`

### 4.4 回测接入层

1. `execution/backtrader_runtime/`

### 4.5 建议新增的薄桥接层（待创建）

当前不新建顶层 `factor/`，但建议后续增加一个很薄的 `FactorHub` 桥接层：

1. `integrations/factorhub/contracts.py`
2. `integrations/factorhub/loader.py`
3. `integrations/factorhub/adapter.py`

该层只负责把 `FactorHub` 产出的评分面板转成 `strategy_kits` 可消费的输入，不负责因子管理本身。

---

## 5. 单策略研发主流程

### 5.1 本地研究链路（依赖 `SBS` / 本地特征）

推荐标准流程：

1. 定义基础池：`universe` + `trade_calendar`
2. 计算信号/本地特征：`signals/*`
3. 组合构建：`portfolio_builder` + `risk/constraints`
4. 生成目标权重并计算调仓差分：`rebalance_diff`
5. 通过模板策略接入 `backtrader_runtime` 运行回测

伪代码：

```python
universe = build_universe(...)
features = build_features(universe, ...)
score_df = run_scoring(features, ...)

target_weights = PortfolioBuilder(...).build(score_df, ...)
orders = compute_rebalance_diff(target=target_weights, current=current_pos)

result = run_backtest(config, WeightedTopNStrategy, pred_df=target_weights_plan)
```

### 5.2 `FactorHub` 驱动链路（依赖外部评分产物）

当研究以时序因子为主时，推荐直接消费 `FactorHub` 产物：

1. 在 `FactorHub` 中定义 profile 并生成评分结果。
2. 导出 `score_panel` 或 `pool_panel`。
3. 在 `strategy_kits` 中将其转成 `pred_df` 或目标权重。
4. 通过模板策略接入 `backtrader_runtime` 回测。

伪代码：

```python
pool_panel = load_factorhub_pool_panel(profile_id="temporal_pool_x", ...)
pred_df = adapt_pool_panel_to_predictions(pool_panel, top_n=20)

result = run_backtest(
    config,
    WeightedTopNStrategy,
    pred_df=pred_df,
)
```

### 5.3 “截面基座 + 时序增强”链路

这是当前最推荐的融合方式：

1. 截面模型先产生基础候选与基础分数。
2. `FactorHub` 提供个股时序评分。
3. 在 `strategy_kits` 中合成最终分数或最终仓位。
4. 再进入组合构建与回测。

伪代码：

```python
cs_score = build_cross_sectional_score(...)
ts_score = load_factorhub_temporal_score(...)

merged = merge_scores(cs_score, ts_score)
merged["final_score"] = merged["cs_score"] + 0.3 * merged["ts_score"]

target_weights = PortfolioBuilder(...).build(merged, score_col="final_score")
```

---

## 6. 因子维度策略

当前结论：

1. **先不新建顶层 `factor/` 目录。**
2. 因子在 `strategy_kits` 中按“策略输入”处理，而不是“平台资产”处理。
3. 因子资产管理、版本治理、公式编译、研究引擎应优先放在 `FactorHub`。
4. `strategy_kits` 只消费因子产物，不接管因子平台职责。

当前在 `strategy_kits` 的因子相关范围：

1. `signals/factor_preprocess/`：清洗、标准化、打分。
2. `signals/indicator_factory/`：研究期信号计算。
3. `signals/regime_filters/`：市场级总闸门与状态过滤。

建议未来 `strategy_kits` 只承认三类来自 `FactorHub` 的标准输入：

1. `score_panel`：单股时序评分面板。
2. `pool_panel`：池内排序面板，典型字段为 `date/code/score/rank`。
3. `profile_meta`：profile 描述、来源、版本等元信息。

---

## 7. 当前已落地能力（2026-04-03）

以下能力已按“第 1-2 周 + 第 3-4 周”目标完成并可直接使用：

1. 股票池过滤闭环：`st/paused/new_stock/limitup/limitdown` 已由 TODO 骨架升级为可运行实现（含阶段日志）。
2. 交易日历闭环：支持 `init_trade_cal_from_gateway`、`init_trade_cal_from_csv`、`is_trade_cal_initialized`，并有统一错误码。
3. 预处理一致性：`FactorPreprocessPipeline.fit()` 统计量已在 `transform()` 中稳定复用；输入 `date/code` 已做统一规范化。
4. 组合与调仓 contract 化：`weighting_strategies.py` 与 `rebalance_diff.py` 已接入 DataFrame 合同校验。
5. 工程化底座：已提供统一错误码、统一日志事件格式、DataFrame 合同模块。
6. 测试体系：已补齐 unit + smoke（覆盖“输入池 -> 打分 -> 配仓 -> 回测”端到端样例）。
7. FactorHub 薄桥接层：`integrations/factorhub/` 已支持 `pool_panel/score_panel` 读取、校验、适配。
8. 统一任务入口：`orchestration/task_schema.py` + `orchestration/task_runner.py` 已可用于 `skill.md` 自动编排调用。
9. CI gate：已新增 `.github/workflows/strategy_kits_ci.yml`，默认执行 `strategy_kits` 测试。
10. 任务产物标准化：`orchestration/artifacts.py` + `orchestration/cli.py` 已支持统一落盘与命令行触发。
11. 产物 contract 冻结：`orchestration/artifact_contracts.py` 已定义 `artifact_schema_version=v1.0` 的 summary/manifest/report 规范。

---

## 8. 近期优先级（产品级下一阶段）

### P0（继续强化）

1. 强化 `integrations/factorhub/`（补 profile/meta 一致性校验与远端加载适配）。
2. 固化 contract 文档版本号（例如 `v1.0`），避免后续增强时字段漂移。
3. 统一 task artifacts 产物规范（结果文件命名、落盘结构、元数据）。
4. 将 CI gate 与主仓分支策略联动（要求 PR 必过后才可合并）。

### P1（能力扩展）

1. 增加“截面基座 + 时序增强”模板策略（过滤/排序增强/仓位缩放三种模式）。
2. 增加策略任务输入 schema（为后续 `skill.md` 自动编排做准备）。
3. 增加更多错误码分层（输入错误、运行时错误、外部依赖错误）。

### P2（暂缓）

1. 平台化验证框架（walk-forward、admission profile、归因报告）。
2. 实盘监控与运维能力。
3. 因子资产治理平台化（继续由 `FactorHub` 主导，不在 `strategy_kits` 内展开）。

---

## 9. 验收标准（当前版本）

满足以下五条即视为架构收敛有效：

1. 一个新策略可在 1 天内完成从模板到可回测版本。
2. 输入、信号、组合、回测四层边界清晰且可替换。
3. `SBS`、`FactorHub`、`strategy_kits` 三方职责不冲突。
4. 能支持“纯截面”“纯时序”“截面基座 + 时序增强”三类单策略研究。
5. 时序因子可以用于个股增强，而无需把 `strategy_kits` 先做成因子平台。
