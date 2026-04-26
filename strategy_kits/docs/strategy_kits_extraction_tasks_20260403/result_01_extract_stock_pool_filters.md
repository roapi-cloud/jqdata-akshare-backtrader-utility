# 任务 01：A 股股票池过滤器抽取结果

## 1. 可复用过滤器清单

### 1.1 第一版立即实现（核心必选）

| 过滤器名称 | 功能说明 | 源代码位置 | 实现要点 |
|-----------|---------|-----------|---------|
| `filter_st` | 过滤ST、\*ST、退市股票 | 聚宽558/01, 37, 86等所有策略 | 检查 `is_st` 字段 + 名称包含 ST/\*/退 |
| `filter_paused` | 过滤停牌股票 | 聚宽558/所有策略、QuantsPlaybook/BuildStockPool.py | 检查 `paused` 字段，支持停牌天数阈值 |
| `filter_new_stock` | 过滤次新股（上市不足N天） | 聚宽558/01, 86等，默认250-500天 | 计算上市日期与当前日期差值 |
| `filter_limitup` | 过滤涨停不可买股票 | 聚宽558/37, 30, 01等 | 对比最新价与涨停价，已持仓保留 |
| `filter_limitdown` | 过滤跌停不可买股票 | 聚宽558/37, 30等 | 对比最新价与跌停价，边界需说明 |
| `filter_kcbj` | 过滤科创板/北交所 | 聚宽558/37, 86等 | 代码前缀过滤：4开头、8开头、68开头 |

### 1.2 第二版扩展（可选）

| 过滤器名称 | 功能说明 | 源代码位置 | 备注 |
|-----------|---------|-----------|------|
| `filter_industry` | 过滤指定行业 | QuantsPlaybook/BuildStockPool.py:110-114 | 行业分类支持 sw_l1 等 |
| `filter_low_liquidity` | 过滤低流动性股票 | QuantsPlaybook部分策略提及 | 需定义流动性阈值（成交量/换手率） |
| `filter_blacklist` | 自定义黑名单过滤 | 聚宽558/86（预判ST避雷） | 支持外部注入黑名单 |

## 2. 源代码关键实现片段

### 2.1 ST过滤（聚宽风格）

```python
# 聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:236-241
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]
```

### 2.2 停牌过滤（QuantsPlaybook工程化版本）

```python
# QuantsPlaybook/B-因子构建类/高频价量相关性/Hugos_tools/BuildStockPool.py:52-78
def filter_paused(self, paused_N:int=1, threshold:int=None)->list:
    '''过滤停牌股
    输入:
        paused_N:默认为1即查询当日不停牌
        threshold:在过paused_N日内停牌数量小于threshold
    '''
    paused = get_price(self.securities, end_date=self.watch_date, 
                      count=paused_N, fields='paused', panel=False)
    paused = paused.pivot(index='time', columns='code')['paused']
    
    if threshold:
        sum_paused_day = paused.sum()
        self.securities = sum_paused_day[sum_paused_day < threshold].index.tolist()
    else:
        paused_ser = paused.iloc[-1]
        self.securities = paused_ser[paused_ser == 0].index.tolist()
```

### 2.3 涨停/跌停过滤（边界说明）

```python
# 聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:251-262
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
            if stock in context.portfolio.positions.keys()  # 已持仓保留
            or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
            if stock in context.portfolio.positions.keys()  # 已持仓保留
            or last_prices[stock][-1] > current_data[stock].low_limit]
```

**边界说明**：
- 涨停：当日已涨停股票无法买入，但已持仓股票允许保留观察
- 跌停：当日已跌停股票买入可能成交困难，卖出确定无法成交，需策略层决策

### 2.4 科创/北交所过滤

```python
# 聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:244-248
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list
```

**代码前缀规则**：
- `4`开头：北交所（如430001）
- `8`开头：北交所（如830001）
- `68`开头：科创板（如688001）

### 2.5 次新股过滤

```python
# 聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:265-267
def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list 
            if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)]
```

## 3. 统一接口设计

### 3.1 输入 Contract

```python
@dataclass
class FilterInput:
    base_universe: List[str]        # 基础股票池（股票代码列表）
    date: datetime.date            # 过滤日期
    config: Dict[str, Any]         # 过滤配置参数
    positions: Optional[List[str]] # 当前持仓股票列表（涨停/跌停过滤用）
```

### 3.2 输出 Contract

```python
@dataclass
class FilterOutput:
    filtered_universe: List[str]           # 过滤后的股票池
    filter_stats: Dict[str, int]           # 统计信息：各过滤器移除数量
    removed_reasons: Dict[str, List[str]]  # 移除原因：{原因: [股票列表]}
```

### 3.3 单个过滤器接口

```python
def filter_xxx(input: FilterInput) -> FilterOutput:
    """
    过滤器函数统一签名
    - 输入：FilterInput
    - 输出：FilterOutput（仅包含本过滤器移除信息）
    """
```

### 3.4 组合过滤器接口

```python
def apply_filters(
    base_universe: List[str],
    date: datetime.date,
    filter_config: Dict[str, Dict[str, Any]],
    positions: Optional[List[str]] = None
) -> FilterOutput:
    """
    应用多个过滤器，返回最终结果
    filter_config格式：{
        'st': {'enabled': True},
        'paused': {'enabled': True, 'threshold': None},
        'new_stock': {'enabled': True, 'min_days': 250},
        'limitup': {'enabled': True},
        'limitdown': {'enabled': False},  # 可配置开关
        'kcbj': {'enabled': True}
    }
    """
```

## 4. 目标目录与文件拆分

### 4.1 目标目录结构

```
strategy_kits/universe/stock_pool_filters/
├── __init__.py                    # 导出所有过滤器
├── contract.py                    # 输入输出数据类定义
├── base_filter.py                 # 过滤器基类（可选）
├── filter_st.py                   # ST过滤
├── filter_paused.py               # 停牌过滤
├── filter_new_stock.py            # 次新股过滤
├── filter_limitup.py              # 涨停过滤
├── filter_limitdown.py            # 跌停过滤
├── filter_kcbj.py                 # 科创/北交所过滤
├── filter_pipeline.py             # 组合过滤器执行管道
├── default_config.py              # 默认配置
└── README.md                      # 使用说明
```

### 4.2 文件职责说明

| 文件名 | 职责 | 第一版是否实现 |
|-------|------|--------------|
| `contract.py` | 定义 FilterInput/FilterOutput 数据类 | ✅ |
| `filter_st.py` | ST过滤实现 | ✅ |
| `filter_paused.py` | 停牌过滤实现（支持停牌天数阈值） | ✅ |
| `filter_new_stock.py` | 次新股过滤实现（参数化上市天数） | ✅ |
| `filter_limitup.py` | 涨停过滤实现（保留持仓） | ✅ |
| `filter_limitdown.py` | 跌停过滤实现（保留持仓+边界说明） | ✅ |
| `filter_kcbj.py` | 科创/北交所过滤实现 | ✅ |
| `filter_pipeline.py` | 组合过滤器管道 | ✅ |
| `default_config.py` | 默认配置字典 | ✅ |
| `filter_industry.py` | 行业过滤 | ❌（第二版） |
| `filter_low_liquidity.py` | 低流动性过滤 | ❌（第二版） |

## 5. 推荐默认配置

```python
DEFAULT_FILTER_CONFIG = {
    'st': {
        'enabled': True,
        'check_name': True,  # 是否额外检查名称中ST/*/退
    },
    'paused': {
        'enabled': True,
        'paused_N': 1,      # 查询当天
        'threshold': None,  # 不使用停牌天数阈值
    },
    'new_stock': {
        'enabled': True,
        'min_days': 250,    # 默认上市250天以上
    },
    'limitup': {
        'enabled': True,    # 买入时默认过滤涨停
        'keep_positions': True,  # 保留持仓
    },
    'limitdown': {
        'enabled': False,   # 默认不启用（边界复杂）
        'keep_positions': True,
    },
    'kcbj': {
        'enabled': True,    # 默认过滤科创/北交所
    },
}
```

## 6. 不应抽取的内容（边界）

### 6.1 保留在策略层

| 内容 | 原因 |
|-----|------|
| 最终股票池数量限制（如取前100只） | 策略特有的持仓数量控制 |
| 市值排序/打分排序 | 因子选股逻辑，非股票池过滤 |
| 行业中性/行业权重配置 | 策略组合构建逻辑 |
| 具体因子筛选条件（如EPS>0） | 因子选股，非通用过滤 |
| 预判ST的复杂逻辑（聚宽558/86） | 需要财报分析，暂不纳入基础过滤 |
| 流动性阈值的具体数值 | 策略特定参数，暂不标准化 |

### 6.2 过滤器职责边界

- **过滤器职责**：移除明确不可交易/不合规的股票（ST、停牌、次新、涨跌停、板块限制）
- **策略层职责**：在过滤后股票池上进行选股、打分、排序、数量控制

## 7. 第一版实现顺序

1. **Step 1**：创建 `contract.py`（定义 FilterInput/FilterOutput）
2. **Step 2**：实现 `filter_st.py`、`filter_paused.py`、`filter_new_stock.py`（最基础、最稳定）
3. **Step 3**：实现 `filter_kcbj.py`（板块过滤，规则简单）
4. **Step 4**：实现 `filter_limitup.py`、`filter_limitdown.py`（涨跌停，需持仓参数）
5. **Step 5**：实现 `filter_pipeline.py`（组合过滤器管道）
6. **Step 6**：创建 `default_config.py` 和 `README.md`

## 8. 数据依赖说明

### 8.1 必需数据字段

| 过滤器 | 必需字段 | 数据来源 |
|-------|---------|---------|
| ST | `is_st`、股票名称 | get_extras('is_st')、get_security_info |
| 停牌 | `paused` | get_price(fields='paused') |
| 次新 | 上市日期 `start_date` | get_security_info |
| 涨停/跌停 | `high_limit`、`low_limit`、最新价 | get_current_data、get_price |
| 科创/北交所 | 股票代码 | 代码前缀规则 |

### 8.2 数据接口适配建议

- 需实现聚宽风格API的本地适配：
  - `get_extras('is_st', stock_list, date)`
  - `get_price(stock_list, fields='paused', date)`
  - `get_security_info(stock).start_date`
  - `get_current_data()[stock].high_limit/low_limit`
- 或使用 AkShare 适配：
  - ST数据：`ak.stock_zh_a_st_em()`
  - 停牌数据：`ak.stock_zh_a_stop_em()`
  - 上市日期：`ak.stock_info_a_code_name()`
  - 涨跌停价：需计算（前日收盘价 × 涨跌停幅度）

## 9. 使用示例（预期）

```python
from strategy_kits.universe.stock_pool_filters import apply_filters, DEFAULT_FILTER_CONFIG

# 获取基础股票池
base_universe = get_all_securities('stock', date).index.tolist()

# 应用过滤器
result = apply_filters(
    base_universe=base_universe,
    date=date,
    filter_config=DEFAULT_FILTER_CONFIG,
    positions=list(context.portfolio.positions.keys())  # 传入持仓
)

# 获取过滤后的股票池
filtered_stocks = result.filtered_universe

# 查看过滤统计
print(result.filter_stats)  
# {'st': 15, 'paused': 3, 'new_stock': 8, 'limitup': 2}

# 查看移除原因
print(result.removed_reasons['st'])  # ['600001.XSHG', ...]
```

## 10. 验收标准

- ✅ 新策略可直接调用 `apply_filters`，无需复制粘贴过滤代码
- ✅ 过滤器参数可通过 `filter_config` 配置，不硬编码
- ✅ 输入输出接口统一，便于扩展新过滤器
- ✅ 过滤统计和移除原因清晰，便于调试和日志
- ✅ 职责边界明确：过滤器只做合规/可交易性判断，不做选股打分

## 11. 后续扩展建议

- 第二版增加行业过滤、流动性过滤、自定义黑名单
- 支持过滤器开关和参数热更新
- 支持不同市场的过滤器配置（如港股、美股）
- 提供过滤器性能优化版本（批量查询、缓存）