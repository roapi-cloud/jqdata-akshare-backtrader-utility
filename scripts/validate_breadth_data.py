#!/usr/bin/env python3
"""
Breadth Data Interface Validation Script

This script validates AkShare breadth data interfaces for the Market Diagnostic System.
It tests limit-up/down pools and market-wide realtime quotes, verifying field names
and documenting data quality issues.

Requirements: 1.3, 3.1, 3.2, 3.3
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import akshare as ak
except ImportError:
    print("ERROR: akshare not installed. Run: pip install akshare")
    sys.exit(1)


class BreadthDataValidator:
    """Validates breadth data interfaces from AkShare"""
    
    def __init__(self):
        self.results = []
        self.field_mappings = {}
        self.data_quality_issues = []
        
    def test_limit_up_pool(self, date: str) -> Dict[str, Any]:
        """Test ak.stock_zt_pool_em() - limit-up pool"""
        print(f"\n{'='*80}")
        print(f"Testing: ak.stock_zt_pool_em(date='{date}')")
        print(f"{'='*80}")
        
        result = {
            'interface': 'ak.stock_zt_pool_em()',
            'status': 'UNKNOWN',
            'rows': 0,
            'columns': 0,
            'response_time': 0.0,
            'issues': []
        }
        
        try:
            start_time = time.time()
            df = ak.stock_zt_pool_em(date=date)
            response_time = time.time() - start_time
            
            result['status'] = 'SUCCESS'
            result['rows'] = len(df)
            result['columns'] = len(df.columns)
            result['response_time'] = response_time
            
            print(f"✅ SUCCESS - Retrieved {len(df)} limit-up stocks")
            print(f"⏱️  Response time: {response_time:.2f}s")
            print(f"\nColumns ({len(df.columns)}):")
            for col in df.columns:
                print(f"  - {col}")
            
            # Store field mapping
            self.field_mappings['limit_up_pool'] = list(df.columns)
            
            # Check for expected fields
            expected_fields = ['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额', '换手率']
            missing_fields = [f for f in expected_fields if f not in df.columns]
            if missing_fields:
                issue = f"Missing expected fields: {missing_fields}"
                result['issues'].append(issue)
                print(f"\n⚠️  {issue}")
            
            # Data quality checks
            print(f"\nData Quality Analysis:")
            print(f"  - Total stocks: {len(df)}")
            
            # Check for missing values
            null_counts = df.isnull().sum()
            if null_counts.any():
                print(f"  - Columns with missing values:")
                for col, count in null_counts[null_counts > 0].items():
                    pct = (count / len(df)) * 100
                    print(f"    • {col}: {count} ({pct:.1f}%)")
                    if pct > 10:
                        issue = f"High null rate in {col}: {pct:.1f}%"
                        result['issues'].append(issue)
                        self.data_quality_issues.append({
                            'interface': 'limit_up_pool',
                            'issue': issue,
                            'severity': 'HIGH' if pct > 50 else 'MEDIUM'
                        })
            else:
                print(f"  - No missing values detected ✅")
            
            # Show sample data
            print(f"\nSample Data (first 3 rows):")
            print(df.head(3).to_string())
            
            # Check for outliers in key fields
            if '涨跌幅' in df.columns:
                max_change = df['涨跌幅'].max()
                min_change = df['涨跌幅'].min()
                print(f"\n  - 涨跌幅 range: [{min_change:.2f}%, {max_change:.2f}%]")
                if max_change > 20 or min_change < -20:
                    issue = f"Outlier detected in 涨跌幅: [{min_change:.2f}%, {max_change:.2f}%]"
                    result['issues'].append(issue)
                    self.data_quality_issues.append({
                        'interface': 'limit_up_pool',
                        'issue': issue,
                        'severity': 'LOW'
                    })
            
        except Exception as e:
            result['status'] = 'FAILED'
            result['issues'].append(str(e))
            print(f"❌ FAILED: {e}")
        
        self.results.append(result)
        return result
    
    def test_limit_down_pool(self, date: str) -> Dict[str, Any]:
        """Test limit-down pool - NOTE: No direct interface exists in akshare"""
        print(f"\n{'='*80}")
        print(f"Testing: Limit-down pool (no direct interface)")
        print(f"{'='*80}")
        
        result = {
            'interface': 'limit_down_pool (workaround)',
            'status': 'UNKNOWN',
            'rows': 0,
            'columns': 0,
            'response_time': 0.0,
            'issues': []
        }
        
        print(f"⚠️  NOTE: akshare does not provide a direct limit-down pool interface")
        print(f"   Available workarounds:")
        print(f"   1. Filter from stock_zh_a_spot_em() where 涨跌幅 <= -9.9")
        print(f"   2. Use stock_a_high_low_statistics() for market statistics")
        print(f"   3. Calculate from individual stock data")
        
        # Try workaround: get market statistics
        try:
            start_time = time.time()
            df = ak.stock_a_high_low_statistics()
            response_time = time.time() - start_time
            
            result['status'] = 'WORKAROUND'
            result['rows'] = len(df)
            result['columns'] = len(df.columns)
            result['response_time'] = response_time
            
            print(f"✅ WORKAROUND SUCCESS - Retrieved market statistics")
            print(f"⏱️  Response time: {response_time:.2f}s")
            print(f"\nColumns ({len(df.columns)}):")
            for col in df.columns:
                print(f"  - {col}")
            
            # Store field mapping
            self.field_mappings['market_statistics'] = list(df.columns)
            
            print(f"\nSample Data:")
            print(df.to_string())
            
            result['issues'].append("No direct limit-down pool interface - using market statistics as workaround")
            
        except Exception as e:
            result['status'] = 'FAILED'
            result['issues'].append(str(e))
            print(f"❌ FAILED: {e}")
        
        self.results.append(result)
        return result
    
    def test_market_spot_data(self) -> Dict[str, Any]:
        """Test ak.stock_zh_a_spot_em() - market-wide realtime quotes"""
        print(f"\n{'='*80}")
        print(f"Testing: ak.stock_zh_a_spot_em()")
        print(f"{'='*80}")
        
        result = {
            'interface': 'ak.stock_zh_a_spot_em()',
            'status': 'UNKNOWN',
            'rows': 0,
            'columns': 0,
            'response_time': 0.0,
            'issues': []
        }
        
        try:
            start_time = time.time()
            df = ak.stock_zh_a_spot_em()
            response_time = time.time() - start_time
            
            result['status'] = 'SUCCESS'
            result['rows'] = len(df)
            result['columns'] = len(df.columns)
            result['response_time'] = response_time
            
            print(f"✅ SUCCESS - Retrieved {len(df)} stocks")
            print(f"⏱️  Response time: {response_time:.2f}s")
            print(f"\nColumns ({len(df.columns)}):")
            for col in df.columns:
                print(f"  - {col}")
            
            # Store field mapping
            self.field_mappings['market_spot'] = list(df.columns)
            
            # Check for expected fields
            expected_fields = ['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额', '量比', '换手率']
            missing_fields = [f for f in expected_fields if f not in df.columns]
            if missing_fields:
                issue = f"Missing expected fields: {missing_fields}"
                result['issues'].append(issue)
                print(f"\n⚠️  {issue}")
            else:
                print(f"\n✅ All expected fields present")
            
            # Data quality checks
            print(f"\nData Quality Analysis:")
            print(f"  - Total stocks: {len(df)}")
            
            # Check for missing values in key fields
            key_fields = ['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额']
            available_key_fields = [f for f in key_fields if f in df.columns]
            
            if available_key_fields:
                null_counts = df[available_key_fields].isnull().sum()
                if null_counts.any():
                    print(f"  - Missing values in key fields:")
                    for col, count in null_counts[null_counts > 0].items():
                        pct = (count / len(df)) * 100
                        print(f"    • {col}: {count} ({pct:.1f}%)")
                        if pct > 5:
                            issue = f"High null rate in {col}: {pct:.1f}%"
                            result['issues'].append(issue)
                            self.data_quality_issues.append({
                                'interface': 'market_spot',
                                'issue': issue,
                                'severity': 'HIGH' if pct > 20 else 'MEDIUM'
                            })
                else:
                    print(f"  - No missing values in key fields ✅")
            
            # Show sample data
            print(f"\nSample Data (first 5 rows):")
            sample_cols = [c for c in ['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额', '换手率'] if c in df.columns]
            if sample_cols:
                print(df[sample_cols].head(5).to_string())
            
            # Check for outliers
            if '涨跌幅' in df.columns:
                change_stats = df['涨跌幅'].describe()
                print(f"\n  - 涨跌幅 statistics:")
                print(f"    • Mean: {change_stats['mean']:.2f}%")
                print(f"    • Std: {change_stats['std']:.2f}%")
                print(f"    • Min: {change_stats['min']:.2f}%")
                print(f"    • Max: {change_stats['max']:.2f}%")
                
                # Count extreme values
                extreme_up = (df['涨跌幅'] > 15).sum()
                extreme_down = (df['涨跌幅'] < -15).sum()
                print(f"    • Stocks with >15% gain: {extreme_up}")
                print(f"    • Stocks with <-15% loss: {extreme_down}")
            
        except Exception as e:
            result['status'] = 'FAILED'
            result['issues'].append(str(e))
            print(f"❌ FAILED: {e}")
            
            # Check if it's a proxy error
            if 'proxy' in str(e).lower() or 'connection' in str(e).lower():
                print(f"\n💡 Workaround suggestion:")
                print(f"   - This interface may require direct connection (no proxy)")
                print(f"   - Consider using alternative data sources or caching")
                print(f"   - Implement retry logic with exponential backoff")
        
        self.results.append(result)
        return result
    
    def generate_report(self) -> str:
        """Generate validation report"""
        report = []
        report.append("# Breadth Data Interface Validation Report")
        report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n## Summary")
        
        total_tests = len(self.results)
        successful = sum(1 for r in self.results if r['status'] == 'SUCCESS')
        failed = sum(1 for r in self.results if r['status'] == 'FAILED')
        
        report.append(f"\n- **Total Tests:** {total_tests}")
        report.append(f"- **Successful:** {successful}")
        report.append(f"- **Failed:** {failed}")
        report.append(f"- **Success Rate:** {(successful/total_tests*100):.1f}%")
        
        # Test results table
        report.append(f"\n## Test Results")
        report.append(f"\n| Interface | Status | Rows | Columns | Response Time | Issues |")
        report.append(f"|-----------|--------|------|---------|---------------|--------|")
        
        for r in self.results:
            status_icon = "✅" if r['status'] == 'SUCCESS' else "❌"
            issues_str = "; ".join(r['issues'][:2]) if r['issues'] else "None"
            if len(issues_str) > 50:
                issues_str = issues_str[:47] + "..."
            report.append(
                f"| `{r['interface']}` | {status_icon} {r['status']} | "
                f"{r['rows']} | {r['columns']} | {r['response_time']:.2f}s | {issues_str} |"
            )
        
        # Field mappings
        report.append(f"\n## Field Mappings")
        
        for interface_name, fields in self.field_mappings.items():
            report.append(f"\n### {interface_name}")
            report.append(f"\n```python")
            report.append(f"columns = {fields}")
            report.append(f"```")
        
        # Data quality issues
        if self.data_quality_issues:
            report.append(f"\n## Data Quality Issues")
            
            for severity in ['HIGH', 'MEDIUM', 'LOW']:
                issues = [i for i in self.data_quality_issues if i['severity'] == severity]
                if issues:
                    report.append(f"\n### {severity} Severity")
                    for issue in issues:
                        report.append(f"- **{issue['interface']}**: {issue['issue']}")
        
        # Recommendations
        report.append(f"\n## Recommendations")
        
        # Check if market_spot failed
        market_spot_failed = any(
            r['interface'] == 'ak.stock_zh_a_spot_em()' and r['status'] == 'FAILED'
            for r in self.results
        )
        
        if market_spot_failed:
            report.append(f"\n### Workaround for ak.stock_zh_a_spot_em()")
            report.append(f"- **Issue**: Proxy connection errors")
            report.append(f"- **Workaround 1**: Use limit-up/down pools + individual stock queries")
            report.append(f"- **Workaround 2**: Implement caching layer with daily refresh")
            report.append(f"- **Workaround 3**: Use alternative data source (e.g., tushare, efinance)")
            report.append(f"- **Workaround 4**: Retry with exponential backoff (3 attempts)")
        
        report.append(f"\n### Rate Limiting")
        report.append(f"- **Recommended delay**: 3-5 seconds between requests")
        report.append(f"- **Batch processing**: Cache results for same trading day")
        report.append(f"- **Peak hours**: Avoid 9:30-10:00 and 14:30-15:00")
        
        report.append(f"\n### Data Quality")
        report.append(f"- **Missing values**: Implement fallback to previous day's data")
        report.append(f"- **Outliers**: Validate extreme values (>20% change) manually")
        report.append(f"- **Field mapping**: Use column name mapping for robustness")
        
        return "\n".join(report)
    
    def run_all_tests(self):
        """Run all breadth data validation tests"""
        print("="*80)
        print("BREADTH DATA INTERFACE VALIDATION")
        print("="*80)
        
        # Use yesterday's date for historical data
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        
        # Test 1: Limit-up pool
        self.test_limit_up_pool(date=yesterday)
        time.sleep(2)  # Rate limiting
        
        # Test 2: Limit-down pool
        self.test_limit_down_pool(date=yesterday)
        time.sleep(2)  # Rate limiting
        
        # Test 3: Market-wide spot data
        self.test_market_spot_data()
        
        # Generate report
        print(f"\n{'='*80}")
        print("GENERATING REPORT")
        print(f"{'='*80}")
        
        report = self.generate_report()
        
        # Save report
        report_path = project_root / "docs" / "breadth_data_validation.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding='utf-8')
        
        print(f"\n✅ Report saved to: {report_path}")
        print(f"\n{report}")


def main():
    """Main entry point"""
    validator = BreadthDataValidator()
    validator.run_all_tests()


if __name__ == "__main__":
    main()
