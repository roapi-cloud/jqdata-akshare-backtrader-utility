# 任务 01：验证 contract 与目录骨架

你正在为 `/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/validation/` 定义第一版骨架，不是在泛泛讨论“验证很重要”。

## 硬约束

1. 主结果必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_validation_tasks_20260403/result_01_validation_contract_and_structure.md`
2. 简版回执必须写入：`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_validation_tasks_20260403/dispatch_prompts_20260403/results/01_任务_01_验证contract与目录骨架_回执.md`
3. 必须覆盖以下目录职责：
   - `contracts/`
   - `profiles/`
   - `baseline_matrix/`
   - `ablation/`
   - `walkforward/`
   - `stress/`
   - `regime_slices/`
   - `attribution/`
   - `diagnostics/`
   - `admission/`
   - `reporting/`
   - `artifacts/`
4. 不要写实现代码；本任务只做目录、contract、命名与最小文件清单设计。
5. 不能把 `36_data_benchmark_cost_spec.md` 里已经确定的统一口径重新发明一遍，只能承接和映射。

## 必看材料

- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/33_master_validation_pipeline.md`
- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/35_enhancement_replay_checklist.md`
- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/38_strategy_admission_oos.md`
- `/Users/fengzhi/Downloads/git/testlixingren/docs/universal_mechanisms/39_strategy_factory_execution_checklist.md`

## 任务目标

把 `strategy_kits/validation/` 定义成一个真正能接住后续实现的目录体系，回答清楚：

1. 每个子目录负责什么，不负责什么。
2. 每个子目录下第一批最小文件应该有哪些。
3. 各目录之间传什么中间产物。
4. 哪些是输入 contract，哪些是输出 contract。
5. 哪些字段必须全局统一命名。

## 必须产出

1. 一张完整目录职责表。
2. 一张文件 contract 表，至少包含以下对象：
   - `strategy_card.yaml`
   - `validation_profile.yaml`
   - `validation_manifest.yaml`
   - `baseline_matrix.csv`
   - `ablation_matrix.csv`
   - `walkforward_results.csv`
   - `stress_results.csv`
   - `regime_slice_results.csv`
   - `attribution_summary.json`
   - `admission_decision.json`
   - `validation_report.md`
3. 一份命名规范，至少覆盖：策略 ID、版本 ID、实验 ID、窗口 ID、成本档位、OOS 标签。
4. 一份“最小可实现骨架”建议，说明第一版先做哪些文件，哪些先不做。

## 结果文档至少包含

- 目录树建议
- 各目录职责边界
- 全局文件 contract
- 命名规范
- 必须统一的字段列表
- 推荐先后顺序
- 风险与未决问题

## 回执必须写明

- 你推荐保留的目录
- 你建议第一版立即实现的 5 个文件
- 最关键的 10 个统一字段
- 你认为最容易重复建设的地方
- 是否可直接进入实现

## 通过门槛

- 看完结果后，其他任务可以直接引用你的 contract
- 目录职责没有明显重叠
- 第一版实现顺序清楚
- 不依赖额外口头解释