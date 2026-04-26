#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test all 31 Shenwan Level-1 Industries

This script tests data availability for all 31 Shenwan Level-1 industries
using hardcoded industry codes.
"""

import time
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd

# Shenwan Level-1 Industry Codes (31 industries)
SHENWAN_L1_INDUSTRIES = {
    'BK0420': '农林牧渔',
    'BK0427': '采掘',
    'BK0428': '化工',
    'BK0429': '钢铁',
    'BK0430': '有色金属',
    'BK0431': '电子',
    'BK0432': '汽车',
    'BK0433': '家用电器',
    'BK0434': '食品饮料',
    'BK0435': '纺织服装',
    'BK0436': '轻工制造',
    'BK0437': '医药生物',
    'BK0438': '公用事业',
    'BK0439': '交通运输',
    'BK0440': '房地产',
    'BK0441': '商业贸易',
    'BK0442': '休闲服务',
    'BK0447': '通信',
    'BK0473': '银行',
    'BK0474': '非银金融',
    'BK0475': '综合',
    'BK0478': '建筑材料',
    'BK0479': '建筑装饰',
    'BK0481': '电气设备',
    'BK0482': '机械设备',
    'BK0483': '国防军工',
    'BK0484': '计算机',
    'BK0485': '传媒',
    'BK0486': '通信',  # Duplicate? Check
    'BK0490': '环保',
    'BK0732': '美容护理',
}

def test_industry_data(code, name, delay=3):
    """Test historical data and constituents for one industry"""
    result = {
        'code': code,
        'name': name,
        'hist_success': False,
        'hist_days': 0,
        'hist_error': None,
        'cons_success': False,
        'cons_count': 0,
        'cons_error': None,
    }
    
    # Test historical data
    try:
        time.sleep(delay)
        df_hist = ak.stock_board_industry_hist_em(
            symbol=code,
            period='日k',
            start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust=''
        )
        result['hist_success'] = True
        result['hist_days'] = len(df_hist)
    except Exception as e:
        result['hist_error'] = str(e)[:100]
    
    # Test constituents
    try:
        time.sleep(delay)
        df_cons = ak.stock_board_industry_cons_em(symbol=code)
        result['cons_success'] = True
        result['cons_count'] = len(df_cons)
    except Exception as e:
        result['cons_error'] = str(e)[:100]
    
    return result

def main():
    """Test all 31 Shenwan Level-1 industries"""
    print("="*80)
    print("Testing All 31 Shenwan Level-1 Industries")
    print("="*80)
    print(f"\nTotal industries to test: {len(SHENWAN_L1_INDUSTRIES)}")
    print("Delay between requests: 3 seconds")
    print(f"Estimated time: ~{len(SHENWAN_L1_INDUSTRIES) * 6 / 60:.1f} minutes")
    print("\nStarting tests...\n")
    
    results = []
    start_time = time.time()
    
    for idx, (code, name) in enumerate(SHENWAN_L1_INDUSTRIES.items(), 1):
        print(f"[{idx}/{len(SHENWAN_L1_INDUSTRIES)}] Testing {name} ({code})...")
        result = test_industry_data(code, name)
        results.append(result)
        
        # Print status
        hist_status = f"✅ {result['hist_days']} days" if result['hist_success'] else f"❌ {result['hist_error'][:30]}"
        cons_status = f"✅ {result['cons_count']} stocks" if result['cons_success'] else f"❌ {result['cons_error'][:30]}"
        print(f"  Historical: {hist_status}")
        print(f"  Constituents: {cons_status}")
    
    elapsed = time.time() - start_time
    
    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    
    hist_success = sum(1 for r in results if r['hist_success'])
    cons_success = sum(1 for r in results if r['cons_success'])
    
    print(f"\nTotal time: {elapsed/60:.1f} minutes")
    print(f"Historical data: {hist_success}/{len(results)} successful ({hist_success/len(results)*100:.1f}%)")
    print(f"Constituents: {cons_success}/{len(results)} successful ({cons_success/len(results)*100:.1f}%)")
    
    # Detailed results table
    print("\n" + "="*80)
    print("Detailed Results")
    print("="*80)
    print(f"\n{'Industry':<20} {'Code':<10} {'Historical':<15} {'Constituents':<15}")
    print("-" * 80)
    
    for r in results:
        hist_str = f"✅ {r['hist_days']} days" if r['hist_success'] else "❌ Failed"
        cons_str = f"✅ {r['cons_count']} stocks" if r['cons_success'] else "❌ Failed"
        print(f"{r['name']:<20} {r['code']:<10} {hist_str:<15} {cons_str:<15}")
    
    # Failed industries
    failed_hist = [r for r in results if not r['hist_success']]
    failed_cons = [r for r in results if not r['cons_success']]
    
    if failed_hist:
        print("\n" + "="*80)
        print("Failed Historical Data Queries")
        print("="*80)
        for r in failed_hist:
            print(f"{r['name']} ({r['code']}): {r['hist_error']}")
    
    if failed_cons:
        print("\n" + "="*80)
        print("Failed Constituent Queries")
        print("="*80)
        for r in failed_cons:
            print(f"{r['name']} ({r['code']}): {r['cons_error']}")
    
    # Save results to CSV
    df_results = pd.DataFrame(results)
    output_file = 'docs/shenwan_industries_validation.csv'
    df_results.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ Results saved to {output_file}")

if __name__ == "__main__":
    main()
