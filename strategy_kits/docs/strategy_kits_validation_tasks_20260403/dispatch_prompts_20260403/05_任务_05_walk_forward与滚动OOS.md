# 任务 05：Walk-forward 与滚动 OOS

你正在定义样本内 / 样本外和滚动验证框架，不是在重新做一次 train/test 随机切分。

## 硬约束

1. 主结果必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_validation_tasks_20260403/result_05_walkforward_and_rolling_oos.md`
2. 简版回执必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_validation_tasks_20260403/dispatch_prompts_20260403/results/05_任务_05_walk_forward与滚动OOS_回执.md`
3. 必须覆盖：
   - 固定样本内 / 样本外
   - expanding walk-forward
   - rolling walk-forward
   - 最近窗口 OOS 监控
4. 必须给出最小窗口长度、步长、最少窗口数建议。
5. 不允许只给一个 split_date 了事。

## 必看材料

- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/33_master_validation_pipeline.md`
- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/35_enhancement_replay_checklist.md`
- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/38_strategy_admission_oos.md`
- `/Users/fengzhi/Downloads/git/testlixingren/stock-backtesting-system/src/factor_workflow/dataset_config.py`

## 任务目标

把 `walkforward/` 设计成真正可复用的滚动验证组件，回答清楚：窗口怎么切、什么时候算失效、结果如何汇总进统一报告。

## 必须回答

1. 主仓策略与事件策略的窗口设计是否不同。
2. expanding 与 rolling 何时各自适用。
3. 最近 1/3/6/12 个月 OOS 应如何接入。
4. walk-forward 结果该输出哪些核心字段。
5. 何时应该判定“样本外坍塌”。

## 必须产出

1. `walkforward_results.csv` 字段设计。
2. `validation_manifest.yaml` 中与窗口相关的配置建议。
3. 默认窗口模板，至少覆盖主仓和事件两类。
4. OOS 预警规则建议。
5. 结果汇总与可视化建议。

## 结果文档至少包含

- 窗口切分方案
- 参数建议
- 不同策略类型的适配建议
- OOS 预警与降级规则
- 推荐第一版实现路径
- 与任务 09 的接口关系

## 回执必须写明

- 你推荐的默认窗口模板
- 你定义的 OOS 坍塌标准
- `walkforward_results.csv` 最关键字段
- 是否可直接进入实现

## 通过门槛

- 不再依赖一次性 split
- 能支撑 A/B/D 档判断
- 能直接被统一报告消费