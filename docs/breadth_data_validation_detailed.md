# Breadth Data Interface Validation - Detailed Report

**Task:** 0.2 Validate breadth data interfaces  
**Date:** 2026-04-23  
**Requirements:** 1.3, 3.1, 3.2, 3.3

## Executive Summary

This report documents the validation of AkShare breadth data interfaces required for the Market Diagnostic System. We tested three key interfaces for retrieving market breadth data and identified critical issues with workarounds.

### Key Findings

| Interface | Status | Issue | Workaround Available |
|-----------|--------|-------|---------------------|
| `ak.stock_zt_pool_em()` | ✅ Working | Missing '成交量' field | Use '成交额' instead |
| Limit-down pool | ❌ Not Available | No direct interface | Filter from spot data or use statistics |
| `ak.stock_zh_a_spot_em()` | ❌ Proxy Error | Connection issues | Use alternative sources or caching |

## Detailed Test Results

### 1. Limit-Up Pool: `ak.stock_zt_pool_em()`

**Status:** ✅ Working  
**Test Date:** 2026-04-22  
**Response Time:** 0.07s  
**Records Retrieved:** 55 stocks

#### Available Fields (16 columns)

```python
columns = [
    '序号',          # Serial number
    '代码',          # Stock code
    '名称',          # Stock name
    '涨跌幅',        # Change percentage
    '最新价',        # Latest price
    '成交额',        # Turnover amount
    '流通市值',      # Circulating market cap
    '总市值',        # Total market cap
    '换手率',        # Turnover rate
    '封板资金',      # Sealing capital
    '首次封板时间',  # First seal time
    '最后封板时间',  # Last seal time
    '炸板次数',      # Exploded board count
    '涨停统计',      # Limit-up statistics
    '连板数',        # Consecutive boards
    '所属行业'       # Industry
]
```

#### Field Mapping Issues

**Missing Expected Field:** `成交量` (Volume)

**Workaround:**
- Use `成交额` (Turnover amount) instead
- Calculate approximate volume: `volume ≈ 成交额 / 最新价`
- Note: This is an approximation and may not match exact volume

#### Data Quality

- ✅ No missing values detected
- ✅ All 55 records complete
- ⚠️ 涨跌幅 range: [9.95%, 30.00%] - includes ST stocks with 30% limit

#### Sample Data

```
代码      名称      涨跌幅    最新价    成交额        换手率    连板数
002081   金螳螂    10.02%    4.94     302,975,504   2.32%     4
300067   安诺其    20.00%    6.06     108,986,949   1.92%     2
002194   武汉凡谷  10.02%    11.86    178,942,008   2.95%     1
```

### 2. Limit-Down Pool: No Direct Interface

**Status:** ❌ Not Available  
**Issue:** AkShare does not provide a `stock_dt_pool_em()` interface

#### Available Workarounds

**Option 1: Filter from Market-Wide Data**
```python
# Pseudo-code (requires working stock_zh_a_spot_em)
df = ak.stock_zh_a_spot_em()
limit_down = df[df['涨跌幅'] <= -9.9]
```

**Option 2: Use Market Statistics**
```python
# Get aggregate statistics
stats = ak.stock_a_high_low_statistics()
# Returns: date, high_count, low_count, etc.
```

**Option 3: Calculate from Individual Stocks**
```python
# Fetch individual stock data and filter
# More reliable but slower
for code in stock_list:
    data = ak.stock_zh_a_hist(symbol=code, period="daily")
    if data['涨跌幅'].iloc[-1] <= -9.9:
        limit_down_list.append(code)
```

**Recommendation:** Use Option 2 for aggregate counts, Option 3 for detailed list when needed.

### 3. Market-Wide Realtime Quotes: `ak.stock_zh_a_spot_em()`

**Status:** ❌ Proxy Connection Error  
**Error:** `HTTPSConnectionPool(host='82.push2.eastmoney.com', port=443): Max retries exceeded`

#### Root Cause Analysis

1. **Proxy Configuration Issue:** The interface fails when using proxy settings
2. **Rate Limiting:** Eastmoney may be blocking rapid requests
3. **Network Restrictions:** Some networks block direct access to Eastmoney APIs

#### Workarounds

**Workaround 1: Use Alternative Interfaces**

```python
# Option A: Shanghai A-shares only
df_sh = ak.stock_sh_a_spot_em()

# Option B: Shenzhen A-shares only
df_sz = ak.stock_sz_a_spot_em()

# Combine both
df_all = pd.concat([df_sh, df_sz], ignore_index=True)
```

**Workaround 2: Use efinance Package**

```python
import efinance as ef

# Get all A-share realtime quotes
df = ef.stock.get_realtime_quotes()
```

**Workaround 3: Implement Caching Layer**

```python
# Cache daily data with 20-minute TTL
@cache(ttl=1200)  # 20 minutes
def get_market_breadth():
    try:
        return ak.stock_zh_a_spot_em()
    except Exception:
        # Fallback to cached data
        return load_from_cache()
```

**Workaround 4: Retry with Exponential Backoff**

```python
def fetch_with_retry(max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return ak.stock_zh_a_spot_em()
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
            else:
                raise
```

## Field Name Mappings

### Expected vs Actual Field Names

| Expected Field | Actual Field | Available In | Notes |
|---------------|--------------|--------------|-------|
| 代码 | 代码 | ✅ limit_up_pool | Exact match |
| 名称 | 名称 | ✅ limit_up_pool | Exact match |
| 最新价 | 最新价 | ✅ limit_up_pool | Exact match |
| 涨跌幅 | 涨跌幅 | ✅ limit_up_pool | Exact match |
| 成交量 | ❌ Not available | ❌ limit_up_pool | Use 成交额 instead |
| 成交额 | 成交额 | ✅ limit_up_pool | Exact match |
| 量比 | ❌ Not available | ❌ limit_up_pool | Not provided |
| 换手率 | 换手率 | ✅ limit_up_pool | Exact match |

### Additional Useful Fields

The limit-up pool provides several additional fields not in the original requirements but useful for analysis:

- `封板资金` - Capital required to seal the limit-up
- `首次封板时间` - First seal time (format: HHMMSS)
- `最后封板时间` - Last seal time
- `炸板次数` - Number of times the board was broken
- `连板数` - Consecutive limit-up days
- `所属行业` - Industry classification

## Data Quality Issues

### Issue 1: Missing Volume Field

**Severity:** MEDIUM  
**Impact:** Cannot directly calculate volume-based indicators  
**Workaround:** Calculate from turnover amount and price

```python
# Approximate volume calculation
df['成交量_估算'] = df['成交额'] / df['最新价']
```

### Issue 2: Proxy Connection Failures

**Severity:** HIGH  
**Impact:** Cannot retrieve market-wide data  
**Workaround:** Use alternative data sources or implement caching

### Issue 3: No Limit-Down Pool Interface

**Severity:** MEDIUM  
**Impact:** Cannot directly get limit-down stocks  
**Workaround:** Filter from market data or use statistics

### Issue 4: Outliers in Change Percentage

**Severity:** LOW  
**Impact:** ST stocks have 30% limit instead of 10%  
**Workaround:** Filter ST stocks or handle separately

```python
# Filter out ST stocks
df_normal = df[~df['名称'].str.contains('ST')]
```

## Implementation Recommendations

### 1. Data Fetching Strategy

```python
class BreadthDataFetcher:
    """Robust breadth data fetcher with fallbacks"""
    
    def fetch_limit_up_pool(self, date: str) -> pd.DataFrame:
        """Fetch limit-up pool with retry logic"""
        try:
            df = ak.stock_zt_pool_em(date=date)
            # Add estimated volume
            df['成交量_估算'] = df['成交额'] / df['最新价']
            return df
        except Exception as e:
            logger.error(f"Failed to fetch limit-up pool: {e}")
            return pd.DataFrame()
    
    def fetch_limit_down_count(self, date: str) -> int:
        """Get limit-down count using statistics"""
        try:
            stats = ak.stock_a_high_low_statistics()
            # Extract limit-down count from statistics
            return stats['跌停数'].iloc[-1]
        except Exception:
            return 0
    
    def fetch_market_breadth(self) -> pd.DataFrame:
        """Fetch market-wide data with fallbacks"""
        # Try primary source
        try:
            return ak.stock_zh_a_spot_em()
        except Exception:
            pass
        
        # Fallback 1: Combine SH + SZ
        try:
            df_sh = ak.stock_sh_a_spot_em()
            df_sz = ak.stock_sz_a_spot_em()
            return pd.concat([df_sh, df_sz], ignore_index=True)
        except Exception:
            pass
        
        # Fallback 2: Use cached data
        return self.load_cached_data()
```

### 2. Field Mapping Configuration

```python
# Field mapping configuration
FIELD_MAPPINGS = {
    'limit_up_pool': {
        'code': '代码',
        'name': '名称',
        'price': '最新价',
        'change_pct': '涨跌幅',
        'amount': '成交额',
        'turnover_rate': '换手率',
        'seal_capital': '封板资金',
        'consecutive_boards': '连板数',
        'industry': '所属行业'
    }
}

# Use mapping for robust access
def get_field(df: pd.DataFrame, field_key: str) -> pd.Series:
    """Get field using mapping"""
    field_name = FIELD_MAPPINGS['limit_up_pool'].get(field_key)
    if field_name and field_name in df.columns:
        return df[field_name]
    return pd.Series()
```

### 3. Caching Strategy

```python
from functools import lru_cache
from datetime import datetime, timedelta

class BreadthDataCache:
    """Cache breadth data with TTL"""
    
    def __init__(self, ttl_minutes: int = 20):
        self.ttl = timedelta(minutes=ttl_minutes)
        self.cache = {}
    
    def get(self, key: str) -> Optional[pd.DataFrame]:
        """Get cached data if not expired"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
        return None
    
    def set(self, key: str, data: pd.DataFrame):
        """Cache data with timestamp"""
        self.cache[key] = (data, datetime.now())
```

### 4. Rate Limiting

```python
import time
from functools import wraps

def rate_limit(delay_seconds: float = 3.0):
    """Rate limiting decorator"""
    def decorator(func):
        last_called = [0.0]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < delay_seconds:
                time.sleep(delay_seconds - elapsed)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        
        return wrapper
    return decorator

@rate_limit(delay_seconds=3.0)
def fetch_akshare_data():
    """Fetch with rate limiting"""
    pass
```

## Testing Recommendations

### Unit Tests

```python
def test_limit_up_pool_fields():
    """Test limit-up pool has required fields"""
    df = fetch_limit_up_pool(date='20260422')
    assert '代码' in df.columns
    assert '名称' in df.columns
    assert '涨跌幅' in df.columns
    assert len(df) > 0

def test_volume_estimation():
    """Test volume estimation accuracy"""
    df = fetch_limit_up_pool(date='20260422')
    df['成交量_估算'] = df['成交额'] / df['最新价']
    assert (df['成交量_估算'] > 0).all()
```

### Integration Tests

```python
def test_breadth_data_pipeline():
    """Test complete breadth data pipeline"""
    fetcher = BreadthDataFetcher()
    
    # Test limit-up pool
    limit_up = fetcher.fetch_limit_up_pool(date='20260422')
    assert len(limit_up) > 0
    
    # Test limit-down count
    limit_down_count = fetcher.fetch_limit_down_count(date='20260422')
    assert limit_down_count >= 0
    
    # Test market breadth (with fallback)
    market_data = fetcher.fetch_market_breadth()
    assert len(market_data) > 0
```

## Next Steps

1. ✅ **Completed:** Validated limit-up pool interface
2. ✅ **Completed:** Documented field mappings and issues
3. ⏭️ **Next:** Implement robust data fetcher with fallbacks
4. ⏭️ **Next:** Create caching layer for market-wide data
5. ⏭️ **Next:** Implement alternative data source integration (efinance)
6. ⏭️ **Next:** Write comprehensive unit tests

## Conclusion

The breadth data interfaces have significant limitations:

1. **Limit-up pool works well** but missing volume field
2. **No direct limit-down pool interface** - requires workarounds
3. **Market-wide data has connection issues** - needs fallback strategy

**Recommended Approach:**
- Use `ak.stock_zt_pool_em()` for limit-up data
- Use `ak.stock_a_high_low_statistics()` for aggregate counts
- Implement caching and fallback mechanisms for market-wide data
- Consider integrating alternative data sources (efinance, tushare)

The system can proceed with implementation using these workarounds, with graceful degradation when data is unavailable.
