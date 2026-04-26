
## Sector Data Field Mappings

### 1. ak.stock_board_industry_hist_em() - Industry Historical Data

**Purpose:** Fetch historical OHLCV data for industry indices

**Parameters:**
- symbol: Industry code (e.g., 'BK0447')
- period: '日k' (daily), '周k' (weekly), '月k' (monthly)
- start_date: Start date in 'YYYYMMDD' format
- end_date: End date in 'YYYYMMDD' format
- adjust: '' (no adjust), 'qfq' (forward), 'hfq' (backward)

### 2. ak.stock_board_industry_cons_em() - Industry Constituents

**Purpose:** Fetch list of stocks in an industry

**Parameters:**
- symbol: Industry code (e.g., 'BK0447')

### 3. ak.stock_sector_fund_flow_rank() - Industry Capital Flow

**Purpose:** Fetch capital flow rankings for all industries

**Parameters:**
- indicator: '今日', '3日', '5日', '10日'


## Usage Recommendations

1. **Rate Limiting:** Use 3-5 second delays between requests
2. **Caching:** Cache historical data (daily refresh)
3. **Error Handling:** Implement retry logic with exponential backoff
4. **Data Validation:** Check for null values and outliers
5. **Batch Processing:** Process all 31 Shenwan industries sequentially with delays
