# 任务 04：抽 Backtrader 运行底座

你正在做可复用回测底座抽取，不是在写某个单策略的回测脚本。

## 硬约束

1. 主结果必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_extraction_tasks_20260403/result_04_extract_backtrader_runtime.md`
2. 简版回执必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_extraction_tasks_20260403/dispatch_prompts_20260403/results/04_任务_04_抽Backtrader运行底座_回执.md`
3. 必须同时参考：
   - 聚宽侧 `backtrader_base_strategy.py`
   - QuantsPlaybook 的 `BackTestTemplate/*`
4. 目标归宿限定为：`/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/execution/backtrader_runtime/`
5. 允许直接补最小骨架文件。

## 任务目标

让一个新策略只要给出信号/目标权重，就能尽快跑起来，而不必重新搭 Cerebro、佣金、datafeed、订单记录、context 兼容层。

## 必须产出

1. 聚宽 compat 层与 QuantsPlaybook runtime 层的职责切分。
2. 最小运行底座文件清单。
3. 最小配置对象定义。
4. 最小策略接入接口。
5. 如边界清晰，直接补骨架文件。

## 最小接口要求

至少定义清楚：

- `run_backtest(config, strategy_cls, data_bundle)`
- `load_datafeeds(...)`
- `build_broker(...)`
- `build_analyzers(...)`
- `strategy_context` / `portfolio_compat`

## 不该抽的内容

- 某个具体择时信号
- 某个具体 ETF 轮动参数
- 某个具体仓位答案

## 通过门槛

- 新策略接入回测底座的路径足够短
- JQ 风格策略与普通 BT 策略都能有清晰归宿