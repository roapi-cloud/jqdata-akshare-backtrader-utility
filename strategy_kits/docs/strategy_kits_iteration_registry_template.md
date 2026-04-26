# Strategy Iteration Registry Template（策略迭代台账模板）

适用场景：

1. `strategy_kits` 本地回测 + 平台回测（JoinQuant / RiceQuant）联合验证
2. 每轮只改一个增强点，记录“改了什么、带来什么、是否保留”

---

## 1. 使用规则

1. 一轮增强对应一行记录（或一节记录）。
2. 每轮只允许一个核心变更点，避免归因混淆。
3. 必须同时记录本地与平台结果。
4. 结论必须二选一：`keep` / `rollback`。

---

## 2. 字段定义

1. `version`：版本号，如 `rfscore7_pb10_v1.1`
2. `change_scope`：本轮改动范围（filter / regime / portfolio / execution）
3. `change_summary`：一句话说明改了什么
4. `local_period`：本地回测区间
5. `platform_period`：平台回测区间
6. `local_annual_return`：本地年化收益
7. `local_max_drawdown`：本地最大回撤
8. `local_sharpe`：本地夏普
9. `platform_annual_return`：平台年化收益
10. `platform_max_drawdown`：平台最大回撤
11. `platform_sharpe`：平台夏普
12. `diff_comment`：本地/平台差异简述
13. `decision`：`keep` 或 `rollback`
14. `owner`：负责人
15. `date`：记录日期
16. `artifact_links`：关键产物路径（run_report/platform result）

---

## 3. Markdown 台账模板

```markdown
## rfscore7_pb10_v1.1

- date: 2026-04-04
- owner: fengzhi
- change_scope: filter
- change_summary: 新股过滤从 180 天提高到 250 天

### Backtest Window
- local_period: 2018-01-01 ~ 2025-12-31
- platform_period: 2018-01-01 ~ 2025-12-31

### Metrics
- local_annual_return: 0.182
- local_max_drawdown: -0.236
- local_sharpe: 1.08
- platform_annual_return: 0.169
- platform_max_drawdown: -0.251
- platform_sharpe: 0.97

### Diff
- diff_comment: 平台回撤高于本地，怀疑成交/滑点口径差异，收益改善仍成立

### Decision
- decision: keep

### Artifacts
- local_run_report: /abs/path/output/strategy_kits_runs/rfscore7_pb10_v1.1/.../run_report.md
- platform_report: /abs/path/output/platform_validation/rfscore7_pb10_v1.1/.../result.json
```

---

## 4. CSV 台账模板

配套文件：

`skills/strategy_kits/docs/strategy_kits_iteration_registry_template.csv`

建议每轮回测后追加一行，后续可直接做透视和趋势分析。

