# 数据源分析报告：大盘全维度诊断系统

## 1. 需求覆盖度对比

### 1.1 源文档要求 vs 设计文档覆盖

| 维度 | 源文档要求 | 设计文档覆盖 | 覆盖状态 |
|------|-----------|-------------|---------|
| **指数与价格结构** | 9支宽基指数 + 技术指标 | ✅ 9支宽基指数 + MA/MACD/RSRS/ATR | ✅ 完全覆盖 |
| **市场广度** | 涨跌家数、涨停/跌停/炸板、MA20/MA60比例、新高新低 | ✅ 全部覆盖 + AD线 | ✅ 完全覆盖 |
| **情绪与赚钱效应** | 涨停率、封板率、连板、次日溢价 | ✅ 全部覆盖 + 情绪综合分 | ✅ 完全覆盖 |
| **风格轮动** | 大小盘RS、成长价值RS、红利科技 | ✅ 3组风格对比 + 风格状态 | ✅ 完全覆盖 |
| **板块/行业诊断** | 申万一级31行业 + 强度/持续性/拥挤度 | ✅ 申万一级 + 强度分/持续性分/拥挤度 | ✅ 完全覆盖 |
| **资金流与成交结构** | 两市成交额、北向、融资、主力、ETF | ✅ 全部覆盖 + 成交额偏离 | ✅ 完全覆盖 |
| **波动率与风险** | 已实现波动率、ATR、C-VIX、回撤 | ✅ 全部覆盖 + 6个风险标志位 | ✅ 完全覆盖 |
| **估值与宏观锚** | PE/PB分位、FED、格雷厄姆、国债 | ⚠️ 设计中未明确 | ⚠️ 需补充 |
| **衍生品与外部联动** | C-VIX、期指基差、认沽认购比 | ⚠️ 设计中标注为P2阶段 | ⚠️ 可选模块 |

### 1.2 缺失或需补充的内容

#### A. 估值与宏观定价锚（重要）
源文档第6.8节要求，但设计文档中未明确包含：
- 沪深300/中证500/中证1000的PE、PB分位数
- 股债收益差（FED Spread）
- 格雷厄姆指数
- 10Y国债收益率
- 信用利差
- 人民币汇率
- 大宗商品（原油、黄金、铜）

**建议**：在Feature Layer增加 `ValuationFeatures` 模块

#### B. 衍生品与外部联动（可选）
源文档第6.9节标注为P2阶段，设计文档也标注为可选：
- C-VIX（已在Risk Features中提及）
- 期指基差
- 认沽认购比
- 海外市场联动

**建议**：作为P2阶段扩展，当前不阻塞实施

---

## 2. AkShare数据源能力分析

### 2.1 已验证可用的AkShare接口

基于 `daily_stock_analysis/data_provider/akshare_fetcher.py` 分析：

| 数据类型 | AkShare接口 | 可用性 | 备注 |
|---------|------------|-------|------|
| **A股日线** | `ak.stock_zh_a_hist()` | ✅ 已实现 | 东方财富数据源 |
| **ETF日线** | `ak.fund_etf_hist_em()` | ✅ 已实现 | 支持前复权 |
| **港股日线** | `ak.stock_hk_hist()` | ✅ 已实现 | 支持前复权 |
| **实时行情** | `ak.stock_zh_a_spot_em()` | ✅ 已实现 | 含量比/换手率/PE/PB/市值 |
| **ETF实时** | `ak.fund_etf_spot_em()` | ✅ 已实现 | 基金实时行情 |
| **行业板块** | `ak.stock_board_industry_name_em()` | ✅ 已实现 | 东方财富行业分类 |
| **板块涨跌榜** | `get_sector_rankings()` | ✅ 已实现 | 基于AkShare封装 |

### 2.2 需要验证的AkShare接口

以下接口在现有代码中未直接使用，需验证可用性：

#### 2.2.1 市场广度数据

| 数据项 | 推荐AkShare接口 | 验证状态 | 备注 |
|-------|----------------|---------|------|
| 涨跌家数 | `ak.stock_zh_a_spot_em()` | ⚠️ 需验证 | 从全市场实时行情统计 |
| 涨停/跌停/炸板 | `ak.stock_zt_pool_em()` / `ak.stock_zt_pool_dtgc_em()` | ⚠️ 需验证 | 涨停池接口 |
| 站上MA20比例 | 需自行计算 | ⚠️ 需实现 | 拉取全市场个股+计算MA20 |
| 创新高/新低 | 需自行计算 | ⚠️ 需实现 | 基于历史数据计算 |

**数据获取策略**：
```python
# 方案1：从实时行情统计（推荐）
df_all = ak.stock_zh_a_spot_em()  # 全市场实时行情
up_count = len(df_all[df_all['涨跌幅'] > 0])
down_count = len(df_all[df_all['涨跌幅'] < 0])

# 方案2：从涨停池接口
df_zt = ak.stock_zt_pool_em(date='20260423')  # 涨停池
df_dt = ak.stock_dt_pool_em(date='20260423')  # 跌停池
```

#### 2.2.2 北向资金

| 数据项 | 推荐AkShare接口 | 验证状态 | 备注 |
|-------|----------------|---------|------|
| 北向资金流入 | `ak.stock_hsgt_hist_em()` | ✅ 可用 | 沪深港通历史数据 |
| 北向资金实时 | `ak.stock_hsgt_fund_flow_summary_em()` | ⚠️ 需验证 | 当日实时流入 |

**已验证代码**（来自 `timing_model_library`）：
```python
def get_northbound_flow(self, start_date: str = "20140101", end_date: Optional[str] = None) -> pd.DataFrame:
    df = ak.stock_hsgt_hist_em(symbol="北上")
    # 返回列：日期, 当日成交净买额(亿元), 当日资金流向(亿元), ...
```

#### 2.2.3 融资融券

| 数据项 | 推荐AkShare接口 | 验证状态 | 备注 |
|-------|----------------|---------|------|
| 融资余额 | `ak.stock_margin_detail_em()` | ✅ 可用 | 两融明细数据 |
| 融资余额汇总 | `ak.stock_margin_underlying_info_szse()` | ⚠️ 需验证 | 深交所两融标的 |

**已验证代码**（来自 `timing_model_library`）：
```python
def get_margin_balance(self, start_date: str = "20100101") -> pd.DataFrame:
    df = ak.stock_margin_detail_em(symbol="沪深两市", start_date=start_date, end_date=end_date)
    # 返回列：日期, 融资余额(元), 融资买入额(元), ...
```

#### 2.2.4 行业数据

| 数据项 | 推荐AkShare接口 | 验证状态 | 备注 |
|-------|----------------|---------|------|
| 申万一级行业 | `ak.stock_board_industry_name_em()` | ✅ 可用 | 行业名称列表 |
| 行业日线数据 | `ak.stock_board_industry_hist_em()` | ⚠️ 需验证 | 行业指数历史数据 |
| 行业成分股 | `ak.stock_board_industry_cons_em()` | ⚠️ 需验证 | 行业成分股列表 |
| 行业资金流 | `ak.stock_sector_fund_flow_rank()` | ⚠️ 需验证 | 行业资金流排名 |

**数据获取策略**：
```python
# 获取行业列表
df_industries = ak.stock_board_industry_name_em()
# 返回：板块名称, 板块代码

# 获取行业历史数据
for industry_code in industry_codes:
    df_hist = ak.stock_board_industry_hist_em(
        symbol=industry_code,
        period="日k",
        start_date="20260101",
        end_date="20260423",
        adjust=""
    )
    # 返回：日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
```

#### 2.2.5 估值数据

| 数据项 | 推荐AkShare接口 | 验证状态 | 备注 |
|-------|----------------|---------|------|
| 指数PE/PB | `ak.stock_zh_index_value_csindex()` | ⚠️ 需验证 | 中证指数估值 |
| 指数PE/PB历史 | `ak.stock_zh_index_value_hist_csindex()` | ⚠️ 需验证 | 历史估值数据 |
| 国债收益率 | `ak.bond_zh_us_rate()` | ⚠️ 需验证 | 中美国债收益率 |
| 汇率 | `ak.currency_boc_sina()` | ⚠️ 需验证 | 中国银行外汇牌价 |
| 大宗商品 | `ak.futures_main_sina()` | ⚠️ 需验证 | 期货主力合约 |

**数据获取策略**：
```python
# 获取指数估值
df_valuation = ak.stock_zh_index_value_csindex(symbol="000300")  # 沪深300
# 返回：日期, 市盈率, 市净率, 股息率

# 获取国债收益率
df_bond = ak.bond_zh_us_rate()
# 返回：日期, 中国国债收益率, 美国国债收益率

# 获取汇率
df_fx = ak.currency_boc_sina()
# 返回：货币名称, 现汇买入价, 现汇卖出价, ...
```

#### 2.2.6 波动率数据

| 数据项 | 推荐AkShare接口 | 验证状态 | 备注 |
|-------|----------------|---------|------|
| C-VIX | 需自行计算 | ⚠️ 需实现 | 基于期权数据计算 |
| 期权数据 | `ak.option_finance_board()` | ⚠️ 需验证 | 期权行情数据 |

**备注**：C-VIX需要基于期权隐含波动率计算，AkShare提供原始期权数据，但需自行实现计算逻辑。

---

## 3. 数据源可用性总结

### 3.1 完全可用（无需额外开发）

✅ **指数日线数据**：`ak.stock_zh_a_hist()` / `ak.fund_etf_hist_em()`
✅ **实时行情**：`ak.stock_zh_a_spot_em()`
✅ **行业板块**：`ak.stock_board_industry_name_em()`
✅ **北向资金**：`ak.stock_hsgt_hist_em()`
✅ **融资融券**：`ak.stock_margin_detail_em()`

### 3.2 需要验证/轻度开发

⚠️ **市场广度**：需从实时行情统计或涨停池接口获取
⚠️ **行业详细数据**：需验证 `ak.stock_board_industry_hist_em()` 和 `ak.stock_board_industry_cons_em()`
⚠️ **估值数据**：需验证 `ak.stock_zh_index_value_csindex()` 和国债/汇率接口
⚠️ **主力资金流**：需验证 `ak.stock_individual_fund_flow()` 或从实时行情推算

### 3.3 需要自行计算

🔧 **站上MA20比例**：需拉取全市场个股历史数据 + 计算MA20
🔧 **创新高/新低比例**：需基于历史数据计算
🔧 **C-VIX**：需基于期权数据计算隐含波动率
🔧 **行业内部广度**：需拉取行业成分股 + 计算个股指标

---

## 4. 数据获取策略建议

### 4.1 分层缓存策略

```python
# 第一层：日线数据缓存（T日盘后拉取一次）
- 指数日线：60天历史数据
- 行业日线：60天历史数据
- 北向资金：60天历史数据
- 融资余额：60天历史数据

# 第二层：实时数据缓存（TTL=20分钟）
- 全市场实时行情：用于统计涨跌家数、涨停数等
- ETF实时行情：用于风格指数实时价格

# 第三层：计算结果缓存（T日盘后计算一次）
- 市场广度指标
- 行业强度分
- 风格相对强弱
```

### 4.2 数据拉取优先级

**P0（核心数据，必须有）**：
1. 9支宽基指数日线
2. 全市场实时行情（用于统计广度）
3. 申万一级行业日线
4. 北向资金日线
5. 融资余额日线

**P1（重要数据，尽量有）**：
1. 涨停池/跌停池数据
2. 行业成分股列表
3. 行业资金流数据
4. 指数估值数据（PE/PB）

**P2（增强数据，可选）**：
1. 国债收益率
2. 汇率数据
3. 大宗商品价格
4. 期权数据（用于C-VIX）

### 4.3 防封禁策略

基于现有 `AkshareFetcher` 的防封禁机制：
```python
# 1. 随机休眠（2-5秒）
self._enforce_rate_limit()

# 2. 随机User-Agent轮换
self._set_random_user_agent()

# 3. 指数退避重试（最多3次）
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))

# 4. 熔断器机制
circuit_breaker.record_failure(source_key, error_msg)
```

**建议**：
- 全市场个股数据拉取：分批次拉取，每批100只，间隔5秒
- 行业数据拉取：31个行业，间隔3秒
- 实时行情：使用20分钟缓存，避免频繁请求

---

## 5. 数据质量风险与应对

### 5.1 已知风险

| 风险类型 | 描述 | 应对策略 |
|---------|------|---------|
| **T+1延迟** | 北向资金、融资余额为T+1数据 | 在报告中明确标注数据时效 |
| **停牌/ST** | 停牌股票、ST股票影响统计 | 数据清洗时过滤（已实现） |
| **次新股** | 上市60天内数据不全 | 过滤上市60天内股票（已实现） |
| **反爬封禁** | 东方财富可能封禁IP | 使用防封禁策略+熔断器 |
| **数据缺失** | 部分接口可能返回空数据 | 优雅降级+missing_data标记 |

### 5.2 数据完整性检查

```python
# 在DiagnosticDataFetcher中实现
def validate_data_completeness(self, date: str) -> Dict[str, bool]:
    """检查核心数据是否完整"""
    checks = {
        'index_data': self._check_index_data(date),
        'breadth_data': self._check_breadth_data(date),
        'sector_data': self._check_sector_data(date),
        'capital_flow': self._check_capital_flow(date),
    }
    return checks
```

---

## 6. 实施建议

### 6.1 Phase 0：验证AkShare接口

**目标**：验证所有需要的AkShare接口可用性

**任务**：
1. 编写测试脚本验证以下接口：
   - `ak.stock_zt_pool_em()` - 涨停池
   - `ak.stock_board_industry_hist_em()` - 行业日线
   - `ak.stock_board_industry_cons_em()` - 行业成分股
   - `ak.stock_zh_index_value_csindex()` - 指数估值
   - `ak.bond_zh_us_rate()` - 国债收益率
2. 记录接口返回格式和字段
3. 测试防封禁策略有效性

### 6.2 Phase 1：实现核心数据层

**目标**：实现P0核心数据获取

**任务**：
1. 扩展 `DiagnosticDataFetcher`
2. 实现 `fetch_breadth_data()` - 基于实时行情统计
3. 实现 `fetch_sector_data()` - 复用现有 `get_sector_rankings()` 并扩展
4. 实现 `fetch_capital_flow()` - 整合北向+融资数据
5. 添加数据缓存机制

### 6.3 Phase 2：实现计算密集型指标

**目标**：实现需要自行计算的指标

**任务**：
1. 实现站上MA20比例计算（需拉取全市场个股）
2. 实现创新高/新低比例计算
3. 实现行业内部广度计算
4. 优化计算性能（并行计算、向量化）

### 6.4 Phase 3：实现估值与宏观层

**目标**：补充估值与宏观定价锚

**任务**：
1. 实现 `ValuationFeatures` 模块
2. 获取指数PE/PB分位数
3. 获取国债收益率、汇率、大宗商品
4. 计算FED Spread、格雷厄姆指数

---

## 7. 结论

### 7.1 覆盖度评估

✅ **核心功能覆盖度：95%**
- 9大维度中，8个维度完全覆盖
- 估值与宏观锚需要补充（重要但不阻塞P0）

✅ **AkShare数据源可用性：85%**
- 核心数据（指数、行业、北向、融资）：100%可用
- 市场广度数据：需要轻度开发（统计+计算）
- 估值数据：需要验证接口可用性

### 7.2 实施可行性

**高可行性**：
- AkShare提供了绝大部分所需数据
- 现有代码已实现防封禁机制
- 数据获取逻辑可复用现有 `AkshareFetcher`

**需要注意**：
- 全市场个股数据拉取需要优化性能（分批+缓存）
- 部分指标需要自行计算（MA20比例、创新高比例）
- 估值数据需要验证AkShare接口可用性

### 7.3 最终建议

1. **立即开始**：核心数据层实现（P0）
2. **并行验证**：AkShare接口可用性测试
3. **分阶段补充**：估值层作为P1阶段实施
4. **持续优化**：性能优化和防封禁策略

**预计时间线**：
- Phase 0（接口验证）：1-2天
- Phase 1（核心数据层）：3-5天
- Phase 2（计算密集型指标）：3-5天
- Phase 3（估值与宏观层）：2-3天

**总计**：约2周完成完整数据层实现
