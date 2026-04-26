# Breadth Data Interface Validation Report

**Generated:** 2026-04-23 17:06:18

## Summary

- **Total Tests:** 3
- **Successful:** 1
- **Failed:** 2
- **Success Rate:** 33.3%

## Test Results

| Interface | Status | Rows | Columns | Response Time | Issues |
|-----------|--------|------|---------|---------------|--------|
| `ak.stock_zt_pool_em()` | ✅ SUCCESS | 55 | 16 | 0.07s | Missing expected fields: ['成交量']; Outlier detec... |
| `ak.stock_dt_pool_em()` | ❌ FAILED | 0 | 0 | 0.00s | module 'akshare' has no attribute 'stock_dt_poo... |
| `ak.stock_zh_a_spot_em()` | ❌ FAILED | 0 | 0 | 0.00s | HTTPSConnectionPool(host='82.push2.eastmoney.co... |

## Field Mappings

### limit_up_pool

```python
columns = ['序号', '代码', '名称', '涨跌幅', '最新价', '成交额', '流通市值', '总市值', '换手率', '封板资金', '首次封板时间', '最后封板时间', '炸板次数', '涨停统计', '连板数', '所属行业']
```

## Data Quality Issues

### LOW Severity
- **limit_up_pool**: Outlier detected in 涨跌幅: [9.95%, 30.00%]

## Recommendations

### Workaround for ak.stock_zh_a_spot_em()
- **Issue**: Proxy connection errors
- **Workaround 1**: Use limit-up/down pools + individual stock queries
- **Workaround 2**: Implement caching layer with daily refresh
- **Workaround 3**: Use alternative data source (e.g., tushare, efinance)
- **Workaround 4**: Retry with exponential backoff (3 attempts)

### Rate Limiting
- **Recommended delay**: 3-5 seconds between requests
- **Batch processing**: Cache results for same trading day
- **Peak hours**: Avoid 9:30-10:00 and 14:30-15:00

### Data Quality
- **Missing values**: Implement fallback to previous day's data
- **Outliers**: Validate extreme values (>20% change) manually
- **Field mapping**: Use column name mapping for robustness