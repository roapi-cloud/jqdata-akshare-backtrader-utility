# Strategy Kits Skill 输入 Schema（v1）

本文档定义 `strategy_kits` 在被 `skill.md` 调用时的统一输入参数。

目标：

1. 大模型收到任务后可直接落到可执行参数。
2. 不同策略模板共享同一套字段语义。
3. 输入异常可快速定位（字段缺失/类型非法/取值越界）。

---

## 1. 顶层结构

```yaml
task:
  task_id: "demo_20260403_001"
  strategy_name: "single_factor_topn"
  mode: "single_strategy_research"

data:
  panel_type: "pool_panel"          # pool_panel | score_panel | local_features
  panel_path: "/abs/path/pool.csv"
  start_date: "2020-01-01"
  end_date: "2024-12-31"
  code_format: "jq"                 # jq | ak | ts | qlib | auto

pipeline:
  filters_enabled: true
  preprocess_enabled: true
  score_method: "equal"             # equal | custom | ic | icir | pca
  top_n: 20

portfolio:
  cash_target: 0.05
  max_positions: 20
  max_single: 0.1

backtest:
  template: "WeightedTopNStrategy"  # WeightedTopNStrategy | EqualWeightStrategy | DirectExecutionStrategy
  hold_days: 5
  rebalance_threshold: 0.005
  initial_cash: 1000000

risk:
  enable_constraints: true
  max_industry: 0.3
  max_turnover: 0.4

output:
  save_artifacts: true
  artifact_dir: "/abs/path/output"
```

---

## 2. 必填字段

1. `task.task_id`
2. `task.strategy_name`
3. `data.panel_type`
4. `data.start_date`
5. `data.end_date`
6. `backtest.template`
7. `backtest.initial_cash`

补充规则：

1. `data.panel_type` 为 `pool_panel` 或 `score_panel` 时，`data.panel_path` 必填。
2. `pipeline.top_n`、`portfolio.max_positions` 必须为正整数。
3. `portfolio.max_single` 必须在 `(0, 1]`。
4. `backtest.rebalance_threshold` 必须在 `[0, 1)`。

---

## 3. 与现有 contract 的映射

1. `pool_panel` 输入映射到 `validate_pool_panel` / `validate_factorhub_pool_panel`。
2. `score_panel` 输入映射到 `validate_factorhub_score_panel`。
3. 模板策略输入 `pred_df` 映射到 `validate_prediction_frame`。
4. 调仓差分输入映射到：
   - `validate_target_weights_frame`
   - `validate_current_weights_frame`

---

## 4. 建议的 skill.md 执行步骤

1. 校验输入 schema（先做字段和范围）。
2. 根据 `panel_type` 走适配：
   - `pool_panel -> pool_panel_to_prediction_frame`
   - `score_panel -> score_panel_to_prediction_frame`
3. 运行模板策略回测（`run_backtest`）。
4. 产出最小报告：
   - 关键指标 `metrics`
   - 交易记录 `trades`
   - 净值序列 `nav_series`

---

## 5. 常见错误码建议

1. `SK_CONTRACT_001`: 缺关键字段。
2. `SK_CONTRACT_002`: 字段值非法（类型或范围问题）。
3. `SK_CAL_001`: 交易日历未初始化。
4. `SK_FILTER_001`: 过滤器依赖数据缺失。
5. `SK_PRE_001`: 预处理状态非法（如 transform 前未 fit）。

---

## 6. CLI 执行方式

```bash
python -m strategy_kits.orchestration.cli \
  --spec /abs/path/task_spec.json \
  --print-result-json
```

默认会在 `output.artifact_dir/task_id/run_id/` 下落盘：

1. `task_spec.json`
2. `prediction_frame.csv`
3. `nav_series.csv`
4. `metrics.csv`
5. `trades.csv`
6. `analyzers.json`
7. `summary.json`
8. `run_report.json`
9. `run_report.md`
