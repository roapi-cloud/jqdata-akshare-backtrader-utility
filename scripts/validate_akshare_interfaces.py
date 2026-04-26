#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AkShare Interface Validation Script

This script validates all AkShare interfaces required for the Market Diagnostic System.
It tests data availability, return formats, field mappings, API response times,
and rate limiting strategies.

Requirements validated:
- Requirement 1.6: Error handling and logging for missing/invalid data
- Requirement 22.1: Error logging with timestamp and data source information

Usage:
    python scripts/validate_akshare_interfaces.py
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValidationResult:
    """Container for validation test results"""
    
    def __init__(self, interface_name: str):
        self.interface_name = interface_name
        self.success = False
        self.response_time = 0.0
        self.row_count = 0
        self.columns: List[str] = []
        self.sample_data: Optional[pd.DataFrame] = None
        self.error_message: Optional[str] = None
        self.data_quality_issues: List[str] = []
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        sample_data = None
        if self.sample_data is not None:
            # Convert DataFrame to dict and handle date serialization
            sample_data = []
            for record in self.sample_data.to_dict('records')[:3]:
                # Convert any date/datetime objects to strings
                clean_record = {}
                for k, v in record.items():
                    if hasattr(v, 'isoformat'):
                        clean_record[k] = v.isoformat()
                    elif pd.isna(v):
                        clean_record[k] = None
                    else:
                        clean_record[k] = v
                sample_data.append(clean_record)
        
        return {
            'interface_name': self.interface_name,
            'success': self.success,
            'response_time_seconds': round(self.response_time, 3),
            'row_count': self.row_count,
            'columns': self.columns,
            'sample_data': sample_data,
            'error_message': self.error_message,
            'data_quality_issues': self.data_quality_issues,
            'timestamp': self.timestamp
        }


class AkShareInterfaceValidator:
    """Validates AkShare interfaces for Market Diagnostic System"""
    
    def __init__(self):
        self.results: List[ValidationResult] = []
        self.rate_limit_delay = 3.0  # seconds between API calls
        
    def _rate_limit(self):
        """Enforce rate limiting between API calls"""
        logger.debug(f"Rate limiting: sleeping {self.rate_limit_delay}s")
        time.sleep(self.rate_limit_delay)
    
    def _validate_interface(
        self,
        interface_name: str,
        api_call: callable,
        expected_columns: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Generic interface validation wrapper
        
        Args:
            interface_name: Name of the interface being tested
            api_call: Callable that executes the API call
            expected_columns: Optional list of expected column names
            
        Returns:
            ValidationResult object
        """
        result = ValidationResult(interface_name)
        
        try:
            logger.info(f"Testing {interface_name}...")
            start_time = time.time()
            
            # Execute API call
            df = api_call()
            
            result.response_time = time.time() - start_time
            
            # Validate response
            if df is None or df.empty:
                result.error_message = "API returned empty DataFrame"
                logger.warning(f"{interface_name}: Empty response")
                return result
            
            result.success = True
            result.row_count = len(df)
            result.columns = list(df.columns)
            result.sample_data = df.head(3)
            
            # Check for expected columns
            if expected_columns:
                missing_cols = set(expected_columns) - set(df.columns)
                if missing_cols:
                    result.data_quality_issues.append(
                        f"Missing expected columns: {missing_cols}"
                    )
            
            # Check for missing values
            null_counts = df.isnull().sum()
            high_null_cols = null_counts[null_counts > len(df) * 0.5].index.tolist()
            if high_null_cols:
                result.data_quality_issues.append(
                    f"High null rate (>50%) in columns: {high_null_cols}"
                )
            
            logger.info(
                f"{interface_name}: SUCCESS - {result.row_count} rows, "
                f"{len(result.columns)} columns, {result.response_time:.2f}s"
            )
            
        except Exception as e:
            result.error_message = str(e)
            result.response_time = time.time() - start_time
            logger.error(f"{interface_name}: FAILED - {e}")
        
        return result
    
    def validate_index_data(self) -> List[ValidationResult]:
        """
        Validate index historical data interfaces
        
        Tests:
        - ak.stock_zh_index_daily() for major indices
        - 60-day historical data availability
        
        Requirements: 1.1, 1.2
        """
        import akshare as ak
        
        results = []
        
        # Test indices
        test_indices = [
            ("sh000001", "上证指数"),
            ("sh000300", "沪深300"),
            ("sz399006", "创业板指"),
            ("sh000852", "中证1000"),
        ]
        
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        
        for code, name in test_indices:
            self._rate_limit()
            
            result = self._validate_interface(
                f"ak.stock_zh_index_daily({code})",
                lambda c=code: ak.stock_zh_index_daily(symbol=c),
                expected_columns=['date', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Check if we have at least 60 days of data
            if result.success and result.row_count < 60:
                result.data_quality_issues.append(
                    f"Insufficient historical data: {result.row_count} days (need 60+)"
                )
            
            results.append(result)
        
        self.results.extend(results)
        return results
    
    def validate_breadth_data(self) -> List[ValidationResult]:
        """
        Validate market breadth data interfaces
        
        Tests:
        - ak.stock_zt_pool_em() - limit-up pool
        - ak.stock_dt_pool_em() - limit-down pool
        - ak.stock_zh_a_spot_em() - market-wide realtime quotes
        
        Requirements: 1.3, 3.1, 3.2, 3.3
        """
        import akshare as ak
        
        results = []
        
        # Use a recent trading date
        test_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        
        # Test limit-up pool
        self._rate_limit()
        result = self._validate_interface(
            f"ak.stock_zt_pool_em(date={test_date})",
            lambda: ak.stock_zt_pool_em(date=test_date),
            expected_columns=['代码', '名称', '涨跌幅', '最新价', '成交额', '流通市值']
        )
        results.append(result)
        
        # Test limit-down pool (note: this interface may not exist in current akshare)
        self._rate_limit()
        try:
            result = self._validate_interface(
                f"ak.stock_zt_pool_dtgc_em(date={test_date})",
                lambda: ak.stock_zt_pool_dtgc_em(date=test_date),
                expected_columns=['代码', '名称', '涨跌幅', '最新价', '成交额', '流通市值']
            )
            results.append(result)
        except AttributeError:
            logger.warning("ak.stock_zt_pool_dtgc_em not available, skipping limit-down pool test")
        
        # Test market-wide realtime quotes
        self._rate_limit()
        result = self._validate_interface(
            "ak.stock_zh_a_spot_em()",
            lambda: ak.stock_zh_a_spot_em(),
            expected_columns=[
                '代码', '名称', '最新价', '涨跌幅', '成交量', '成交额',
                '量比', '换手率', '市盈率-动态', '市净率'
            ]
        )
        
        # Additional validation for market-wide data
        if result.success:
            if result.row_count < 4000:
                result.data_quality_issues.append(
                    f"Unexpectedly low stock count: {result.row_count} (expected 4000+)"
                )
        
        results.append(result)
        
        self.results.extend(results)
        return results
    
    def validate_sector_data(self) -> List[ValidationResult]:
        """
        Validate sector/industry data interfaces
        
        Tests:
        - ak.stock_board_industry_name_em() - industry list
        - ak.stock_board_industry_hist_em() - industry historical data
        - ak.stock_board_industry_cons_em() - industry constituents
        - ak.stock_sector_fund_flow_rank() - industry capital flow
        
        Requirements: 1.4, 6.1, 6.2
        """
        import akshare as ak
        
        results = []
        
        # Test industry list
        self._rate_limit()
        result = self._validate_interface(
            "ak.stock_board_industry_name_em()",
            lambda: ak.stock_board_industry_name_em(),
            expected_columns=['板块名称', '板块代码']
        )
        results.append(result)
        
        # Use hardcoded sample industry codes for testing (Shenwan Level-1)
        # BK0447: 通信, BK0437: 医药生物, BK0432: 汽车
        sample_industries = [
            ('BK0447', '通信'),
            ('BK0437', '医药生物'),
            ('BK0432', '汽车'),
        ]
        
        for sample_code, sample_name in sample_industries:
            # Test industry historical data
            self._rate_limit()
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")
            
            result = self._validate_interface(
                f"ak.stock_board_industry_hist_em(symbol={sample_code}, name={sample_name})",
                lambda code=sample_code: ak.stock_board_industry_hist_em(
                    symbol=code,
                    period='日k',
                    start_date=start_date,
                    end_date=end_date,
                    adjust=''
                ),
                expected_columns=['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额']
            )
            
            # Additional validation for historical data
            if result.success:
                # Check if we have at least 20 days of data
                if result.row_count < 20:
                    result.data_quality_issues.append(
                        f"Insufficient historical data: {result.row_count} days (expected 20+)"
                    )
                
                # Check for required fields including 涨跌幅
                if '涨跌幅' not in result.columns:
                    result.data_quality_issues.append("Missing '涨跌幅' field")
            
            results.append(result)
            
            # Test industry constituents
            self._rate_limit()
            result = self._validate_interface(
                f"ak.stock_board_industry_cons_em(symbol={sample_code}, name={sample_name})",
                lambda code=sample_code: ak.stock_board_industry_cons_em(symbol=code),
                expected_columns=['代码', '名称', '最新价', '涨跌幅']
            )
            
            # Additional validation for constituents
            if result.success:
                # Check if we have reasonable number of constituents
                if result.row_count < 10:
                    result.data_quality_issues.append(
                        f"Low constituent count: {result.row_count} stocks (expected 10+)"
                    )
            
            results.append(result)
        
        # Test industry capital flow
        self._rate_limit()
        result = self._validate_interface(
            "ak.stock_sector_fund_flow_rank(indicator='今日')",
            lambda: ak.stock_sector_fund_flow_rank(indicator='今日'),
            expected_columns=['名称', '涨跌幅', '主力净流入-净额', '主力净流入-净占比']
        )
        results.append(result)
        
        self.results.extend(results)
        return results
    
    def validate_capital_flow_data(self) -> List[ValidationResult]:
        """
        Validate capital flow data interfaces
        
        Tests:
        - ak.stock_hsgt_north_net_flow_in_em() - North Bound Capital
        - ak.stock_margin_underlying_info_szse() - Margin balance (Shenzhen)
        - ak.stock_margin_underlying_info_sse() - Margin balance (Shanghai)
        
        Requirements: 1.5, 7.3, 7.4
        """
        import akshare as ak
        
        results = []
        
        # Test North Bound Capital (use correct interface name)
        self._rate_limit()
        try:
            result = self._validate_interface(
                "ak.stock_hsgt_hist_em(symbol='沪股通')",
                lambda: ak.stock_hsgt_hist_em(symbol='沪股通'),
                expected_columns=['日期', '当日成交净买额', '当日资金流入']
            )
            results.append(result)
        except AttributeError:
            logger.warning("ak.stock_hsgt_hist_em not available, trying alternative interface")
            try:
                result = self._validate_interface(
                    "ak.stock_hsgt_north_net_flow_in_em(indicator='沪股通')",
                    lambda: ak.stock_hsgt_north_net_flow_in_em(indicator='沪股通'),
                    expected_columns=['日期', '当日成交净买额']
                )
                results.append(result)
            except Exception as e:
                logger.error(f"North Bound Capital interface not available: {e}")
        
        # Test margin balance (note: these interfaces may have different structures)
        self._rate_limit()
        try:
            result = self._validate_interface(
                "ak.stock_margin_sse()",
                lambda: ak.stock_margin_sse(start_date='20240101'),
                expected_columns=['日期', '融资余额', '融资买入额']
            )
            results.append(result)
        except Exception as e:
            logger.warning(f"Margin balance interface test skipped: {e}")
        
        self.results.extend(results)
        return results
    
    def validate_valuation_data(self) -> List[ValidationResult]:
        """
        Validate valuation and macro data interfaces
        
        Tests:
        - ak.stock_zh_index_value_csindex() - CSI index PE/PB
        - ak.bond_zh_us_rate() - China/US bond yields
        - ak.currency_boc_sina() - BOC exchange rates
        
        Requirements: 24.1, 24.2
        """
        import akshare as ak
        
        results = []
        
        # Test CSI index valuation
        self._rate_limit()
        result = self._validate_interface(
            "ak.stock_zh_index_value_csindex(symbol='000300')",
            lambda: ak.stock_zh_index_value_csindex(symbol='000300'),
            expected_columns=['日期', '市盈率', '市净率']
        )
        results.append(result)
        
        # Test bond yields
        self._rate_limit()
        result = self._validate_interface(
            "ak.bond_zh_us_rate()",
            lambda: ak.bond_zh_us_rate(),
            expected_columns=['日期', '中国国债收益率10年', '美国国债收益率10年']
        )
        results.append(result)
        
        # Test exchange rates
        self._rate_limit()
        result = self._validate_interface(
            "ak.currency_boc_sina()",
            lambda: ak.currency_boc_sina(),
            expected_columns=['日期', '货币名称', '中行折算价']
        )
        results.append(result)
        
        self.results.extend(results)
        return results
    
    def test_rate_limiting(self) -> Dict[str, Any]:
        """
        Test rate limiting and anti-ban strategies
        
        Measures:
        - Response time variance with different delays
        - Success rate with rapid requests
        
        Requirements: 1.6, 22.1
        """
        import akshare as ak
        
        logger.info("Testing rate limiting strategies...")
        
        test_results = {
            'rapid_requests': {'success_count': 0, 'fail_count': 0, 'avg_time': 0.0},
            'delayed_requests': {'success_count': 0, 'fail_count': 0, 'avg_time': 0.0}
        }
        
        # Test rapid requests (no delay)
        times = []
        for i in range(3):
            try:
                start = time.time()
                df = ak.stock_zh_index_daily(symbol='sh000001')
                elapsed = time.time() - start
                times.append(elapsed)
                if df is not None and not df.empty:
                    test_results['rapid_requests']['success_count'] += 1
                else:
                    test_results['rapid_requests']['fail_count'] += 1
            except Exception as e:
                test_results['rapid_requests']['fail_count'] += 1
                logger.warning(f"Rapid request {i+1} failed: {e}")
        
        if times:
            test_results['rapid_requests']['avg_time'] = sum(times) / len(times)
        
        # Test delayed requests (3s delay)
        times = []
        for i in range(3):
            if i > 0:
                time.sleep(3.0)
            try:
                start = time.time()
                df = ak.stock_zh_index_daily(symbol='sh000300')
                elapsed = time.time() - start
                times.append(elapsed)
                if df is not None and not df.empty:
                    test_results['delayed_requests']['success_count'] += 1
                else:
                    test_results['delayed_requests']['fail_count'] += 1
            except Exception as e:
                test_results['delayed_requests']['fail_count'] += 1
                logger.warning(f"Delayed request {i+1} failed: {e}")
        
        if times:
            test_results['delayed_requests']['avg_time'] = sum(times) / len(times)
        
        logger.info(f"Rate limiting test results: {test_results}")
        return test_results
    
    def generate_report(self, output_path: str = "docs/akshare_interface_validation.md"):
        """
        Generate validation report in Markdown format
        
        Args:
            output_path: Path to output Markdown file
        """
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Calculate summary statistics
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - successful_tests
        avg_response_time = sum(r.response_time for r in self.results) / total_tests if total_tests > 0 else 0
        
        # Generate Markdown report
        report_lines = [
            "# AkShare Interface Validation Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"- **Total Tests:** {total_tests}",
            f"- **Successful:** {successful_tests}",
            f"- **Failed:** {failed_tests}",
            f"- **Success Rate:** {successful_tests/total_tests*100:.1f}%",
            f"- **Average Response Time:** {avg_response_time:.2f}s",
            "",
            "## Test Results",
            ""
        ]
        
        # Group results by category
        categories = {
            'Index Data': [],
            'Breadth Data': [],
            'Sector Data': [],
            'Capital Flow': [],
            'Valuation Data': []
        }
        
        for result in self.results:
            if 'index_daily' in result.interface_name:
                categories['Index Data'].append(result)
            elif any(x in result.interface_name for x in ['zt_pool', 'dt_pool', 'spot_em']):
                categories['Breadth Data'].append(result)
            elif any(x in result.interface_name for x in ['board_industry', 'sector_fund']):
                categories['Sector Data'].append(result)
            elif any(x in result.interface_name for x in ['hsgt', 'margin']):
                categories['Capital Flow'].append(result)
            elif any(x in result.interface_name for x in ['value_csindex', 'bond', 'currency']):
                categories['Valuation Data'].append(result)
        
        for category, results in categories.items():
            if not results:
                continue
            
            report_lines.extend([
                f"### {category}",
                "",
                "| Interface | Status | Rows | Columns | Response Time | Issues |",
                "|-----------|--------|------|---------|---------------|--------|"
            ])
            
            for result in results:
                status = "✅ SUCCESS" if result.success else "❌ FAILED"
                issues = "; ".join(result.data_quality_issues) if result.data_quality_issues else "None"
                if result.error_message:
                    issues = result.error_message
                
                report_lines.append(
                    f"| `{result.interface_name}` | {status} | {result.row_count} | "
                    f"{len(result.columns)} | {result.response_time:.2f}s | {issues} |"
                )
            
            report_lines.append("")
        
        # Add detailed field mappings
        report_lines.extend([
            "## Field Mappings",
            "",
            "### Index Data Fields",
            "",
            "```python",
            "# ak.stock_zh_index_daily()",
            "columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']",
            "```",
            "",
            "### Breadth Data Fields",
            "",
            "```python",
            "# ak.stock_zh_a_spot_em()",
            "columns = ['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额',",
            "           '量比', '换手率', '市盈率-动态', '市净率', '总市值', '流通市值']",
            "```",
            "",
            "### Sector Data Fields",
            "",
            "```python",
            "# ak.stock_board_industry_hist_em()",
            "columns = ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '涨跌幅']",
            "```",
            "",
            "## Recommendations",
            "",
            "### Rate Limiting",
            "",
            "- **Recommended delay between requests:** 3-5 seconds",
            "- **Batch processing:** Use caching for repeated queries within same session",
            "- **Peak hours:** Avoid 9:30-10:00 and 14:30-15:00 (market open/close)",
            "",
            "### Anti-Ban Strategies",
            "",
            "1. **Random User-Agent rotation:** Implement User-Agent pool",
            "2. **Exponential backoff:** Retry with increasing delays on failures",
            "3. **Circuit breaker:** Stop requests after consecutive failures",
            "4. **Request jitter:** Add random delay variance (±1s)",
            "",
            "### Known Issues",
            ""
        ])
        
        # Add known issues from validation
        issues_found = set()
        for result in self.results:
            if result.error_message:
                issues_found.add(f"- `{result.interface_name}`: {result.error_message}")
            for issue in result.data_quality_issues:
                issues_found.add(f"- `{result.interface_name}`: {issue}")
        
        if issues_found:
            report_lines.extend(sorted(issues_found))
        else:
            report_lines.append("- No critical issues found")
        
        report_lines.extend([
            "",
            "## Next Steps",
            "",
            "1. Review failed interfaces and implement fallback strategies",
            "2. Implement caching layer for frequently accessed data",
            "3. Set up monitoring for API availability and response times",
            "4. Document field mappings in data layer implementation",
            ""
        ])
        
        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        logger.info(f"Validation report written to {output_path}")
        
        # Also save JSON results
        json_path = output_path.replace('.md', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    'summary': {
                        'total_tests': total_tests,
                        'successful': successful_tests,
                        'failed': failed_tests,
                        'success_rate': successful_tests/total_tests if total_tests > 0 else 0,
                        'avg_response_time': avg_response_time
                    },
                    'results': [r.to_dict() for r in self.results],
                    'timestamp': datetime.now().isoformat()
                },
                f,
                ensure_ascii=False,
                indent=2
            )
        
        logger.info(f"JSON results written to {json_path}")


def main():
    """Main validation workflow"""
    logger.info("=" * 80)
    logger.info("AkShare Interface Validation - Market Diagnostic System")
    logger.info("=" * 80)
    
    validator = AkShareInterfaceValidator()
    
    try:
        # Run all validation tests
        logger.info("\n[1/5] Validating index data interfaces...")
        validator.validate_index_data()
        
        logger.info("\n[2/5] Validating breadth data interfaces...")
        validator.validate_breadth_data()
        
        logger.info("\n[3/5] Validating sector data interfaces...")
        validator.validate_sector_data()
        
        logger.info("\n[4/5] Validating capital flow interfaces...")
        validator.validate_capital_flow_data()
        
        logger.info("\n[5/5] Validating valuation data interfaces...")
        validator.validate_valuation_data()
        
        # Test rate limiting
        logger.info("\n[BONUS] Testing rate limiting strategies...")
        rate_limit_results = validator.test_rate_limiting()
        
        # Generate report
        logger.info("\nGenerating validation report...")
        validator.generate_report()
        
        # Print summary
        total = len(validator.results)
        successful = sum(1 for r in validator.results if r.success)
        
        logger.info("\n" + "=" * 80)
        logger.info(f"Validation Complete: {successful}/{total} tests passed")
        logger.info("=" * 80)
        logger.info("\nReport generated at: docs/akshare_interface_validation.md")
        logger.info("JSON results at: docs/akshare_interface_validation.json")
        
        return 0 if successful == total else 1
        
    except Exception as e:
        logger.error(f"Validation failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
