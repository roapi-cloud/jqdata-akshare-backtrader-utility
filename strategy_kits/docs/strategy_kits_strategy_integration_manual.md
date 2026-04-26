# Strategy Kits 策略接入手册（详细版）

本文档用于把“现有策略脚本”接入到 `skills/strategy_kits`，并形成可持续增强的研究流程。

Skill 入口：

`/Users/fengzhi/Downloads/git/testlixingren/skills/strategy_kits/SKILL.md`

建议优先从 `SKILL.md` 执行标准流程，本手册作为详细参考。

目标：

1. 快速跑通：输入策略候选 -> 回测 -> 产物落盘。
2. 标准化接入：统一 contract、统一命令、统一报告。
3. 便于增强：后续可逐步替换过滤、状态控制、配仓模块，而不是重写整套策略。

---

## 1. 你先看什么（阅读顺序）

建议按以下顺序阅读：

1. 架构总览  
`skills/strategy_kits/docs/strategy_kits_architecture_design.md`

2. 产品化落地现状  
`skills/strategy_kits/docs/strategy_kits_productization_guide.md`

3. skill 输入 schema  
`skills/strategy_kits/docs/strategy_kits_skill_input_schema.md`

4. 任务入口与执行代码  
`skills/strategy_kits/orchestration/task_schema.py`  
`skills/strategy_kits/orchestration/task_runner.py`  
`skills/strategy_kits/orchestration/cli.py`

5. 产物 contract 与落盘  
`skills/strategy_kits/orchestration/artifact_contracts.py`  
`skills/strategy_kits/orchestration/artifacts.py`

---

## 2. 接入前准备（环境与自检）

在仓库根目录执行：

```bash
cd /Users/fengzhi/Downloads/git/testlixingren
uv run pytest skills/strategy_kits/tests -q
PYTHONPATH=skills python -m strategy_kits.orchestration.cli --help
```

通过标准：

1. 测试全绿（当前应为 `31 passed` 左右，随代码演进会变化）。
2. CLI 能输出帮助信息。

---

## 3. 接入 contract（必须满足）

`strategy_kits` 当前支持三类输入：

1. `pool_panel`：`date, code, score, rank`
2. `score_panel`：`date, code, score`（或 `ts_score`）
3. `local_features`：本地预测结果（需至少 `date, code`，建议含 `weight`）

最常用的是 `pool_panel`，CSV 示例：

```csv
date,code,score,rank
2024-01-05,000001,0.82,1
2024-01-05,600519,0.79,2
2024-02-05,000001,0.75,1
```

说明：

1. `date` 会被标准化为日期。
2. `code` 会被标准化（常见格式可自动兼容）。
3. 任何关键字段缺失会触发 `SK_CONTRACT_001`。

---

## 4. 一条最小接入链路（先跑通）

### 4.1 准备 task spec（JSON）

创建 `output/rfscore7_pb10_task_spec.json`：

```json
{
  "task": {
    "task_id": "rfscore7_pb10_v1",
    "strategy_name": "rfscore7_pb10",
    "mode": "single_strategy_research"
  },
  "data": {
    "panel_type": "pool_panel",
    "panel_path": "/Users/fengzhi/Downloads/git/testlixingren/output/rfscore7_pb10_pool_panel.csv",
    "start_date": "2018-01-01",
    "end_date": "2025-12-31"
  },
  "pipeline": {
    "top_n": 20,
    "weight_mode": "equal"
  },
  "backtest": {
    "template": "WeightedTopNStrategy",
    "initial_cash": 1000000,
    "rebalance_threshold": 0.01,
    "hold_days": 1
  },
  "output": {
    "save_artifacts": true,
    "artifact_dir": "/Users/fengzhi/Downloads/git/testlixingren/output/strategy_kits_runs"
  }
}
```

### 4.2 运行

```bash
cd /Users/fengzhi/Downloads/git/testlixingren
PYTHONPATH=skills python -m strategy_kits.orchestration.cli \
  --spec /Users/fengzhi/Downloads/git/testlixingren/output/rfscore7_pb10_task_spec.json \
  --print-result-json
```

CLI 输出里会包含：

1. `portfolio_value`
2. `artifact_dir`
3. `run_report_md`

---

## 5. 产物怎么看（重点）

落盘目录为：

`output/strategy_kits_runs/<task_id>/<run_id>/`

核心文件：

1. `task_spec.json`：本次任务参数快照
2. `prediction_frame.csv`：策略模板实际消费的输入
3. `nav_series.csv`：净值序列
4. `metrics.csv`：指标表
5. `trades.csv`：交易记录
6. `summary.json`：摘要（冻结 contract）
7. `run_report.json`：机器可读报告
8. `run_report.md`：人类可读报告（推荐先看）

建议阅读顺序：

1. `run_report.md`（先看整体）
2. `metrics.csv`（看收益/回撤/风险）
3. `trades.csv`（看换手和交易行为）

---

## 6. 你的策略如何映射（以 RFScore7 PB10 为例）

策略文件：  
`strategies/rfscore7_pb10_release_v1.py`

可按以下映射迁移：

1. 股票池构建（`get_universe`, `filter_buyable`）  
-> `universe/stock_pool_filters/apply_filters`

2. 市场状态控制（`calc_market_state`, `get_target_hold_num`）  
-> `signals/regime_filters/run_regime_gate`（逐步替换，不必一次完成）

3. 候选打分与排序（`calc_rfscore_table`, `sort_candidates`, `choose_stocks`）  
-> 先输出 `pool_panel`，后续再拆到 `signals/*` 模块

4. 调仓执行（`rebalance` 中等额 `order_target`）  
-> 研究侧先走模板策略 + `PortfolioBuilder` + `rebalance_diff`

迁移原则：

1. 先“接入研究链路”，不动你现有线上脚本。
2. 再“模块替换”，每次只替换一层并做回归。

---

## 7. 后续增强建议（推荐顺序）

### 阶段 A：低风险增强（建议先做）

1. 固化 `pool_panel` 生成脚本（每月/每日可重跑）。
2. 用固定 `task_spec` 回测，形成统一产物。
3. 把 `run_report.md` 纳入策略迭代评审。

### 阶段 B：中风险增强

1. 替换股票池过滤为 `apply_filters`。
2. 把持仓数动态逻辑改为 `regime_gate` 驱动。
3. 引入 `PortfolioBuilder` 控制权重/行业集中度。

### 阶段 C：高价值增强

1. 接入 `FactorHub` 的 `score_panel/pool_panel`。
2. 做“截面基座 + 时序增强”的分数合成。
3. 让 `skill.md` 自动生成任务 spec 并执行。

---

## 7.1 平台验证与循环增强（`skills/backtest_guide`）

上面是本地研究闭环；如果你要“真实可交易验证 + 反复增强”，必须再加平台回测闭环。

平台指南入口：

1. `skills/backtest_guide/SKILL.md`
2. `skills/backtest_guide/joinquant.md`
3. `skills/backtest_guide/ricequant.md`

针对 `rfscore7_pb10_release_v1.py`（使用 `jqfactor`），建议平台优先级：

1. 主验证：JoinQuant（语义最一致）
2. 对照验证：RiceQuant（看跨平台稳健性）

### A. 平台提交（JoinQuant 示例）

```bash
cd /Users/fengzhi/Downloads/git/testlixingren/skills/joinquant_strategy
node run-skill.js \
  --id <algorithmId> \
  --file /Users/fengzhi/Downloads/git/testlixingren/strategies/rfscore7_pb10_release_v1.py \
  --start 2018-01-01 \
  --end 2025-12-31 \
  --capital 1000000 \
  --freq day
```

如 session 失效：

```bash
node browser/capture-session.js --headed
```

### B. 拉取结果并落盘

```bash
cd /Users/fengzhi/Downloads/git/testlixingren/skills/joinquant_strategy
node fetch-backtest-results.js --algorithm-id <algorithmId> --latest --save
```

建议把平台结果统一归档到：

`/Users/fengzhi/Downloads/git/testlixingren/output/platform_validation/<strategy_name>/<date>/`

### C. 与 strategy_kits 本地结果对比（每轮都做）

最少对比以下指标：

1. 年化收益
2. 最大回撤
3. 夏普
4. 换手（或交易次数）
5. 空仓比例 / 持仓股票数分布

若平台与本地偏差显著，优先排查：

1. 交易日与调仓触发时点差异
2. 涨跌停/停牌过滤口径差异
3. 手续费与滑点参数不一致
4. 下单粒度差异（按股数/按权重）

### D. 循环增强节奏（建议）

每轮循环固定 5 步：

1. 在 `strategy_kits` 生成新版本 `pool_panel/task_spec` 并本地回测
2. 平台提交同版本策略进行验证
3. 回收平台结果并和本地结果做差异归因
4. 只修改一个增强点（例如过滤器阈值或持仓数规则）
5. 记录版本结论并进入下一轮

推荐版本命名：

`rfscore7_pb10_v1.0`, `rfscore7_pb10_v1.1`, `rfscore7_pb10_v1.2` ...

每个版本至少保留：

1. `task_spec.json`
2. `run_report.md`（本地）
3. 平台回测结果 JSON
4. 一段“本轮修改点 + 指标变化 + 是否保留”的结论

可直接使用的台账模板：

1. `skills/strategy_kits/docs/strategy_kits_iteration_registry_template.md`
2. `skills/strategy_kits/docs/strategy_kits_iteration_registry_template.csv`

---

## 8. 常见报错与排查

1. `SK_CONTRACT_001`  
字段缺失。先检查输入 CSV 列名是否匹配 contract。

2. `SK_CONTRACT_002`  
字段值非法。重点检查 `date`、`score`、`rank`、`top_n`、`rebalance_threshold`。

3. `SK_ARTIFACT_001`  
产物目录写入失败。检查 `output.artifact_dir` 权限与路径。

4. `SK_ARTIFACT_002`  
产物 contract 不合法。通常是落盘流程被改坏，先跑单测定位。

---

## 9. 回归测试建议（每次改动后执行）

```bash
cd /Users/fengzhi/Downloads/git/testlixingren
uv run pytest skills/strategy_kits/tests -q
```

若改了策略接入链路，建议至少补两类测试：

1. unit：schema/adapter/contract
2. smoke：输入池 -> 打分 -> 配仓 -> 回测

---

## 10. 最小实践清单（可直接打勾）

1. 已生成 `pool_panel.csv`，字段满足 contract
2. 已创建 `task_spec.json`
3. CLI 可运行并输出 `artifact_dir`
4. 已查看 `run_report.md`
5. 已把本次参数和结果归档
6. 已跑测试确认无回归

完成以上 6 项，说明策略已成功接入 `strategy_kits`，可以进入增强阶段。
