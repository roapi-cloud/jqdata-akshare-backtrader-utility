# Strategy Kits 单策略接入与增强 Skill

## 功能描述

把任意“已有策略脚本”接入 `skills/strategy_kits`，形成标准化研发闭环：

1. 本地研究回测：`panel -> task_spec -> 回测 -> 产物`
2. 平台验证对照：JoinQuant / RiceQuant 提交、拉取结果、差异归因
3. 版本化增强：按单改动点迭代，沉淀可复用策略能力

---

## 适用场景

适合：

1. 已有策略脚本需要标准化接入（如 `rfscore7_pb10_release_v1.py`）
2. 新策略需要统一 contract、统一回测流程、统一报告产物
3. 希望建立“本地研究 + 平台验证 + 循环增强”的工程化流程

不适合：

1. 纯实盘监控运维（不在本 skill 范围）
2. 纯因子平台治理（由 FactorHub 主导）

---

## 核心能力

1. 统一输入 contract：`pool_panel / score_panel / local_features`
2. 统一任务入口：`orchestration/task_schema.py` + `task_runner.py`
3. 统一命令行执行：`python -m strategy_kits.orchestration.cli`
4. 统一产物落盘：`summary.json`, `run_report.json`, `run_report.md`
5. 平台验证接入：配合 `skills/backtest_guide` 做提交和结果拉取
6. 迭代台账模板：记录每轮增强、平台对比和保留决策

---

## 快速开始

### 1) 环境自检

```bash
cd /Users/fengzhi/Downloads/git/testlixingren
uv run pytest skills/strategy_kits/tests -q
PYTHONPATH=skills python -m strategy_kits.orchestration.cli --help
```

### 2) 准备 task spec

最小必填字段：

1. `task.task_id`
2. `task.strategy_name`
3. `data.panel_type`
4. `data.start_date`
5. `data.end_date`
6. `backtest.template`
7. `backtest.initial_cash`

### 3) 执行本地回测

```bash
PYTHONPATH=skills python -m strategy_kits.orchestration.cli \
  --spec /abs/path/task_spec.json \
  --print-result-json
```

### 4) 查看核心产物

产物目录：

`output/strategy_kits_runs/<task_id>/<run_id>/`

重点先看：

1. `run_report.md`
2. `metrics.csv`
3. `trades.csv`

---

## 标准输入

### pool_panel（推荐）

必需列：`date, code, score, rank`

### score_panel

必需列：`date, code, score`（或 `ts_score`）

### local_features

必需列：`date, code`（建议包含 `weight`）

---

## 标准执行流程（新策略）

1. 提取候选结果并导出 `pool_panel.csv`
2. 编写并固化 `task_spec.json`
3. 运行本地 `strategy_kits` 回测
4. 归档 `run_report` 与关键指标
5. 用 `backtest_guide` 提交平台验证
6. 回收平台结果并与本地结果做差异归因
7. 只改一个增强点，进入下一轮

---

## 平台验证（配合 backtest_guide）

对使用 `jqfactor` 的策略，优先 JoinQuant 做主验证。

### JoinQuant 提交

```bash
cd /Users/fengzhi/Downloads/git/testlixingren/skills/joinquant_strategy
node run-skill.js \
  --id <algorithmId> \
  --file /abs/path/your_strategy.py \
  --start 2018-01-01 \
  --end 2025-12-31 \
  --capital 1000000 \
  --freq day
```

### JoinQuant 拉取最近结果

```bash
node fetch-backtest-results.js --algorithm-id <algorithmId> --latest --save
```

---

## 循环增强规范

每轮固定 5 步：

1. 本地回测（strategy_kits）
2. 平台回测（JoinQuant / RiceQuant）
3. 指标差异归因
4. 单点改动（仅一个改动点）
5. 版本结论（`keep` / `rollback`）

版本命名建议：

`strategy_name_v1.0`, `strategy_name_v1.1`, `strategy_name_v1.2`

台账模板：

1. `skills/strategy_kits/docs/strategy_kits_iteration_registry_template.md`
2. `skills/strategy_kits/docs/strategy_kits_iteration_registry_template.csv`

---

## 常见问题

1. `SK_CONTRACT_001`：输入字段缺失，先检查 panel 列名
2. `SK_CONTRACT_002`：字段值非法，先检查 `date/score/rank/top_n`
3. `SK_ARTIFACT_001`：落盘目录不可写，检查 `output.artifact_dir`
4. `SK_ARTIFACT_002`：产物 contract 非法，先跑单测定位

---

## 详细文档

1. [策略接入手册](docs/strategy_kits_strategy_integration_manual.md)
2. [架构设计](docs/strategy_kits_architecture_design.md)
3. [产品化指南](docs/strategy_kits_productization_guide.md)
4. [Skill 输入 Schema](docs/strategy_kits_skill_input_schema.md)
5. [FactorHub 迁移评估](docs/factorhub_migration_assessment_20260403.md)

