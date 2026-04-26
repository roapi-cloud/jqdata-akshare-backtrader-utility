# 主策略增强机制库 (Universal Mechanisms)

> **定位**：这里只放“主策略增强模块”，不再把它当成完整策略灵感库或原始 alpha 来源库。
> **默认前提**：当前 `strategy.py` 已经是一条主仓 alpha 原型；本目录只负责增强，不负责重写主策略。

---

## 一、现在这套目录应该怎么用

配合 `skills/autoresearch_joinquant/program_enhance.md` 使用时，默认流程是：

```text
当前主策略
→ 先做工程审计
→ 再做 alpha 参数增强
→ 再补主路由与总暴露
→ 最后加过滤 / 确认 / 风控
→ 再做统一验证与定档
```

给 agent 的最短入口：

1. 先读 `MANIFEST.md`
2. 再按需读本 `README.md`
3. 最后只打开当前层相关的机制文档

这样做的目的，是避免 agent 一上来就在全目录里随机加机制。

这意味着本目录里的文档，不再按“哪类策略都能直接拿来当主策略”理解，而要按下面 4 层理解：

- `L0 工程与执行正确性`
- `L1 Alpha 参数增强`
- `L2 主路由与总暴露`
- `L3 过滤 / 确认 / 风控增强`

---

## 二、四层分工

### L0 工程与执行正确性

解决：

- 规则有没有真正接通
- 状态变量有没有写入和清理
- 主路由是否真的影响总暴露
- 是否有目标权重、现金缓冲、执行一致性

### L1 Alpha 参数增强

解决：

- 当前 alpha 选什么
- 持仓数多少
- 估值 / 市值 / 质量 / 成长阈值是否适合当前市场

注意：

- 这一层是“细化原 alpha”
- 不是“把原策略替换成一个新 alpha”

### L2 主路由与总暴露

解决：

- 现在给不给做
- 总仓位做到几成
- 是否该保留更多现金
- 是否该降档而不是空仓

### L3 过滤 / 确认 / 风控增强

解决：

- 是否允许升档 / 恢复
- 是否减少噪声交易
- 是否降低单笔大亏
- 是否减少止损后过早回补

---

## 三、默认保留的核心文档

如果你的目标是“增强当前主策略”，这批文档应默认保留。

### A. 必保留：工程骨架

| # | 文件 | 用途 |
|---|---|---|
| 04 | `04_base_filters.md` | 基础股票池过滤，防回测失真 |
| 31 | `31_index_enhancement_base.md` | 主仓执行底座 |
| 32 | `32_master_portfolio_assembly.md` | 主仓装配总图 |
| 33 | `33_master_validation_pipeline.md` | 统一验证框架 |
| 34 | `34_alpha_weight_mapping.md` | 目标权重映射 |
| 35 | `35_enhancement_replay_checklist.md` | 增强回放清单 |
| 36 | `36_data_benchmark_cost_spec.md` | 数据 / 成本 / 基准统一口径 |
| 37 | `37_signal_confirmation_interface.md` | 双确认与再进场 |
| 38 | `38_strategy_admission_oos.md` | 定档与 OOS 标准 |

### B. 必保留：主策略常用增强

| # | 文件 | 默认角色 |
|---|---|---|
| 03 | `03_state_router.md` | 主路由 / 总暴露分档 |
| 10 | `10_volatility_position.md` | 连续型风险缩放 |
| 17 | `17_trailing_stop.md` | 退出与保护 |
| 24 | `24_fscore_selection.md` | Alpha 参数增强参考 |
| 28 | `28_dividend_quality_filter.md` | Alpha 参数增强参考 |
| 30 | `30_signalmaker_filters.md` | 二级过滤 / 确认层 |

---

## 四、条件保留的文档

这批文档可以留在目录中，但不应默认挂到所有主策略上。

| # | 文件 | 默认建议 |
|---|---|---|
| 01 | `01_emotion_switch.md` | 只做底线确认或降档，不默认硬停手 |
| 08 | `08_rsrs_timing.md` | 更适合 ETF / 趋势 / 指数，不是所有价值主策略都需要 |
| 09 | `09_north_money.md` | 只做辅助确认，不单独主导仓位 |
| 11 | `11_consistency_control.md` | 微盘更常用，基本面主策略慎用 |
| 12 | `12_breadth_index.md` | 可做宽度输入，不必单独成层 |
| 15 | `15_crowding_detection.md` | 适合热点 / 微盘 / 拥挤环境修正 |
| 18 | `18_multi_timeframe.md` | 适合趋势确认，不适合默认强过滤 |
| 25 | `25_epo_portfolio.md` | 多资产 / ETF 组合优化 |
| 27 | `27_es_risk_parity.md` | 多资产风险预算 |

---

## 五、不建议默认挂到当前主策略上的文档

如果你当前主要做的是“股票低频主仓 / 红利质量 / 价值混合”增强，这些文档不建议默认加入搜索前排：

| # | 文件 | 原因 |
|---|---|---|
| 02 | `02_pause_mechanism.md` | 更像机会仓 / 情绪仓保护，不适合默认主仓 |
| 05 | `05_position_management.md` | 更像基准说明，信息量不高 |
| 06 | `06_exit_rules.md` | 模板价值有，但优先级低于 17 / 37 |
| 13 | `13_sector_rotation.md` | 更像独立 alpha 或轮动主策略 |
| 14 | `14_auction_signal.md` | 竞价 / 短线属性太强 |
| 16 | `16_macro_event_filter.md` | 更像战略辅助，不是日常默认增强 |
| 19 | `19_turnover_filter.md` | 更像 alpha 或股票池侧过滤，不是当前主线优先项 |
| 20 | `20_fed_valuation.md` | 更像大级别宏观辅助开关 |
| 21 | `21_nhnl_indicator.md` | 同上，偏大级别环境识别 |
| 22 | `22_cvix_panic.md` | 同上，偏极端环境识别 |
| 23 | `23_bottom_signals.md` | 同上，更适合战略底部辅助 |
| 26 | `26_diffusion_index_timing.md` | 对微盘更合适，主仓价值策略默认慎用 |
| 29 | `29_mac_momentum_factor.md` | 更像独立 alpha 或成长支线 |
| 39 | `39_strategy_factory_execution_checklist.md` | 更适合“从策略库抽机制”，不是单策略增强的第一优先级 |

说明：

- 这里是不建议“默认前排使用”，不是说这些文档没价值。
- 如果你后面确实只想保留主策略增强相关文档，可以把这批迁到 `archive_optional/`，而不是直接删除。

---

## 六、对当前流程最重要的使用规则

### 1. `24` / `28` 是参数增强参考，不是原始 alpha 替代品

对当前主策略：

- 可以用 `24` / `28` 去细化估值、质量、成长、持仓数
- 不要因为有这两个文档，就把原策略整条 alpha 逻辑推翻重写

### 2. `03` 的职责是总暴露，不是风格切换包装

如果策略里只是把成长和红利之间切权重，但总资金仍然 100% 暴露，那不算真正接入主路由。

`03` 用来解决的是：

- `route_scale`
- 仓位分档
- 现金比例
- 是否允许恢复

### 3. `30` / `37` 只能修正主路由，不能取代主路由

过滤器和确认层只负责：

- 升档确认
- 降档修正
- 止损后恢复确认

不要把它们直接写成：

- 单信号全仓进
- 单信号全仓出
- 单信号替代主策略

### 4. `01` / `11` / `26` 默认不要当硬停手总开关

对基本面价值 / 红利质量主策略：

- 默认先做“降档”而不是“空仓”
- 默认先做“恢复确认”而不是“直接恢复”
- 默认先用连续型控制，再考虑二元开关

### 5. `10` / `17` 优先于更复杂的强门控

对大多数主策略，先把这两类增强做好，往往比直接加更敏感的择时开关更稳：

- `10`：波动率 / 风险缩放
- `17`：退出与保护

---

## 七、推荐阅读顺序

### 如果你在增强“股票低频主仓 / 红利质量 / 价值混合”

推荐顺序：

1. `31_index_enhancement_base.md`
2. `32_master_portfolio_assembly.md`
3. `34_alpha_weight_mapping.md`
4. `03_state_router.md`
5. `10_volatility_position.md`
6. `17_trailing_stop.md`
7. `30_signalmaker_filters.md`
8. `37_signal_confirmation_interface.md`
9. `33_master_validation_pipeline.md`
10. `38_strategy_admission_oos.md`

参数细化时再读：

11. `24_fscore_selection.md`
12. `28_dividend_quality_filter.md`

### 如果你在增强 ETF / 多资产主仓

推荐顺序：

1. `31_index_enhancement_base.md`
2. `32_master_portfolio_assembly.md`
3. `08_rsrs_timing.md`
4. `25_epo_portfolio.md`
5. `27_es_risk_parity.md`
6. `10_volatility_position.md`
7. `17_trailing_stop.md`
8. `33_master_validation_pipeline.md`
9. `38_strategy_admission_oos.md`

---

## 八、和 `program_enhance.md` 的对应关系

`program_enhance.md` 现在已经改成“主策略增强版”。

因此这里的 README 也采用同一套口径：

| `program_enhance` 层级 | 本目录对应文档 |
|---|---|
| `L0 工程与执行正确性` | 04 / 31 / 32 / 34 / 35 / 36 / 37 / 33 / 38 |
| `L1 Alpha 参数增强` | 24 / 28 |
| `L2 主路由与总暴露` | 03 / 08 / 10 |
| `L3 过滤 / 确认 / 风控` | 17 / 30 / 37 / 01 / 09 / 11 / 12 / 15 / 18 / 26 |

这也是以后自动搜索应该默认遵守的顺序。

---

## 九、建议的目录整理方式

如果你后面真要把这个目录收窄成“只服务主策略增强”，推荐这样整理：

### `core/` 口径

实际意义上的核心文档应包括：

- 03, 04, 10, 17, 24, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38

### `optional/` 口径

按策略条件启用：

- 01, 08, 09, 11, 12, 15, 18, 25, 27

### `archive_optional/` 口径

不删，但不放默认搜索前排：

- 02, 05, 06, 13, 14, 16, 19, 20, 21, 22, 23, 26, 29, 39

当前我只建议先改 README 和使用口径，不建议直接批量删除文件。

---

## 十、结论

以后这个目录不再回答：

- “还有哪些神策略可以直接拿来用？”
- “有没有更多 alpha 可以替换当前主策略？”

它主要回答的是：

- 当前主策略哪里没接通？
- 哪些参数应该微调？
- 如何把主路由做成总暴露控制？
- 哪些过滤器只该做确认而不是替代主策略？
- 如何把研究原型强化成更接近实盘的主仓底座？

如果这份 README 还能让 agent 继续“随机加机制”，那它就还没改对。
