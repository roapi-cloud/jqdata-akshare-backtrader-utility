# Implementation Plan: Market Diagnostic System

## Overview

This implementation plan creates a comprehensive market diagnostic system for A-share market analysis. The system follows a 5-layer architecture (Data → Feature → Diagnostic → State → Report) and integrates with the existing `daily_stock_analysis` codebase. Implementation will be incremental, with testing at each layer to ensure correctness.

## Tasks

- [x] 0. Validate AkShare Data Source Interfaces (Phase 0)
  - [x] 0.1 Create validation script `scripts/validate_akshare_interfaces.py`
    - Test all required AkShare interfaces
    - Document return formats and field mappings
    - Measure API response times
    - Test rate limiting and anti-ban strategies
    - _Requirements: 1.6, 22.1_

  - [x] 0.2 Validate breadth data interfaces
    - Test `ak.stock_zt_pool_em(date='20260423')` - limit-up pool
    - Test `ak.stock_dt_pool_em(date='20260423')` - limit-down pool
    - Test `ak.stock_zh_a_spot_em()` - market-wide realtime quotes
    - Verify field names: 代码, 名称, 最新价, 涨跌幅, 成交量, 成交额, 量比, 换手率
    - Document data quality issues (missing values, outliers)
    - _Requirements: 1.3, 3.1, 3.2, 3.3_

  - [x] 0.3 Validate sector data interfaces
    - Test `ak.stock_board_industry_hist_em(symbol='BK0447', period='日k')` - industry historical data
    - Test `ak.stock_board_industry_cons_em(symbol='BK0447')` - industry constituents
    - Test `ak.stock_sector_fund_flow_rank(indicator='今日')` - industry capital flow
    - Verify field names and data completeness for all 31 Shenwan Level-1 industries
    - Document API rate limits and recommended delays
    - _Requirements: 1.4, 6.1, 6.2_

  - [x] 0.4 Validate valuation and macro data interfaces
    - Test `ak.stock_zh_index_value_csindex(symbol='000300')` - CSI300 PE/PB
    - Test `ak.stock_zh_index_value_hist_csindex(symbol='000300')` - historical valuation
    - Test `ak.bond_zh_us_rate()` - China/US bond yields
    - Test `ak.currency_boc_sina()` - BOC exchange rates
    - Verify data availability and update frequency
    - _Requirements: 24.1, 24.2_

  - [x] 0.5 Document validation results
    - Create `docs/akshare_interface_validation.md`
    - Document all tested interfaces with examples
    - List known issues and workarounds
    - Provide recommended usage patterns
    - _Requirements: 1.6, 22.1_

- [x] 1. Set up project structure and core data models
  - Create `daily_stock_analysis/src/market_diagnostic/` directory structure
  - Create subdirectories: `data/`, `features/`, `diagnostics/`, `states/`, `reports/`
  - Create `__init__.py` files for all modules
  - Define core data models in `data/models.py`: `IndexDailyData`, `MarketBreadthData`, `SectorDailyData`, `CapitalFlowData`
  - Create configuration file `config.py` with index pool, style pairs, and industry codes
  - _Requirements: 1.1, 24.1, 24.2, 24.3, 25.1_

- [x] 1.1 Write property tests for data models
  - **Property 2: Data Structure Completeness**
  - **Validates: Requirement 1.3**

- [x] 2. Implement Data Layer - Data Fetchers
  - [x] 2.1 Implement `DiagnosticDataFetcher` class in `data/fetchers.py`
    - Initialize with `DataFetcherManager` from existing codebase
    - Implement `fetch_index_series()` method to retrieve 60-day historical data for 9 core indices
    - Implement `fetch_breadth_data()` method to retrieve market breadth metrics
    - Implement `fetch_sector_data()` method to retrieve 31 Shenwan Level-1 industry data
    - Implement `fetch_capital_flow()` method to retrieve capital flow data
    - Implement `fetch_valuation_data()` method to retrieve valuation and macro data
    - Add error handling and logging for missing data
    - Add stock filtering logic (exclude ST, suspended, newly listed stocks)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 21.1, 21.2, 21.3, 21.4, 21.5_

  - [x] 2.1.1 Verify AkShare interfaces for breadth data
    - Test `ak.stock_zt_pool_em()` for limit-up stocks
    - Test `ak.stock_dt_pool_em()` for limit-down stocks
    - Test `ak.stock_zh_a_spot_em()` for market-wide statistics
    - Document return formats and field mappings
    - _Requirements: 1.3, 1.6_

  - [x] 2.1.2 Verify AkShare interfaces for sector data
    - Test `ak.stock_board_industry_hist_em()` for industry historical data
    - Test `ak.stock_board_industry_cons_em()` for industry constituents
    - Test `ak.stock_sector_fund_flow_rank()` for industry capital flow
    - Document return formats and field mappings
    - _Requirements: 1.4, 1.6_

  - [x] 2.1.3 Verify AkShare interfaces for valuation data
    - Test `ak.stock_zh_index_value_csindex()` for index PE/PB
    - Test `ak.bond_zh_us_rate()` for bond yields
    - Test `ak.currency_boc_sina()` for exchange rates
    - Document return formats and field mappings
    - _Requirements: 1.6, 24.1_

  - [x] 2.1.4 Implement breadth data calculation
    - Fetch market-wide realtime quotes using `ak.stock_zh_a_spot_em()`
    - Calculate up/down counts, limit-up/down counts
    - Calculate above_ma20_ratio (requires individual stock MA20 calculation)
    - Calculate new high/low ratios (requires 20-day historical data)
    - Implement stock filtering (ST, suspended, newly listed)
    - Add caching mechanism (20-minute TTL)
    - _Requirements: 1.3, 1.7, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 2.1.5 Implement sector data enrichment
    - Fetch sector historical data using `ak.stock_board_industry_hist_em()`
    - Fetch sector constituents using `ak.stock_board_industry_cons_em()`
    - Calculate sector breadth (above_ma20_ratio within sector)
    - Calculate sector new high ratio
    - Calculate sector turnover and amount share
    - Add rate limiting (3-second delay between sectors)
    - _Requirements: 1.4, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 2.1.6 Implement valuation data fetching
    - Fetch index valuation using `ak.stock_zh_index_value_csindex()`
    - Fetch bond yields using `ak.bond_zh_us_rate()`
    - Fetch exchange rates using `ak.currency_boc_sina()`
    - Calculate historical percentiles (requires historical valuation data)
    - Add caching mechanism (daily cache)
    - _Requirements: 24.1, 24.2_

  - [x] 2.2 Write property tests for data fetchers
    - **Property 1: Historical Data Completeness**
    - **Validates: Requirement 1.2**
    - **Property 3: Sector Data Completeness**
    - **Validates: Requirement 1.4**
    - **Property 4: Capital Flow Data Structure**
    - **Validates: Requirement 1.5**
    - **Property 5: Error Handling Continuity**
    - **Validates: Requirements 1.6, 22.1, 22.2**
    - **Property 6: Stock Filtering Consistency**
    - **Validates: Requirement 1.7**

  - [x] 2.3 Write unit tests for data fetcher edge cases
    - Test handling of missing index data
    - Test handling of incomplete sector data
    - Test T+1 data marking for North Bound Capital and margin balance
    - _Requirements: 1.6, 7.6, 22.3, 22.4_

- [x] 3. Checkpoint - Verify data layer functionality
  - Ensure all data fetcher tests pass
  - Verify integration with existing `DataFetcherManager`
  - Ask the user if questions arise

- [x] 4. Implement Feature Layer - Trend Features
  - [x] 4.1 Implement trend feature calculation in `features/trend.py`
    - Define `TrendFeatures` dataclass with all required fields
    - Implement `compute_trend_features()` function
    - Calculate MA5, MA10, MA20, MA60, MA120 using numpy
    - Determine MA alignment status (bullish/bearish/tangled)
    - Calculate MACD (DIF, DEA, BAR) and identify golden/death cross
    - Calculate RSRS scores and normalize them
    - Calculate ATR-20 for volatility measurement
    - Calculate bias ratios relative to MA5, MA20, MA60
    - Calculate relative strength ratios between index pairs
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 4.2 Write property tests for trend features
    - **Property 7: Moving Average Calculation Completeness**
    - **Validates: Requirement 2.1**
    - **Property 8: MA Alignment Classification Validity**
    - **Validates: Requirement 2.2**
    - **Property 9: MACD Calculation Completeness**
    - **Validates: Requirement 2.3**
    - **Property 10: Technical Indicator Calculation**
    - **Validates: Requirements 2.4, 2.5, 2.6**
    - **Property 11: Relative Strength Calculation**
    - **Validates: Requirement 2.7**

  - [x] 4.3 Write unit tests for trend feature edge cases
    - Test with insufficient historical data
    - Test with extreme price movements
    - Test MACD signal detection accuracy
    - _Requirements: 2.1, 2.3, 22.4_

- [x] 5. Implement Feature Layer - Breadth, Sentiment, and Style Features
  - [x] 5.1 Implement breadth features in `features/breadth.py`
    - Define `BreadthFeatures` dataclass
    - Implement `compute_breadth_features()` function
    - Calculate up/down ratio, limit-up rate, seal rate
    - Calculate MA penetration ratios (above_ma20_ratio, above_ma60_ratio)
    - Calculate new high ratio
    - Calculate turnover amount deviations from 5-day and 20-day averages
    - Compute composite breadth score (0-100)
    - Add division-by-zero handling
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 5.2 Implement sentiment features in `features/sentiment.py`
    - Define `SentimentFeatures` dataclass
    - Implement `compute_sentiment_features()` function
    - Calculate limit-up to limit-down ratio
    - Calculate continuous limit-up count
    - Calculate seal rate for limit-up stocks
    - Calculate next-day premium for yesterday's limit-up stocks
    - Calculate turnover rate Z-score
    - Compute composite sentiment score
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 5.3 Implement style features in `features/style.py`
    - Define `StyleFeatures` dataclass
    - Implement `compute_style_features()` function
    - Calculate relative strength for all three style pairs (large-cap vs small-cap, 沪深300 vs 中证1000, 中证500 vs 中证1000)
    - Calculate 1-day, 5-day, and 20-day returns for each style index
    - Calculate turnover amount share for each style category
    - Identify dominant style (large-cap defensive, small-cap offensive, growth dominant, dividend defensive, style conflict)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

  - [x] 5.4 Write property tests for breadth, sentiment, and style features
    - **Property 12: Breadth Metrics Calculation**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
    - **Property 13: Breadth Score Range Constraint**
    - **Validates: Requirement 3.7**
    - **Property 14: Division by Zero Handling**
    - **Validates: Requirements 3.3, 4.1**
    - **Property 15: Sentiment Metrics Calculation**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.6**
    - **Property 16: Historical Context Calculation**
    - **Validates: Requirements 4.4, 4.5**
    - **Property 17: Style Relative Strength Calculation**
    - **Validates: Requirements 5.1, 5.2, 5.3**
    - **Property 18: Multi-Period Return Calculation**
    - **Validates: Requirements 5.4, 6.1**
    - **Property 19: Style Classification Validity**
    - **Validates: Requirement 5.6**

- [x] 6. Implement Feature Layer - Sector, Capital, Risk, and Valuation Features
  - [x] 6.1 Implement sector features in `features/sector.py`
    - Define `SectorFeatureResult` dataclass
    - Implement `compute_sector_features()` function
    - Calculate 1-day, 5-day, and 20-day returns for each sector
    - Calculate excess returns relative to 沪深300
    - Calculate industry breadth (ratio of stocks above MA20)
    - Calculate new high ratio within each industry
    - Calculate industry turnover metrics (amount, amount share, amount share delta)
    - Calculate industry limit-up count and leadership score
    - Implement `compute_sector_strength_score()` using weighted Z-score formula
    - Implement `compute_sector_persistence_score()` based on ranking history
    - Implement `classify_sector_state()` function
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [x] 6.2 Implement capital flow features in `features/capital.py`
    - Define `CapitalFeatures` dataclass
    - Implement `compute_capital_features()` function
    - Calculate total market turnover amount
    - Calculate turnover deviations from 5-day, 20-day, and 60-day averages
    - Retrieve North Bound Capital net flow and calculate 5-day MA
    - Retrieve margin balance changes
    - Calculate main force net flow and ETF net flow proxies
    - Mark T+1 delayed data with time lag indicators
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 6.3 Implement risk features in `features/risk.py`
    - Define `RiskFeatures` dataclass
    - Implement `compute_risk_features()` function
    - Calculate realized volatility using 20-day rolling standard deviation
    - Calculate ATR-based volatility for each major index
    - Calculate short-term to long-term volatility ratio
    - Calculate index drawdown from recent peaks
    - Calculate cross-asset correlation (index-to-index)
    - Calculate sector correlation elevation
    - Incorporate C-VIX data when available
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 6.4 Implement valuation features in `features/valuation.py`
    - Define `ValuationFeatures` dataclass
    - Implement `compute_valuation_features()` function
    - Calculate index PE/PB for CSI300, CSI500, CSI1000
    - Calculate historical percentiles for PE/PB (requires historical data)
    - Calculate FED Spread (1/PE - bond yield)
    - Calculate Graham Index (PE * PB)
    - Calculate term spread (10Y - 1Y bond yield)
    - Determine valuation level (undervalued/fair/overvalued/bubble)
    - Calculate risk premium
    - _Requirements: 24.1, 24.2, 24.3_

  - [x] 6.5 Write property tests for sector, capital, risk, and valuation features
    - **Property 20: Sector Metrics Calculation**
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6**
    - **Property 21: Sector Strength Score Formula**
    - **Validates: Requirement 6.7**
    - **Property 22: Sector Persistence Score Calculation**
    - **Validates: Requirement 6.8**
    - **Property 23: Capital Flow Metrics Calculation**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    - **Property 24: T+1 Data Marking**
    - **Validates: Requirement 7.6**
    - **Property 25: Risk Metrics Calculation**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**
    - **Property 26: Optional Data Incorporation**
    - **Validates: Requirement 8.7**
    - **Property 54: Valuation Metrics Calculation**
    - **Validates: Requirements 24.1, 24.2**
    - **Property 55: FED Spread Calculation**
    - **Validates: Requirement 24.1**
    - **Property 56: Graham Index Calculation**
    - **Validates: Requirement 24.2**

- [x] 7. Checkpoint - Verify feature layer functionality
  - Ensure all feature calculation tests pass
  - Verify feature calculations produce expected ranges
  - Ask the user if questions arise

- [x] 8. Implement State Layer - State Enumerations and Classifiers
  - [x] 8.1 Define state enumerations in `states/enums.py`
    - Define `TrendState` enum (5 states)
    - Define `BreadthState` enum (5 states)
    - Define `SentimentState` enum (5 states)
    - Define `StyleState` enum (5 states)
    - Define `SectorState` enum (5 states)
    - Define `RiskState` enum (4 states)
    - Define `CompositeRegime` enum (7 regimes)
    - _Requirements: 9.1-9.5, 10.1-10.5, 11.1-11.5, 12.1-12.5, 13.1-13.5, 14.1-14.4, 15.1-15.7_

  - [x] 8.2 Implement state classifier in `states/classifier.py`
    - Define `MarketStateResult` dataclass
    - Implement `MarketStateClassifier` class
    - Implement `classify()` method to orchestrate all sub-classifiers
    - Implement `_classify_trend()` method with threshold-based rules
    - Implement `_classify_breadth()` method with ratio thresholds
    - Implement `_classify_sentiment()` method with indicator conditions
    - Implement `_classify_style()` method with relative strength conditions
    - Implement `_classify_sector()` method with strength/persistence conditions
    - Implement `_classify_risk()` method with volatility/drawdown/flag conditions
    - Implement `_classify_composite()` method with regime mapping rules
    - Implement `_compute_confidence()` method with data completeness scoring
    - Implement evidence extraction logic (3 key evidence items, counter-evidence)
    - Implement risk flag setting logic (6 risk flags)
    - _Requirements: 9.1-9.6, 10.1-10.6, 11.1-11.6, 12.1-12.5, 13.1-13.5, 14.1-14.10, 15.1-15.8, 16.1-16.5, 17.1-17.7_

  - [x] 8.3 Write property tests for state classification
    - **Property 27: Trend State Classification Correctness**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
    - **Property 28: Trend Score Range Constraint**
    - **Validates: Requirement 9.6**
    - **Property 29: Breadth State Threshold Classification**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**
    - **Property 30: Breadth Score Range Constraint**
    - **Validates: Requirement 10.6**
    - **Property 31: Sentiment State Classification Correctness**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**
    - **Property 32: Sentiment Score Range Constraint**
    - **Validates: Requirement 11.6**
    - **Property 33: Style State Classification Correctness**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**
    - **Property 34: Sector State Classification Correctness**
    - **Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5**
    - **Property 35: Risk State Classification Correctness**
    - **Validates: Requirements 14.1, 14.2, 14.3, 14.4**
    - **Property 36: Risk Flag Setting Correctness**
    - **Validates: Requirements 14.5, 14.6, 14.7, 14.8, 14.9, 14.10**
    - **Property 37: Composite Regime Classification Correctness**
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7**
    - **Property 38: Regime Score Formula and Range**
    - **Validates: Requirement 15.8**
    - **Property 39: Individual Sector Classification Correctness**
    - **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**
    - **Property 40: Evidence Extraction Completeness**
    - **Validates: Requirements 17.1, 17.2**
    - **Property 41: Confidence Penalty for Missing Data**
    - **Validates: Requirement 17.3**
    - **Property 42: Confidence Boost for Signal Consistency**
    - **Validates: Requirement 17.4**
    - **Property 43: Confidence Penalty for Anomalies**
    - **Validates: Requirement 17.5**
    - **Property 44: Confidence Penalty for Estimated Data**
    - **Validates: Requirement 17.6**
    - **Property 45: Confidence Range Constraint**
    - **Validates: Requirement 17.7**

  - [x] 8.4 Write unit tests for state classifier edge cases
    - Test classification with missing features
    - Test confidence calculation with various data completeness levels
    - Test evidence extraction with conflicting signals
    - _Requirements: 17.3, 17.5, 22.5_

- [x] 9. Checkpoint - Verify state layer functionality
  - Ensure all state classification tests pass
  - Verify state transitions are logical
  - Ask the user if questions arise

- [x] 10. Implement Report Layer - JSON and Markdown Output
  - [x] 10.1 Implement JSON report schema in `reports/schema.py`
    - Define `DiagnosticReport` dataclass with all required fields
    - Implement `to_json()` method for JSON serialization
    - Ensure all required fields are included (date, states, scores, metrics, evidence, confidence, missing_data)
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8, 18.9, 18.10_

  - [x] 10.2 Implement Markdown renderer in `reports/markdown_renderer.py`
    - Implement `DiagnosticMarkdownRenderer` class
    - Implement `render()` method to generate human-readable Markdown report
    - Include all required sections: one-sentence summary, state dashboard, index structure, breadth, sentiment, style, sector, capital, risk alerts, strategy mapping, evidence & confidence
    - Support optional LLM narrative section
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7, 19.8, 19.9, 19.10, 19.11, 19.12_

  - [x] 10.3 Implement strategy mapping logic in `reports/strategy_mapper.py`
    - Implement `map_regime_to_strategies()` function
    - Map each composite regime to recommended strategy groups with allocation weights
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_

  - [x] 10.4 Write property tests for report generation
    - **Property 46: JSON Output Structure Completeness**
    - **Validates: Requirements 18.1-18.10**
    - **Property 47: Markdown Report Structure Completeness**
    - **Validates: Requirements 19.1-19.11**
    - **Property 48: Strategy Mapping Correctness**
    - **Validates: Requirements 20.1-20.7**

  - [x] 10.5 Write unit tests for report formatting
    - Test JSON serialization with missing data
    - Test Markdown rendering with various state combinations
    - Test strategy mapping for all regime types
    - _Requirements: 18.10, 19.12, 20.7_

- [x] 11. Implement Diagnostic Engine - Main Orchestrator
  - [x] 11.1 Implement diagnostic engine in `engine.py`
    - Implement `MarketDiagnosticEngine` class
    - Implement `__init__()` method to initialize all components
    - Implement `run()` method to orchestrate the complete diagnostic workflow
    - Coordinate data fetching → feature calculation → state classification → report generation
    - Add optional LLM narrative generation integration
    - Implement error handling and graceful degradation
    - _Requirements: 21.6, 22.1, 22.2, 22.5, 22.6, 22.7_

  - [x] 11.2 Write integration tests for diagnostic engine
    - **Property 49: Error Logging and Continuation**
    - **Validates: Requirements 22.1, 22.2**
    - **Property 50: Graceful Degradation with Missing Data**
    - **Validates: Requirements 22.3, 22.4**
    - **Property 51: Confidence Adjustment for Data Completeness**
    - **Validates: Requirements 22.5, 22.6, 22.7**

  - [x] 11.3 Write end-to-end integration tests
    - Test complete workflow from data fetch to report generation
    - Test with partial data availability
    - Test with all data sources available
    - _Requirements: 1.6, 22.5, 22.6, 22.7_

- [x] 12. Integrate with Existing MarketAnalyzer
  - [x] 12.1 Extend `MarketAnalyzer` class in `src/market_analyzer.py`
    - Add `enable_diagnostic` parameter to `__init__()`
    - Instantiate `MarketDiagnosticEngine` when diagnostic mode is enabled
    - Implement `run_full_analysis()` method to execute full diagnostic workflow
    - Add fallback to existing `generate_market_review()` when diagnostic is disabled
    - _Requirements: 21.7, 21.8_

  - [x] 12.2 Write integration tests for MarketAnalyzer extension
    - Test diagnostic mode enabled vs disabled
    - Test fallback to existing review generation
    - Test integration with existing data fetchers
    - _Requirements: 21.1, 21.7, 21.8_

- [x] 13. Implement Caching and Performance Optimization
  - [x] 13.1 Implement data caching in `data/cache.py`
    - Implement cache storage with date-based keys
    - Implement cache retrieval logic
    - Add cache expiration (60 days retention)
    - _Requirements: 23.1, 23.2_

  - [x] 13.2 Optimize feature calculations
    - Use vectorized numpy/pandas operations for all calculations
    - Implement parallel processing for sector feature calculations
    - _Requirements: 23.3, 23.4_

  - [x] 13.3 Write performance tests
    - **Property 52: Data Caching Efficiency**
    - **Validates: Requirement 23.1**
    - Test execution time for full diagnostic run (target: <60 seconds)
    - _Requirements: 23.1, 23.5_

- [x] 14. Implement Configuration Management
  - [x] 14.1 Create configuration file `config.py`
    - Define index pool configuration (9 core indices)
    - Define style pair configuration
    - Define Shenwan Level-1 industry code list (31 industries)
    - Define threshold configurations for state classification
    - Define weight configurations for composite score calculations
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_

  - [x] 14.2 Write property tests for configuration
    - **Property 53: Configuration Application**
    - **Validates: Requirement 24.6**

- [x] 15. Final Integration and Testing
  - [x] 15.1 Create example usage script
    - Create `examples/run_diagnostic.py` demonstrating full workflow
    - Add command-line interface for running diagnostics
    - _Requirements: 21.8_

  - [x] 15.2 Write comprehensive integration tests
    - Test complete workflow with real data
    - Test error handling across all layers
    - Test graceful degradation with missing data
    - _Requirements: 22.1, 22.2, 22.5, 22.6, 22.7_

  - [x] 15.3 Create documentation
    - Write README.md for market_diagnostic module
    - Document API usage and configuration options
    - Add examples for common use cases
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_

- [x] 16. Final checkpoint - Ensure all tests pass
  - Run all unit tests, property tests, and integration tests
  - Verify performance meets requirements (<60 seconds for full run)
  - Ensure all 53 correctness properties are validated
  - Ask the user if questions arise

## Notes

- **Phase 0 (NEW)**: AkShare interface validation must be completed before Phase 1 implementation
- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation follows the existing Python codebase style and integrates with `daily_stock_analysis` components
- All 56 correctness properties from the design document are covered by property test tasks (53 original + 3 new for valuation)
- The system supports graceful degradation when data is missing or incomplete

### Data Source Strategy

**P0 (Core Data - Must Have)**:
- 9 core index daily data (verified: ✅)
- Market-wide realtime quotes (needs validation: ⚠️)
- 31 Shenwan Level-1 industry data (needs validation: ⚠️)
- North Bound Capital daily data (verified: ✅)
- Margin balance daily data (verified: ✅)

**P1 (Important Data - Should Have)**:
- Limit-up/down pool data (needs validation: ⚠️)
- Industry constituents (needs validation: ⚠️)
- Industry capital flow (needs validation: ⚠️)
- Index valuation PE/PB (needs validation: ⚠️)

**P2 (Enhancement Data - Nice to Have)**:
- Bond yields (needs validation: ⚠️)
- Exchange rates (needs validation: ⚠️)
- Commodity prices (optional)
- Option data for C-VIX (optional)

### Implementation Timeline

- **Phase 0**: AkShare interface validation (1-2 days)
- **Phase 1**: Core data layer implementation (3-5 days)
- **Phase 2**: Feature layer implementation (5-7 days)
- **Phase 3**: State and report layer (3-5 days)
- **Phase 4**: Integration and testing (2-3 days)

**Total Estimated Time**: 2-3 weeks for complete implementation
