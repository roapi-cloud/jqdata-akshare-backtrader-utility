# Main Strategy Enhancement Manifest

本文件是 `universal_mechanisms/` 给 agent 的最短入口。

默认前提：

- 当前 `strategy.py` 已经是一条主仓 alpha 原型
- 本目录只提供增强模块，不提供原始 alpha 替代品
- 默认目标是“更稳、更接近实盘”，不是“重写主策略”

---

## 1. 先怎么读

默认顺序：

1. 先读本文件
2. 再按需读 `README.md`
3. 最后只打开当前层需要的机制文档

不要一次性通读全部机制文档。

---

## 2. 四层映射

### L0 工程与执行正确性

先读：

- `31_index_enhancement_base.md`
- `32_master_portfolio_assembly.md`
- `34_alpha_weight_mapping.md`
- `35_enhancement_replay_checklist.md`
- `36_data_benchmark_cost_spec.md`
- `37_signal_confirmation_interface.md`

补充：

- `04_base_filters.md`
- `33_master_validation_pipeline.md`
- `38_strategy_admission_oos.md`

适用问题：

- 状态变量没接通
- 总暴露没有真实生效
- 没有目标权重 / 现金缓冲 / 持仓上限
- 执行口径和研究口径混杂

### L1 Alpha 参数增强

先读：

- `24_fscore_selection.md`
- `28_dividend_quality_filter.md`

适用问题：

- 持仓数
- 估值 / 市值 / 质量 / 成长阈值
- 股票池范围
- 排序细化

### L2 主路由与总暴露

先读：

- `03_state_router.md`
- `10_volatility_position.md`

条件启用：

- `08_rsrs_timing.md`
- `12_breadth_index.md`

适用问题：

- route_scale
- 仓位分档
- 现金比例
- 恢复节奏

### L3 过滤 / 确认 / 风控增强

先读：

- `17_trailing_stop.md`
- `30_signalmaker_filters.md`
- `37_signal_confirmation_interface.md`

条件启用：

- `01_emotion_switch.md`
- `09_north_money.md`
- `11_consistency_control.md`
- `15_crowding_detection.md`
- `18_multi_timeframe.md`

适用问题：

- 升档确认
- 再进场确认
- 单笔大亏保护
- 止损后过早回补

---

## 3. 当前主策略的默认搜索顺序

如果当前策略属于“股票低频主仓 / 红利质量 / 价值混合”，默认只按下面顺序搜索：

1. `L0 工程与执行正确性`
2. `L1 Alpha 参数增强`
3. `L2 主路由与总暴露`
4. `L3 过滤 / 确认 / 风控增强`

禁止混搜。

---

## 4. 默认不要放前排的文档

这些文档可以保留，但不应默认排到当前主策略的前排搜索：

- `02_pause_mechanism.md`
- `13_sector_rotation.md`
- `14_auction_signal.md`
- `16_macro_event_filter.md`
- `20_fed_valuation.md`
- `21_nhnl_indicator.md`
- `22_cvix_panic.md`
- `23_bottom_signals.md`
- `26_diffusion_index_timing.md`
- `29_mac_momentum_factor.md`
- `39_strategy_factory_execution_checklist.md`

原因通常是：

- 更像独立 alpha
- 更像极端环境辅助
- 更适合微盘 / ETF / 轮动 / 短线
- 不适合作为当前主策略的默认增强入口

---

## 5. 关键约束

- `24` / `28` 用来细化原 alpha，不用来推翻原 alpha
- `03` 必须真正控制总暴露，不只是风格切换
- `30` / `37` 只能修正主路由，不能取代主路由
- `01` / `11` / `26` 默认只做确认或降档，不做硬停手总开关
- 每轮只改一个层、一个方向

如果需要更详细解释，再读 `README.md`。
