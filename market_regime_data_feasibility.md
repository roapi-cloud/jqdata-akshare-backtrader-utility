# Market Regime 识别系统 — 信息层数据可行性报告

> 基于 AKShare 开源库，逐一验证 24 个标准化指标的数据获取可行性。

---

## 1. 总览

| 类别 | 可直接获取 | 需计算得出 | 存在缺口 | 合计 |
|------|-----------|-----------|---------|------|
| 宏观/流动性 | 5 | 2 | 0 | 7 |
| 市场状态 | 3 | 2 | 1 | 6 |
| 板块状态 | 0 | 5 | 0 | 5 |
| 微观交易 | 5 | 1 | 0 | 6 |
| **合计** | **13** | **10** | **1** | **24** |

---

## 2. 逐指标详情

### 2.1 宏观/流动性（7 个）

| # | 指标 | AKShare 端点 | 关键参数 | 回溯深度 | 频率 | 状态 |
|---|------|-------------|---------|---------|------|------|
| 1 | 国债收益率(10Y) | `bond_china_yield` | start_date, end_date (需逐年拼接) | ~2002+ | 日 | ✅ 直接 |
| 2 | 信用利差 | `bond_china_yield` × 2 | 计算: AAA企业债收益率 − 国债收益率 | ~2002+ | 日 | 🔧 计算 |
| 3 | 汇率(USD/CNY) | `currency_pair_map` / `fx_spot_quote` | symbol | 长期 | 日 | ✅ 直接 |
| 4 | 北向资金净流入 | `stock_hsgt_hist_em` | symbol="北上" | ~2014+ | 日 | ✅ 直接 |
| 5 | 两市成交额 | `index_zh_a_hist` | symbol="000001"(上证) | 长期 | 日 | ✅ 直接 |
| 6 | Shibor(3M) | `rate_interbank` | market="上海银行同业拆借市场", symbol="Shibor人民币", indicator="3月" | ~2006+ | 日 | ✅ 直接 |
| 7 | 社融增量 | `macro_china_shrzgm` | 无 | ~2015+ | 月 | 🔧 计算(频率降级) |

**信用利差计算公式:**
```
信用利差 = 中债中短期票据收益率曲线(AAA, 10Y) − 中债国债收益率曲线(10Y)
```

**社融频率处理:** 月频数据在日度 regime 中做前值填充，或用 M2 增速 (`macro_china_m2_yearly`) 作高频代理。

---

### 2.2 市场状态（6 个）

| # | 指标 | AKShare 端点 | 关键参数 | 回溯深度 | 频率 | 状态 |
|---|------|-------------|---------|---------|------|------|
| 8 | 指数趋势(MA20/MA60) | `index_zh_a_hist` | symbol="000300"(沪深300) | 长期 | 日 | 🔧 计算 |
| 9 | 已实现波动率(20日) | `index_zh_a_hist` + 计算 | 日收益率 std × √252 | 长期 | 日 | 🔧 计算 |
| 10 | 波动率变化率 | 同上 | RV_t / RV_{t-1} − 1 | 长期 | 日 | 🔧 计算 |
| 11 | 涨跌家数比 | `stock_market_activity_legu` | 无 (返回上涨/下跌家数) | ~2018+ | 日 | ✅ 直接 |
| 12 | 涨停/跌停家数 | `stock_market_activity_legu` 或 `stock_zt_pool_em` / `stock_zt_pool_dtgc_em` | 无 | ~2018+ | 日 | ✅ 直接 |
| 13 | 因子拥挤度 | `stock_a_congestion_lg`(大盘拥挤度) | 无 | 有限 | 日 | ⚠️ 缺口 |

**已实现波动率计算公式:**
```python
import numpy as np
log_ret = np.log(close_series / close_series.shift(1)).dropna()
realized_vol = log_ret.rolling(20).std() * np.sqrt(252)
```

**因子拥挤度缺口说明:** AKShare 仅提供大盘整体拥挤度，无法按因子（价值/动量/质量等）拆分。替代方案：
- 方案 A: 使用大盘拥挤度作为粗粒度代理
- 方案 B: 自行构建 — 计算前 N% 高因子暴露股票的成交量占比

---

### 2.3 板块状态（5 个）

| # | 指标 | AKShare 端点 | 关键参数 | 回溯深度 | 频率 | 状态 |
|---|------|-------------|---------|---------|------|------|
| 14 | 行业排名变化 | `stock_board_industry_name_em` + 计算 | 行业日收益率排名的 rank diff | 有限 | 日 | 🔧 计算 |
| 15 | 行业集中度(HHI) | `stock_board_industry_cons_em` + 市值 | HHI = Σ(market_share²) | 有限 | 日 | 🔧 计算 |
| 16 | 行业动量离散度 | 行业成分股 20 日收益 std | 无 | 有限 | 日 | 🔧 计算 |
| 17 | 概念热度 | `stock_board_concept_name_em` | 成交额 / 换手率作代理 | 有限 | 日 | 🔧 计算 |
| 18 | 行业北向持仓 | `stock_hsgt_hold_stock_em` + 行业映射 | 按申万行业聚合 | ~2017+ | 日 | 🔧 计算 |

**HHI 计算公式:**
```python
industry_weights = industry_mkt_cap / total_mkt_cap
hhi = (industry_weights ** 2).sum()  # 范围 [1/n, 1]
```

**行业北向持仓聚合流程:**
1. 获取 `stock_hsgt_hold_stock_em` (个股北向持股)
2. 关联申万行业分类
3. 按行业汇总持股市值

---

### 2.4 微观交易（6 个）

| # | 指标 | AKShare 端点 | 关键参数 | 回溯深度 | 频率 | 状态 |
|---|------|-------------|---------|---------|------|------|
| 19 | 封板率 | `stock_zt_pool_em` + `stock_zt_pool_zbgc_em` | 涨停/(涨停+炸板) | ~2019+ | 日 | 🔧 计算 |
| 20 | 跌停家数 | `stock_zt_pool_dtgc_em` 或 `stock_market_activity_legu` | 无 | ~2018+ | 日 | ✅ 直接 |
| 21 | 换手率(全市场均值) | `stock_zh_a_spot_em` | 换手率字段求均值 | 实时/日 | 日 | ✅ 直接 |
| 22 | 量价配合度 | `index_zh_a_hist` + 计算 | 20 日价格变化与成交量变化相关系数 | 长期 | 日 | 🔧 计算 |
| 23 | 大单净流入 | `stock_individual_fund_flow_em` | 主力净流入汇总 | 有限 | 日 | ✅ 直接 |
| 24 | 融资余额 | `stock_margin_sse` + `stock_margin_szse` | 两市融资余额汇总 | ~2010+ | 日 | ✅ 直接 |

**封板率计算公式:**
```python
sealed = len(ak.stock_zt_pool_em(date))       # 涨停家数
exploded = len(ak.stock_zt_pool_zbgc_em(date)) # 炸板家数
seal_rate = sealed / (sealed + exploded)
```

**量价配合度计算公式:**
```python
price_chg = close.pct_change()
volume_chg = volume.pct_change()
vol_price_corr = price_chg.rolling(20).corr(volume_chg)
```

---

## 3. 关键缺口及替代方案汇总

| 缺口 | 原因 | 替代方案 |
|------|------|---------|
| 因子拥挤度 | AKShare 无因子维度拥挤度 | ① 用大盘拥挤度 `stock_a_congestion_lg` 做粗粒度代理<br>② 自行构建: 高因子暴露股票的成交集中度 |
| 社融频率不足 | 月频数据，日度 regime 需要更高频 | ① 月内前值填充<br>② 用 M2 + 新增信贷作高频代理 |
| 行业维度北向持仓 | 仅有个股粒度 | 用申万行业映射自行聚合 |

---

## 4. 可复用代码

| 文件 | 可复用函数 | 用途 |
|------|-----------|------|
| `backtrader_base_strategy.py` | `get_akshare_stock_data()` | 股票日线数据获取 + 本地缓存 |
| `backtrader_base_strategy.py` | `get_index_nav()` | 指数净值序列 |
| `backtrader_base_strategy.py` | `get_price()` | 统一行情接口 (聚宽风格) |
| `backtrader_base_strategy.py` | `analyze_performance()` | 策略绩效分析 |
| `jqdata_tool.py` | `get_price` / `get_fundamentals` | 聚宽适配层 |
| `akshare_stock_test.py` | 字段采集工具 | AKShare 字段元数据探索 |

---

## 5. 实施建议

### P0 — 先实现 (7 个, 可直接获取)

| 指标 | 预计工时 | 说明 |
|------|---------|------|
| 国债收益率(10Y) | 0.5d | 调用 `bond_china_yield`，逐年拼接 |
| 汇率(USD/CNY) | 0.5d | 调用 FX 接口 |
| 北向资金净流入 | 0.5d | `stock_hsgt_hist_em` |
| 两市成交额 | 0.5d | `index_zh_a_hist` |
| Shibor(3M) | 0.5d | `rate_interbank` |
| 涨跌家数比 | 0.5d | `stock_market_activity_legu` |
| 涨停/跌停家数 | 0.5d | 同上 |

### P1 — 需开发 (14 个, 需计算逻辑)

| 指标 | 预计工时 | 复杂度 |
|------|---------|--------|
| 信用利差 | 1d | 低 — 双曲线相减 |
| 社融(前值填充) | 0.5d | 低 |
| 指数趋势 | 0.5d | 低 — MA 比值 |
| 已实现波动率 | 0.5d | 低 — rolling std |
| 波动率变化率 | 0.5d | 低 — 比值 |
| 行业排名变化 | 2d | 中 — 需行业数据管线 |
| 行业集中度(HHI) | 2d | 中 — 需行业市值 |
| 行业动量离散度 | 2d | 中 — 需行业成分股 |
| 概念热度 | 1d | 中 |
| 行业北向持仓 | 2d | 中 — 需行业映射 |
| 封板率 | 1d | 低 — 涨停/炸板比 |
| 换手率均值 | 0.5d | 低 — 截面均值 |
| 量价配合度 | 1d | 低 — rolling corr |
| 融资余额 | 1d | 低 — 两市汇总 |

### P2 — 待解决 (3 个, 有数据缺口)

| 指标 | 风险 | 候选方案 |
|------|------|---------|
| 因子拥挤度 | 无因子维度数据 | 自建因子暴露 → 成交集中度指标 |
| 社融高频 | 月频限制 | M2 + 信贷脉冲代理 |
| 大盘拥挤度细化 | 粒度不足 | 聚宽付费 API / Wind 备选 |

---

## 6. 数据质量注意事项

| 风险类型 | 涉及指标 | 说明 |
|---------|---------|------|
| 接口稳定性 | 全部 | AKShare 为爬虫封装，东方财富/同花顺改版可能导致失效 |
| 历史数据缺失 | 行业类指标 | 申万行业板块数据回溯有限，~2019 后较完整 |
| 延迟 | 融资余额、北向资金 | T+1 披露 |
| 幸存者偏差 | 涨停/跌停数据 | ST 股、新股需过滤 |
| 年报窗口 | 社融、M2 | 季末/年末数据发布滞后 |

---

*报告生成时间: 2026-03-31*
*数据源: AKShare 1.18.x 文档 + 当前工作空间代码*
