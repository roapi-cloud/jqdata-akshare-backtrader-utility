#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Task 2.1.2: Verify AkShare interfaces for sector data

This script specifically tests the three sector data interfaces:
1. ak.stock_board_industry_hist_em() - industry historical data
2. ak.stock_board_industry_cons_em() - industry constituents  
3. ak.stock_sector_fund_flow_rank() - industry capital flow

Requirements: 1.4, 1.6
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_industry_historical_data():
    """
    Test ak.stock_board_industry_hist_em() for industry historical data
    
    Validates:
    - Return format and field mappings
    - Data availability for sample industries
    - Historical data depth (need 20+ days for calculations)
    """
    logger.info("=" * 80)
    logger.info("Testing ak.stock_board_industry_hist_em()")
    logger.info("=" * 80)
    
    # Sample Shenwan Level-1 industries
    sample_industries = [
        ('BK0447', '通信'),
        ('BK0437', '医药生物'),
        ('BK0432', '汽车'),
    ]
    
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    
    results = []
    
    for code, name in sample_industries:
        try:
            logger.info(f"\nTesting industry: {name} ({code})")
            
            start_time = time.time()
            df = ak.stock_board_industry_hist_em(
                symbol=code,
                period='日k',
                start_date=start_date,
                end_date=end_date,
                adjust=''
            )
            elapsed = time.time() - start_time
            
            if df is None or df.empty:
                logger.warning(f"  ❌ No data returned for {name}")
                results.append({
                    'industry': name,
                    'code': code,
                    'success': False,
                    'error': 'Empty DataFrame'
                })
                continue
            
            # Document return format
            logger.info(f"  ✅ Success - {len(df)} rows in {elapsed:.2f}s")
            logger.info(f"  Columns: {list(df.columns)}")
            logger.info(f"  Data types: {df.dtypes.to_dict()}")
            
            # Check for required fields
            required_fields = ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '涨跌幅']
            missing_fields = [f for f in required_fields if f not in df.columns]
            
            if missing_fields:
                logger.warning(f"  ⚠️  Missing fields: {missing_fields}")
            
            # Show sample data
            logger.info(f"\n  Sample data (first 3 rows):")
            print(df.head(3).to_string(index=False))
            
            # Validate data quality
            issues = []
            if len(df) < 20:
                issues.append(f"Insufficient historical data: {len(df)} days (need 20+)")
            
            null_counts = df.isnull().sum()
            high_null_cols = null_counts[null_counts > len(df) * 0.3].index.tolist()
            if high_null_cols:
                issues.append(f"High null rate in columns: {high_null_cols}")
            
            if issues:
                logger.warning(f"  ⚠️  Data quality issues: {'; '.join(issues)}")
            
            results.append({
                'industry': name,
                'code': code,
                'success': True,
                'rows': len(df),
                'columns': list(df.columns),
                'response_time': elapsed,
                'issues': issues
            })
            
            # Rate limiting
            time.sleep(3)
            
        except Exception as e:
            logger.error(f"  ❌ Error for {name}: {e}")
            results.append({
                'industry': name,
                'code': code,
                'success': False,
                'error': str(e)
            })
    
    return results


def test_industry_constituents():
    """
    Test ak.stock_board_industry_cons_em() for industry constituents
    
    Validates:
    - Return format and field mappings
    - Constituent count (should have 10+ stocks per industry)
    - Field availability for breadth calculations
    """
    logger.info("\n" + "=" * 80)
    logger.info("Testing ak.stock_board_industry_cons_em()")
    logger.info("=" * 80)
    
    sample_industries = [
        ('BK0447', '通信'),
        ('BK0437', '医药生物'),
        ('BK0432', '汽车'),
    ]
    
    results = []
    
    for code, name in sample_industries:
        try:
            logger.info(f"\nTesting industry: {name} ({code})")
            
            start_time = time.time()
            df = ak.stock_board_industry_cons_em(symbol=code)
            elapsed = time.time() - start_time
            
            if df is None or df.empty:
                logger.warning(f"  ❌ No data returned for {name}")
                results.append({
                    'industry': name,
                    'code': code,
                    'success': False,
                    'error': 'Empty DataFrame'
                })
                continue
            
            # Document return format
            logger.info(f"  ✅ Success - {len(df)} constituents in {elapsed:.2f}s")
            logger.info(f"  Columns: {list(df.columns)}")
            logger.info(f"  Data types: {df.dtypes.to_dict()}")
            
            # Check for required fields
            required_fields = ['代码', '名称', '最新价', '涨跌幅']
            missing_fields = [f for f in required_fields if f not in df.columns]
            
            if missing_fields:
                logger.warning(f"  ⚠️  Missing fields: {missing_fields}")
            
            # Show sample data
            logger.info(f"\n  Sample data (first 5 constituents):")
            print(df.head(5).to_string(index=False))
            
            # Validate data quality
            issues = []
            if len(df) < 10:
                issues.append(f"Low constituent count: {len(df)} stocks (expected 10+)")
            
            # Check for fields needed for breadth calculations
            breadth_fields = ['涨跌幅', '最新价', '成交量', '成交额']
            available_breadth_fields = [f for f in breadth_fields if f in df.columns]
            logger.info(f"  Available breadth calculation fields: {available_breadth_fields}")
            
            if issues:
                logger.warning(f"  ⚠️  Data quality issues: {'; '.join(issues)}")
            
            results.append({
                'industry': name,
                'code': code,
                'success': True,
                'constituent_count': len(df),
                'columns': list(df.columns),
                'response_time': elapsed,
                'issues': issues
            })
            
            # Rate limiting
            time.sleep(3)
            
        except Exception as e:
            logger.error(f"  ❌ Error for {name}: {e}")
            results.append({
                'industry': name,
                'code': code,
                'success': False,
                'error': str(e)
            })
    
    return results


def test_industry_capital_flow():
    """
    Test ak.stock_sector_fund_flow_rank() for industry capital flow
    
    Validates:
    - Return format and field mappings
    - Coverage of all industries
    - Capital flow metrics availability
    """
    logger.info("\n" + "=" * 80)
    logger.info("Testing ak.stock_sector_fund_flow_rank()")
    logger.info("=" * 80)
    
    indicators = ['今日', '3日', '5日', '10日']
    results = []
    
    for indicator in indicators:
        try:
            logger.info(f"\nTesting indicator: {indicator}")
            
            start_time = time.time()
            df = ak.stock_sector_fund_flow_rank(indicator=indicator)
            elapsed = time.time() - start_time
            
            if df is None or df.empty:
                logger.warning(f"  ❌ No data returned for {indicator}")
                results.append({
                    'indicator': indicator,
                    'success': False,
                    'error': 'Empty DataFrame'
                })
                continue
            
            # Document return format
            logger.info(f"  ✅ Success - {len(df)} industries in {elapsed:.2f}s")
            logger.info(f"  Columns: {list(df.columns)}")
            logger.info(f"  Data types: {df.dtypes.to_dict()}")
            
            # Check for required fields
            required_fields = ['名称', '涨跌幅', '主力净流入-净额', '主力净流入-净占比']
            missing_fields = [f for f in required_fields if f not in df.columns]
            
            if missing_fields:
                logger.warning(f"  ⚠️  Missing fields: {missing_fields}")
            
            # Show sample data
            logger.info(f"\n  Sample data (top 5 industries by capital flow):")
            print(df.head(5).to_string(index=False))
            
            # Validate data quality
            issues = []
            if len(df) < 30:
                issues.append(f"Low industry count: {len(df)} (expected 30+ for Shenwan Level-1)")
            
            # Check for capital flow fields
            capital_fields = [col for col in df.columns if '净流入' in col or '资金' in col]
            logger.info(f"  Available capital flow fields: {capital_fields}")
            
            if issues:
                logger.warning(f"  ⚠️  Data quality issues: {'; '.join(issues)}")
            
            results.append({
                'indicator': indicator,
                'success': True,
                'industry_count': len(df),
                'columns': list(df.columns),
                'response_time': elapsed,
                'issues': issues
            })
            
            # Rate limiting
            time.sleep(3)
            
        except Exception as e:
            logger.error(f"  ❌ Error for {indicator}: {e}")
            results.append({
                'indicator': indicator,
                'success': False,
                'error': str(e)
            })
    
    return results


def generate_field_mapping_doc(hist_results, cons_results, flow_results):
    """Generate field mapping documentation"""
    logger.info("\n" + "=" * 80)
    logger.info("FIELD MAPPINGS DOCUMENTATION")
    logger.info("=" * 80)
    
    doc = []
    doc.append("\n## Sector Data Field Mappings\n")
    
    # Historical data fields
    doc.append("### 1. ak.stock_board_industry_hist_em() - Industry Historical Data\n")
    doc.append("**Purpose:** Fetch historical OHLCV data for industry indices\n")
    doc.append("**Parameters:**")
    doc.append("- symbol: Industry code (e.g., 'BK0447')")
    doc.append("- period: '日k' (daily), '周k' (weekly), '月k' (monthly)")
    doc.append("- start_date: Start date in 'YYYYMMDD' format")
    doc.append("- end_date: End date in 'YYYYMMDD' format")
    doc.append("- adjust: '' (no adjust), 'qfq' (forward), 'hfq' (backward)\n")
    
    if hist_results and hist_results[0]['success']:
        doc.append("**Return Fields:**")
        for col in hist_results[0]['columns']:
            doc.append(f"- {col}")
        doc.append(f"\n**Typical Row Count:** {hist_results[0]['rows']} days")
        doc.append(f"**Response Time:** ~{hist_results[0]['response_time']:.2f}s\n")
    
    # Constituents fields
    doc.append("### 2. ak.stock_board_industry_cons_em() - Industry Constituents\n")
    doc.append("**Purpose:** Fetch list of stocks in an industry\n")
    doc.append("**Parameters:**")
    doc.append("- symbol: Industry code (e.g., 'BK0447')\n")
    
    if cons_results and cons_results[0]['success']:
        doc.append("**Return Fields:**")
        for col in cons_results[0]['columns']:
            doc.append(f"- {col}")
        doc.append(f"\n**Typical Constituent Count:** {cons_results[0]['constituent_count']} stocks")
        doc.append(f"**Response Time:** ~{cons_results[0]['response_time']:.2f}s\n")
    
    # Capital flow fields
    doc.append("### 3. ak.stock_sector_fund_flow_rank() - Industry Capital Flow\n")
    doc.append("**Purpose:** Fetch capital flow rankings for all industries\n")
    doc.append("**Parameters:**")
    doc.append("- indicator: '今日', '3日', '5日', '10日'\n")
    
    if flow_results and flow_results[0]['success']:
        doc.append("**Return Fields:**")
        for col in flow_results[0]['columns']:
            doc.append(f"- {col}")
        doc.append(f"\n**Industry Count:** {flow_results[0]['industry_count']} industries")
        doc.append(f"**Response Time:** ~{flow_results[0]['response_time']:.2f}s\n")
    
    doc.append("\n## Usage Recommendations\n")
    doc.append("1. **Rate Limiting:** Use 3-5 second delays between requests")
    doc.append("2. **Caching:** Cache historical data (daily refresh)")
    doc.append("3. **Error Handling:** Implement retry logic with exponential backoff")
    doc.append("4. **Data Validation:** Check for null values and outliers")
    doc.append("5. **Batch Processing:** Process all 31 Shenwan industries sequentially with delays\n")
    
    doc_text = '\n'.join(doc)
    print(doc_text)
    
    return doc_text


def main():
    """Main test workflow for Task 2.1.2"""
    logger.info("=" * 80)
    logger.info("Task 2.1.2: Verify AkShare Interfaces for Sector Data")
    logger.info("Requirements: 1.4, 1.6")
    logger.info("=" * 80)
    
    try:
        # Test 1: Industry historical data
        hist_results = test_industry_historical_data()
        
        # Test 2: Industry constituents
        cons_results = test_industry_constituents()
        
        # Test 3: Industry capital flow
        flow_results = test_industry_capital_flow()
        
        # Generate field mapping documentation
        field_doc = generate_field_mapping_doc(hist_results, cons_results, flow_results)
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("TASK 2.1.2 SUMMARY")
        logger.info("=" * 80)
        
        hist_success = sum(1 for r in hist_results if r.get('success', False))
        cons_success = sum(1 for r in cons_results if r.get('success', False))
        flow_success = sum(1 for r in flow_results if r.get('success', False))
        
        logger.info(f"\n✅ Industry Historical Data: {hist_success}/{len(hist_results)} tests passed")
        logger.info(f"✅ Industry Constituents: {cons_success}/{len(cons_results)} tests passed")
        logger.info(f"✅ Industry Capital Flow: {flow_success}/{len(flow_results)} tests passed")
        
        total_tests = len(hist_results) + len(cons_results) + len(flow_results)
        total_success = hist_success + cons_success + flow_success
        
        logger.info(f"\n📊 Overall: {total_success}/{total_tests} tests passed ({total_success/total_tests*100:.1f}%)")
        
        # Save field mapping documentation
        doc_path = "docs/sector_data_field_mappings.md"
        os.makedirs("docs", exist_ok=True)
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(field_doc)
        logger.info(f"\n📄 Field mapping documentation saved to: {doc_path}")
        
        return 0 if total_success == total_tests else 1
        
    except Exception as e:
        logger.error(f"Task 2.1.2 failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
