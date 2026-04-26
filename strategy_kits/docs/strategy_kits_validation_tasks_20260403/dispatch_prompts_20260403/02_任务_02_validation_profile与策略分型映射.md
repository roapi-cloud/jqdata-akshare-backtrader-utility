# 任务 02：validation profile 与策略分型映射

你正在定义不同策略类型该跑哪些验证，不是在重新讨论所有策略谁更好。

## 硬约束

1. 主结果必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_validation_tasks_20260403/result_02_validation_profiles_and_strategy_mapping.md`
2. 简版回执必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_validation_tasks_20260403/dispatch_prompts_20260403/results/02_任务_02_validation_profile与策略分型映射_回执.md`
3. 必须至少覆盖以下策略类型：
   - `stock_main`
   - `etf_main`
   - `microcap`
   - `event`
   - `satellite`
4. 必须区分：必跑、建议跑、可跳过。
5. 不要把本任务变成“最终定档”，定档属于任务 09。

## 必看材料

- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/32_master_portfolio_assembly.md`
- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/33_master_validation_pipeline.md`
- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/35_enhancement_replay_checklist.md`
- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/39_strategy_factory_execution_checklist.md`

## 任务目标

定义 `validation_profile.yaml` 应该怎么设计，让一个新策略填完 profile 后，就知道自己必须跑哪些验证模块。

## 必须回答

1. 各策略类型默认适用哪些验证模块。
2. 哪些策略类型必须跑 `V0/V1/V2/V3`，哪些可以降级。
3. 哪些策略类型必须跑 walk-forward，哪些只要求 OOS。
4. 哪些策略类型必须做成本/容量压力测试。
5. 哪些策略类型不能直接复用主仓门槛。

## 必须产出

1. `策略类型 -> validation profile` 对照表。
2. `validation_profile.yaml` 建议字段清单。
3. 每个 profile 的必跑实验矩阵。
4. 每个 profile 的跳过规则和前提条件。
5. 一份默认 profile 集合建议，例如：
   - `main_stock_default`
   - `main_etf_default`
   - `microcap_strict`
   - `event_lightweight`
   - `satellite_overlay`

## 结果文档至少包含

- 策略分型定义
- profile 设计原则
- 字段结构建议
- 各 profile 必跑 / 可选 / 跳过矩阵
- 典型误用场景
- 推荐默认值

## 回执必须写明

- 你建议保留的 profile 列表
- 每个 profile 最关键的必跑项
- 哪类策略最容易误用主仓验证门槛
- 是否可以直接据此写 `validation_profile.yaml`

## 通过门槛

- 新策略只要选 profile，就能知道要跑什么
- 不同策略类型不会被一刀切
- 主仓、事件、卫星的验证负担明显区分开