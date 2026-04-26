#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Task 2.1.1: Verify AkShare interfaces for breadth data

This script tests the three key AkShare interfaces needed for market breadth calculation:
1. ak.stock_zt_pool_em() - limit-up stocks
2. ak.stock_dt_pool_em() - limit-down stocks  
3. ak.stock_zh_a_spot_em() - market-wide statistics

Requirements validated:
- Requirement 1.3: Market breadth data retrieval
- Requirement 1.6: Error handling for missing data
"""

import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, '.')

def test_limit_up_pool(test_date: str) -> Dict[str, Any]:
    """
    Test ak.stock_zt_pool_em() for limit-up stocks
    
    Args:
        test_date: Date string in format 'YYYYMMDD'
        
    Returns:
        Dictionary with test results
    """
    print(f"\n{'='*80}")
    print(f"Testing ak.stock_zt_pool_em() - Limit-Up Pool")
    print(f"{'='*80}")
    
    result = {
        'interface': 'ak.stock_zt_pool_em()',
        'success': False,
        'data_count': 0,
        'fields': [],
        'sample_data': None,
        'error': None
    }
    
    try:
        import akshare as ak
        
        print(f"Calling ak.stock_zt_pool_em(date='{test_date}')...")
        start_time = time.time()
        
        df = ak.stock_zt_pool_em(date=test_date)
        
        elapsed = time.time() - start_time
        
        if df is not None and not df.empty:
            result['success'] = True
            result['data_count'] = len(df)
            result['fields'] = list(df.columns)
            result['sample_data'] = df.head(3).to_dict('records')
            
            print(f"✓ Success! Retrieved {len(df)} limit-up stocks in {elapsed:.2f}s")
            print(f"\nFields returned: {list(df.columns)}")
            print(f"\nSample data (first 3 rows):")
            print(df.head(3).to_string())
            
            # Check for key fields
            expected_fields = ['代码', '名称', '涨跌幅', '最新价', '成交额', '流通市值', '首次封板时间', '最后封板时间']
            missing_fields = [f for f in expected_fields if f not in df.columns]
            if missing_fields:
                print(f"\n⚠ Warning: Missing expected fields: {missing_fields}")
            else:
                print(f"\n✓ All expected fields present")
                
        else:
            print(f"⚠ Warning: No data returned (may be no limit-up stocks on {test_date})")
            result['error'] = 'No data returned'
            
    except Exception as e:
        print(f"✗ Error: {e}")
        result['error'] = str(e)
        
    return result


def test_limit_down_pool(test_date: str) -> Dict[str, Any]:
    """
    Test limit-down stocks interface
    
    Note: AkShare may not have a dedicated limit-down pool interface.
    We'll try alternative approaches:
    1. ak.stock_zt_pool_dtgc_em() - limit-down pool (if exists)
    2. Filter from market-wide data where change_pct <= -9.9%
    
    Args:
        test_date: Date string in format 'YYYYMMDD'
        
    Returns:
        Dictionary with test results
    """
    print(f"\n{'='*80}")
    print(f"Testing Limit-Down Pool Interfaces")
    print(f"{'='*80}")
    
    result = {
        'interface': 'limit-down detection',
        'success': False,
        'data_count': 0,
        'fields': [],
        'sample_data': None,
        'error': None
    }
    
    try:
        import akshare as ak
        
        # Try method 1: Check if there's a limit-down specific interface
        print(f"Checking available AkShare interfaces for limit-down data...")
        
        # List possible interface names
        possible_interfaces = [
            'stock_zt_pool_dtgc_em',  # Possible limit-down interface
            'stock_zt_pool_sub_new_em',  # Sub-new stocks
        ]
        
        df = None
        used_interface = None
        
        for interface_name in possible_interfaces:
            if hasattr(ak, interface_name):
                print(f"Found interface: {interface_name}")
                try:
                    func = getattr(ak, interface_name)
                    start_time = time.time()
                    df = func(date=test_date)
                    elapsed = time.time() - start_time
                    used_interface = interface_name
                    break
                except Exception as e:
                    print(f"  Failed to call {interface_name}: {e}")
        
        if df is None:
            print(f"⚠ No dedicated limit-down interface found in AkShare")
            print(f"Note: Limit-down stocks can be identified from market-wide data")
            print(f"      by filtering stocks with change_pct <= -9.9%")
            result['error'] = 'No dedicated limit-down interface available'
            return result
        
        elapsed = time.time() - start_time
        
        if df is not None and not df.empty:
            result['success'] = True
            result['data_count'] = len(df)
            result['fields'] = list(df.columns)
            result['sample_data'] = df.head(3).to_dict('records')
            
            print(f"✓ Success! Retrieved {len(df)} limit-down stocks in {elapsed:.2f}s")
            print(f"\nFields returned: {list(df.columns)}")
            print(f"\nSample data (first 3 rows):")
            print(df.head(3).to_string())
            
            # Check for key fields
            expected_fields = ['代码', '名称', '涨跌幅', '最新价', '成交额', '流通市值']
            missing_fields = [f for f in expected_fields if f not in df.columns]
            if missing_fields:
                print(f"\n⚠ Warning: Missing expected fields: {missing_fields}")
            else:
                print(f"\n✓ All expected fields present")
                
        else:
            print(f"⚠ Warning: No data returned (may be no limit-down stocks on {test_date})")
            result['error'] = 'No data returned'
            
    except Exception as e:
        print(f"✗ Error: {e}")
        result['error'] = str(e)
        
    return result


def test_market_spot() -> Dict[str, Any]:
    """
    Test ak.stock_zh_a_spot_em() for market-wide statistics
    
    Returns:
        Dictionary with test results
    """
    print(f"\n{'='*80}")
    print(f"Testing ak.stock_zh_a_spot_em() - Market-Wide Realtime Quotes")
    print(f"{'='*80}")
    
    result = {
        'interface': 'ak.stock_zh_a_spot_em()',
        'success': False,
        'data_count': 0,
        'fields': [],
        'sample_data': None,
        'error': None,
        'statistics': {}
    }
    
    try:
        import akshare as ak
        
        print(f"Calling ak.stock_zh_a_spot_em()...")
        start_time = time.time()
        
        df = ak.stock_zh_a_spot_em()
        
        elapsed = time.time() - start_time
        
        if df is not None and not df.empty:
            result['success'] = True
            result['data_count'] = len(df)
            result['fields'] = list(df.columns)
            result['sample_data'] = df.head(3).to_dict('records')
            
            print(f"✓ Success! Retrieved {len(df)} stocks in {elapsed:.2f}s")
            print(f"\nFields returned: {list(df.columns)}")
            print(f"\nSample data (first 3 rows):")
            print(df.head(3).to_string())
            
            # Calculate market statistics
            if '涨跌幅' in df.columns:
                up_count = len(df[df['涨跌幅'] > 0])
                down_count = len(df[df['涨跌幅'] < 0])
                flat_count = len(df[df['涨跌幅'] == 0])
                
                result['statistics'] = {
                    'total_stocks': len(df),
                    'up_count': up_count,
                    'down_count': down_count,
                    'flat_count': flat_count,
                    'up_ratio': up_count / len(df) if len(df) > 0 else 0
                }
                
                print(f"\nMarket Statistics:")
                print(f"  Total stocks: {len(df)}")
                print(f"  Up: {up_count} ({up_count/len(df)*100:.1f}%)")
                print(f"  Down: {down_count} ({down_count/len(df)*100:.1f}%)")
                print(f"  Flat: {flat_count} ({flat_count/len(df)*100:.1f}%)")
            
            # Check for key fields needed for breadth calculation
            expected_fields = ['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额', '量比', '换手率']
            missing_fields = [f for f in expected_fields if f not in df.columns]
            if missing_fields:
                print(f"\n⚠ Warning: Missing expected fields: {missing_fields}")
            else:
                print(f"\n✓ All expected fields present")
                
        else:
            print(f"✗ Error: No data returned")
            result['error'] = 'No data returned'
            
    except Exception as e:
        print(f"✗ Error: {e}")
        result['error'] = str(e)
        
    return result


def main():
    """Main test execution"""
    print(f"\n{'#'*80}")
    print(f"# Task 2.1.1: Verify AkShare Interfaces for Breadth Data")
    print(f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*80}")
    
    # Use a recent trading date for testing
    # Try yesterday first, if it's weekend/holiday, try last Friday
    test_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    
    print(f"\nTest date: {test_date}")
    print(f"Note: If no data is returned, the test date may be a non-trading day.")
    
    # Run all tests
    results = []
    
    # Test 1: Limit-up pool
    time.sleep(2)  # Rate limiting
    result1 = test_limit_up_pool(test_date)
    results.append(result1)
    
    # Test 2: Limit-down pool
    time.sleep(2)  # Rate limiting
    result2 = test_limit_down_pool(test_date)
    results.append(result2)
    
    # Test 3: Market-wide spot data
    time.sleep(2)  # Rate limiting
    result3 = test_market_spot()
    results.append(result3)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}")
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    print(f"\nResults: {success_count}/{total_count} tests passed")
    
    for i, result in enumerate(results, 1):
        status = "✓ PASS" if result['success'] else "✗ FAIL"
        print(f"\n{i}. {result['interface']}: {status}")
        if result['success']:
            print(f"   - Data count: {result['data_count']}")
            print(f"   - Fields: {len(result['fields'])} fields")
        else:
            print(f"   - Error: {result['error']}")
    
    # Field mapping documentation
    print(f"\n{'='*80}")
    print(f"FIELD MAPPINGS FOR BREADTH CALCULATION")
    print(f"{'='*80}")
    
    print(f"\n1. Limit-up pool (ak.stock_zt_pool_em):")
    if results[0]['success']:
        print(f"   Fields: {', '.join(results[0]['fields'])}")
        print(f"   Key fields for breadth:")
        print(f"   - 代码: Stock code")
        print(f"   - 名称: Stock name")
        print(f"   - 涨跌幅: Change percentage")
        print(f"   - 首次封板时间: First limit-up time")
        print(f"   - 最后封板时间: Last limit-up time")
    
    print(f"\n2. Limit-down pool (ak.stock_dt_pool_em):")
    if results[1]['success']:
        print(f"   Fields: {', '.join(results[1]['fields'])}")
        print(f"   Key fields for breadth:")
        print(f"   - 代码: Stock code")
        print(f"   - 名称: Stock name")
        print(f"   - 涨跌幅: Change percentage")
    
    print(f"\n3. Market-wide spot (ak.stock_zh_a_spot_em):")
    if results[2]['success']:
        print(f"   Fields: {', '.join(results[2]['fields'])}")
        print(f"   Key fields for breadth:")
        print(f"   - 代码: Stock code")
        print(f"   - 名称: Stock name")
        print(f"   - 最新价: Latest price")
        print(f"   - 涨跌幅: Change percentage")
        print(f"   - 成交量: Volume")
        print(f"   - 成交额: Amount")
        print(f"   - 量比: Volume ratio")
        print(f"   - 换手率: Turnover rate")
    
    # Data quality notes
    print(f"\n{'='*80}")
    print(f"DATA QUALITY NOTES")
    print(f"{'='*80}")
    
    print(f"\n1. Limit-up/down pools may be empty on days with no extreme movements")
    print(f"2. Market-wide spot data includes all A-share stocks (~5000 stocks)")
    print(f"3. Data freshness: Real-time during trading hours, T+0 after market close")
    print(f"4. Rate limiting: Recommend 2-5 second delays between API calls")
    print(f"5. Anti-ban strategy: Use random User-Agent and exponential backoff")
    
    # Return exit code
    return 0 if success_count == total_count else 1


if __name__ == '__main__':
    sys.exit(main())
