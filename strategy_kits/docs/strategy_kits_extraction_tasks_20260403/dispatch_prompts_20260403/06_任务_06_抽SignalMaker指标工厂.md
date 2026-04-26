# 任务 06：抽 SignalMaker 指标工厂

你正在做可拼装信号工厂抽取，不是在挑一个最强信号重写成单策略。

## 硬约束

1. 主结果必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_extraction_tasks_20260403/result_06_extract_indicator_factory.md`
2. 简版回执必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_extraction_tasks_20260403/dispatch_prompts_20260403/results/06_任务_06_抽SignalMaker指标工厂_回执.md`
3. 必须同时参考：
   - QuantsPlaybook `SignalMaker/`
   - 聚宽侧已有可复用信号/打分/择时相关实现
4. 目标归宿限定为：`/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/signals/indicator_factory/`
5. 允许直接补最小骨架文件。

## 任务目标

把最适合复用的单指标/单信号计算器抽出来，让新策略可以像拼积木一样装信号。

## 必须产出

1. 第一版最值得抽的信号列表。
2. 每个信号的输入输出格式。
3. 统一 signal interface。
4. 推荐目录与文件拆分。
5. 如边界清晰，直接补骨架文件。

## 最小接口要求

至少定义清楚：

- 输入：`price_df` / `feature_df` / `config`
- 输出：
  - `signal_series`
  - `signal_df`
  - `meta`

## 不该抽的内容

- 某个策略最终投票规则
- 某个策略的固定阈值答案
- 某个研报专属标签定义

## 通过门槛

- 新策略能快速复用单指标/单信号模块
- 指标工厂和最终策略组合逻辑清晰分离