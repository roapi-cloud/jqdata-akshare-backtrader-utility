# Sector Data Implementation Guide

**For:** Market Diagnostic System - Phase 1 Data Layer  
**Based on:** Task 0.3 Validation Results  
**Requirements:** 1.4, 6.1, 6.2

## Quick Reference

### Working Interfaces ✅

```python
import akshare as ak
from datetime import datetime, timedelta

# 1. Industry Historical Data (WORKING - 0.13s response)
df_hist = ak.stock_board_industry_hist_em(
    symbol='BK0447',  # Industry code
    period='日k',      # Daily K-line
    start_date='20260324',
    end_date='20260423',
    adjust=''
)
# Returns: 日期, 开盘, 收盘, 最高, 最低, 涨跌幅, 成交量, 成交额, 换手率

# 2. Industry Constituents (WORKING - 3.99s response)
df_cons = ak.stock_board_industry_cons_em(symbol='BK0447')
# Returns: 代码, 名称, 最新价, 涨跌幅, 成交额, 换手率, 市盈率-动态, 市净率
```

### Industry Codes (31 Shenwan Level-1)

```python
SHENWAN_L1_INDUSTRIES = {
    'BK0420': '农林牧渔', 'BK0427': '采掘', 'BK0428': '化工',
    'BK0429': '钢铁', 'BK0430': '有色金属', 'BK0431': '电子',
    'BK0432': '汽车', 'BK0433': '家用电器', 'BK0434': '食品饮料',
    'BK0435': '纺织服装', 'BK0436': '轻工制造', 'BK0437': '医药生物',
    'BK0438': '公用事业', 'BK0439': '交通运输', 'BK0440': '房地产',
    'BK0441': '商业贸易', 'BK0442': '休闲服务', 'BK0447': '通信',
    'BK0473': '银行', 'BK0474': '非银金融', 'BK0475': '综合',
    'BK0478': '建筑材料', 'BK0479': '建筑装饰', 'BK0481': '电气设备',
    'BK0482': '机械设备', 'BK0483': '国防军工', 'BK0484': '计算机',
    'BK0485': '传媒', 'BK0490': '环保', 'BK0732': '美容护理',
}
```

## Implementation Pattern

### Recommended Data Fetcher Structure

```python
# daily_stock_analysis/src/market_diagnostic/data/fetchers.py

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import akshare as ak

logger = logging.getLogger(__name__)

class SectorDataFetcher:
    """Fetches sector/industry data from AkShare"""
    
    SHENWAN_L1_INDUSTRIES = {
        'BK0420': '农林牧渔', 'BK0427': '采掘', 'BK0428': '化工',
        # ... (full list)
    }
    
    def __init__(self, rate_limit_delay: float = 3.0):
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()
    
    def fetch_industry_hist(
        self,
        industry_code: str,
        days: int = 30,
        max_retries: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a specific industry
        
        Args:
            industry_code: Industry code (e.g., 'BK0447')
            days: Number of days of historical data
            max_retries: Maximum retry attempts
            
        Returns:
            DataFrame with columns: 日期, 开盘, 收盘, 最高, 最低, 涨跌幅, 
                                   成交量, 成交额, 振幅, 换手率
        """
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                df = ak.stock_board_industry_hist_em(
                    symbol=industry_code,
                    period='日k',
                    start_date=start_date,
                    end_date=end_date,
                    adjust=''
                )
                
                if df is None or df.empty:
                    logger.warning(f"Empty data for industry {industry_code}")
                    return None
                
                # Validate required columns
                required_cols = ['日期', '收盘', '涨跌幅', '成交额']
                missing_cols = [c for c in required_cols if c not in df.columns]
                if missing_cols:
                    logger.error(f"Missing columns for {industry_code}: {missing_cols}")
                    return None
                
                logger.info(f"Fetched {len(df)} days for {industry_code}")
                return df
                
            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/{max_retries} failed for {industry_code}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.rate_limit_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch {industry_code} after {max_retries} attempts")
                    return None
    
    def fetch_industry_constituents(
        self,
        industry_code: str,
        max_retries: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        Fetch constituent stocks for a specific industry
        
        Args:
            industry_code: Industry code (e.g., 'BK0447')
            max_retries: Maximum retry attempts
            
        Returns:
            DataFrame with columns: 代码, 名称, 最新价, 涨跌幅, 成交额, 
                                   换手率, 市盈率-动态, 市净率
        """
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                df = ak.stock_board_industry_cons_em(symbol=industry_code)
                
                if df is None or df.empty:
                    logger.warning(f"Empty constituents for industry {industry_code}")
                    return None
                
                # Validate required columns
                required_cols = ['代码', '名称', '最新价', '涨跌幅']
                missing_cols = [c for c in required_cols if c not in df.columns]
                if missing_cols:
                    logger.error(f"Missing columns for {industry_code}: {missing_cols}")
                    return None
                
                logger.info(f"Fetched {len(df)} constituents for {industry_code}")
                return df
                
            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/{max_retries} failed for {industry_code}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.rate_limit_delay * (2 ** attempt))
                else:
                    logger.error(f"Failed to fetch constituents for {industry_code}")
                    return None
    
    def fetch_all_industries_hist(self, days: int = 30) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for all 31 Shenwan Level-1 industries
        
        Args:
            days: Number of days of historical data
            
        Returns:
            Dictionary mapping industry_code -> DataFrame
        """
        results = {}
        total = len(self.SHENWAN_L1_INDUSTRIES)
        
        logger.info(f"Fetching historical data for {total} industries...")
        
        for idx, (code, name) in enumerate(self.SHENWAN_L1_INDUSTRIES.items(), 1):
            logger.info(f"[{idx}/{total}] Fetching {name} ({code})...")
            df = self.fetch_industry_hist(code, days)
            if df is not None:
                results[code] = df
        
        success_rate = len(results) / total * 100
        logger.info(f"Fetched {len(results)}/{total} industries ({success_rate:.1f}%)")
        
        return results
    
    def fetch_all_industries_constituents(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch constituent stocks for all 31 Shenwan Level-1 industries
        
        Returns:
            Dictionary mapping industry_code -> DataFrame
        """
        results = {}
        total = len(self.SHENWAN_L1_INDUSTRIES)
        
        logger.info(f"Fetching constituents for {total} industries...")
        
        for idx, (code, name) in enumerate(self.SHENWAN_L1_INDUSTRIES.items(), 1):
            logger.info(f"[{idx}/{total}] Fetching {name} ({code})...")
            df = self.fetch_industry_constituents(code)
            if df is not None:
                results[code] = df
        
        success_rate = len(results) / total * 100
        logger.info(f"Fetched {len(results)}/{total} industries ({success_rate:.1f}%)")
        
        return results
```

## Data Model Mapping

### SectorDailyData Dataclass

```python
# daily_stock_analysis/src/market_diagnostic/data/models.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class SectorDailyData:
    """Daily data for a single industry sector"""
    date: str                    # Trading date (YYYY-MM-DD)
    industry_code: str           # Industry code (e.g., 'BK0447')
    industry_name: str           # Industry name (e.g., '通信')
    
    # Price data (from stock_board_industry_hist_em)
    close: float                 # 收盘
    open: float                  # 开盘
    high: float                  # 最高
    low: float                   # 最低
    
    # Returns (from stock_board_industry_hist_em)
    ret_1d: float                # 涨跌幅 (as decimal, e.g., 0.0145 for 1.45%)
    ret_5d: Optional[float]      # 5-day return (calculated)
    ret_20d: Optional[float]     # 20-day return (calculated)
    
    # Excess returns (calculated vs 沪深300)
    excess_ret_1d: Optional[float]
    excess_ret_5d: Optional[float]
    excess_ret_20d: Optional[float]
    
    # Volume/turnover (from stock_board_industry_hist_em)
    volume: float                # 成交量
    amount: float                # 成交额 (元)
    turnover_rate: float         # 换手率
    amplitude: float             # 振幅
    
    # Breadth metrics (calculated from constituents)
    breadth_20: Optional[float]  # Ratio of stocks above MA20
    new_high_ratio: Optional[float]  # Ratio of stocks at 20-day high
    
    # Market share (calculated)
    amount_share: Optional[float]      # Industry amount / Total market amount
    amount_share_delta: Optional[float]  # vs 5-day average
    
    # Sentiment (from constituents)
    limit_up_count: int          # Number of limit-up stocks in industry
    
    # Constituent count
    constituent_count: int       # Number of stocks in industry
```

### Field Mapping Reference

| SectorDailyData Field | AkShare Source | Column Name | Notes |
|----------------------|----------------|-------------|-------|
| close | stock_board_industry_hist_em | 收盘 | Direct mapping |
| open | stock_board_industry_hist_em | 开盘 | Direct mapping |
| high | stock_board_industry_hist_em | 最高 | Direct mapping |
| low | stock_board_industry_hist_em | 最低 | Direct mapping |
| ret_1d | stock_board_industry_hist_em | 涨跌幅 | Convert % to decimal |
| volume | stock_board_industry_hist_em | 成交量 | Direct mapping |
| amount | stock_board_industry_hist_em | 成交额 | In 元 (Yuan) |
| turnover_rate | stock_board_industry_hist_em | 换手率 | Convert % to decimal |
| amplitude | stock_board_industry_hist_em | 振幅 | Convert % to decimal |
| constituent_count | stock_board_industry_cons_em | len(df) | Count rows |
| breadth_20 | stock_board_industry_cons_em | Calculated | Requires MA20 calculation |

## Performance Considerations

### Timing Estimates

**Single Industry:**
- Historical data: ~0.2s
- Constituents: ~4.0s
- Total per industry: ~4.2s

**All 31 Industries:**
- With 3s rate limiting: ~3.5 minutes
- With 5s rate limiting: ~5.5 minutes

### Optimization Strategies

1. **Parallel Fetching (with rate limiting):**
   ```python
   from concurrent.futures import ThreadPoolExecutor
   import threading
   
   class RateLimitedExecutor:
       def __init__(self, max_workers=3, delay=3.0):
           self.executor = ThreadPoolExecutor(max_workers=max_workers)
           self.delay = delay
           self.lock = threading.Lock()
           self.last_request = 0
       
       def submit(self, fn, *args, **kwargs):
           def rate_limited_fn():
               with self.lock:
                   elapsed = time.time() - self.last_request
                   if elapsed < self.delay:
                       time.sleep(self.delay - elapsed)
                   self.last_request = time.time()
               return fn(*args, **kwargs)
           
           return self.executor.submit(rate_limited_fn)
   ```

2. **Caching Strategy:**
   ```python
   import pickle
   from pathlib import Path
   
   def cache_sector_data(data: Dict, date: str, cache_dir: str = '.cache'):
       """Cache sector data for a specific date"""
       cache_path = Path(cache_dir) / f"sector_data_{date}.pkl"
       cache_path.parent.mkdir(exist_ok=True)
       with open(cache_path, 'wb') as f:
           pickle.dump(data, f)
   
   def load_cached_sector_data(date: str, cache_dir: str = '.cache') -> Optional[Dict]:
       """Load cached sector data if available"""
       cache_path = Path(cache_dir) / f"sector_data_{date}.pkl"
       if cache_path.exists():
           with open(cache_path, 'rb') as f:
               return pickle.load(f)
       return None
   ```

3. **Incremental Updates:**
   - Cache full historical data (60 days)
   - Daily: Only fetch latest day's data
   - Append to cached data
   - Reduces API calls by 95%

## Error Handling

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `HTTPSConnectionPool ... Max retries exceeded` | Network/proxy issue | Retry with exponential backoff |
| `Expecting value: line 1 column 1` | Empty response | Skip and log, continue processing |
| `Length mismatch` | API format change | Update field mapping |
| Empty DataFrame | Invalid industry code | Validate code against SHENWAN_L1_INDUSTRIES |

### Graceful Degradation

```python
def fetch_sector_data_with_fallback(date: str) -> Dict[str, SectorDailyData]:
    """Fetch sector data with graceful degradation"""
    
    # Try cache first
    cached = load_cached_sector_data(date)
    if cached:
        logger.info(f"Using cached data for {date}")
        return cached
    
    # Fetch fresh data
    fetcher = SectorDataFetcher()
    results = {}
    missing_data = []
    
    for code, name in fetcher.SHENWAN_L1_INDUSTRIES.items():
        try:
            hist_df = fetcher.fetch_industry_hist(code, days=30)
            cons_df = fetcher.fetch_industry_constituents(code)
            
            if hist_df is not None and cons_df is not None:
                # Convert to SectorDailyData
                sector_data = convert_to_sector_daily_data(
                    code, name, date, hist_df, cons_df
                )
                results[code] = sector_data
            else:
                missing_data.append(f"{name}({code})")
                
        except Exception as e:
            logger.error(f"Failed to process {name}({code}): {e}")
            missing_data.append(f"{name}({code})")
    
    # Log missing data
    if missing_data:
        logger.warning(f"Missing data for {len(missing_data)} industries: {missing_data}")
    
    # Cache results
    if results:
        cache_sector_data(results, date)
    
    return results
```

## Testing

### Unit Test Example

```python
# tests/test_sector_data_fetcher.py

import pytest
from src.market_diagnostic.data.fetchers import SectorDataFetcher

def test_fetch_industry_hist():
    """Test fetching industry historical data"""
    fetcher = SectorDataFetcher(rate_limit_delay=1.0)  # Faster for testing
    
    df = fetcher.fetch_industry_hist('BK0447', days=30)
    
    assert df is not None
    assert len(df) >= 20  # At least 20 trading days
    assert '日期' in df.columns
    assert '收盘' in df.columns
    assert '涨跌幅' in df.columns
    assert '成交额' in df.columns

def test_fetch_industry_constituents():
    """Test fetching industry constituents"""
    fetcher = SectorDataFetcher(rate_limit_delay=1.0)
    
    df = fetcher.fetch_industry_constituents('BK0447')
    
    assert df is not None
    assert len(df) >= 10  # At least 10 constituent stocks
    assert '代码' in df.columns
    assert '名称' in df.columns
    assert '涨跌幅' in df.columns

def test_invalid_industry_code():
    """Test handling of invalid industry code"""
    fetcher = SectorDataFetcher(rate_limit_delay=1.0)
    
    df = fetcher.fetch_industry_hist('INVALID_CODE')
    
    assert df is None  # Should return None for invalid code
```

## Next Steps

1. ✅ **Task 0.3 Complete** - Sector interfaces validated
2. ⏭️ **Task 0.4** - Validate valuation and macro data interfaces
3. ⏭️ **Task 2.1** - Implement DiagnosticDataFetcher with sector support
4. ⏭️ **Task 6.1** - Implement sector feature calculations

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-23  
**Status:** Ready for Phase 1 Implementation
