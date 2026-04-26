# Requirements Document

## Introduction

The Market Diagnostic System is a comprehensive A-share market analysis framework that upgrades the existing `daily_stock_analysis` codebase from simple market recap articles to a systematic diagnostic engine. The system provides structured, quantitative market state assessment across nine diagnostic dimensions, outputting both human-readable reports and machine-readable data for strategy systems.

## Glossary

- **System**: The Market Diagnostic System
- **Data_Layer**: Component responsible for fetching, caching, and cleaning market data
- **Feature_Layer**: Component that transforms raw data into quantitative indicators
- **Diagnostic_Layer**: Component that analyzes features across nine dimensions
- **State_Layer**: Component that classifies market conditions into structured states
- **Report_Layer**: Component that generates output reports in Markdown and JSON formats
- **Regime**: A structured classification of overall market conditions
- **Breadth**: The proportion of stocks participating in market movements
- **Sentiment**: Market emotion measured through trading activity indicators
- **Style**: Market preference for specific investment characteristics (size, growth/value, etc.)
- **Sector**: Industry-level market segment
- **RSRS**: Resistance Support Relative Strength indicator
- **MACD**: Moving Average Convergence Divergence indicator
- **ATR**: Average True Range volatility indicator
- **C-VIX**: China Volatility Index proxy
- **North_Bound_Capital**: Foreign capital flowing into A-shares through Stock Connect
- **Margin_Balance**: Outstanding融资余额 (margin financing balance)
- **Seal_Rate**: Ratio of stocks maintaining limit-up status without breaking down

## Requirements

### Requirement 1: Data Acquisition and Management

**User Story:** As a market analyst, I want the system to automatically fetch comprehensive market data, so that I can perform multi-dimensional analysis without manual data collection.

#### Acceptance Criteria

1. WHEN the system runs for a trading date, THE Data_Layer SHALL fetch daily data for all 9 core indices (上证指数, 深证成指, 创业板指, 科创50, 上证50, 沪深300, 中证500, 中证1000, 微盘股指数)
2. WHEN the system fetches index data, THE Data_Layer SHALL retrieve at least 60 days of historical price series for technical indicator calculation
3. WHEN the system fetches market breadth data, THE Data_Layer SHALL retrieve up/down counts, limit-up/down counts, exploded board counts, and MA20/MA60 penetration ratios
4. WHEN the system fetches sector data, THE Data_Layer SHALL retrieve data for all 31 Shenwan Level-1 industries including returns, breadth, turnover, and capital flow
5. WHEN the system fetches capital flow data, THE Data_Layer SHALL retrieve North Bound Capital, margin balance, main force net flow, and ETF net flow
6. WHEN data fetching encounters missing or invalid data, THE Data_Layer SHALL log the missing data items and continue processing with available data
7. WHEN the system processes raw data, THE Data_Layer SHALL exclude ST stocks, suspended stocks, newly listed stocks (within 60 days), and anomalous samples from market breadth calculations

### Requirement 2: Trend Feature Calculation

**User Story:** As a technical analyst, I want the system to calculate comprehensive trend indicators, so that I can assess market trend direction and strength.

#### Acceptance Criteria

1. WHEN the Feature_Layer processes index data, THE System SHALL calculate MA5, MA10, MA20, MA60, and MA120 moving averages
2. WHEN the Feature_Layer calculates moving averages, THE System SHALL determine MA alignment status as "多头排列" (bullish), "空头排列" (bearish), or "缠绕" (tangled)
3. WHEN the Feature_Layer processes index data, THE System SHALL calculate MACD (DIF, DEA, BAR) and identify golden cross or death cross signals
4. WHEN the Feature_Layer processes index data, THE System SHALL calculate RSRS scores and normalize them for trend strength assessment
5. WHEN the Feature_Layer processes index data, THE System SHALL calculate ATR-20 for volatility measurement
6. WHEN the Feature_Layer processes index data, THE System SHALL calculate bias ratios relative to MA5, MA20, and MA60
7. WHEN the Feature_Layer processes multiple indices, THE System SHALL calculate relative strength ratios between index pairs (e.g., 中证1000/沪深300, 创业板指/沪深300)

### Requirement 3: Market Breadth Feature Calculation

**User Story:** As a market analyst, I want the system to quantify market breadth, so that I can distinguish between index-driven moves and broad market participation.

#### Acceptance Criteria

1. WHEN the Feature_Layer processes market breadth data, THE System SHALL calculate the up/down stock count ratio
2. WHEN the Feature_Layer processes market breadth data, THE System SHALL calculate the limit-up rate as (limit-up count / total stock count)
3. WHEN the Feature_Layer processes market breadth data, THE System SHALL calculate the seal rate as (limit-up count / (limit-up count + exploded board count))
4. WHEN the Feature_Layer processes market breadth data, THE System SHALL calculate the ratio of stocks above MA20 and MA60
5. WHEN the Feature_Layer processes market breadth data, THE System SHALL calculate the new high ratio as (20-day new high count / total stock count)
6. WHEN the Feature_Layer processes market breadth data, THE System SHALL calculate turnover amount deviation from 5-day and 20-day moving averages
7. WHEN the Feature_Layer calculates breadth features, THE System SHALL compute a composite breadth score ranging from 0 to 100

### Requirement 4: Sentiment Feature Calculation

**User Story:** As a trader, I want the system to measure market sentiment, so that I can assess risk appetite and money-making effects.

#### Acceptance Criteria

1. WHEN the Feature_Layer processes sentiment data, THE System SHALL calculate the limit-up to limit-down ratio
2. WHEN the Feature_Layer processes sentiment data, THE System SHALL calculate the continuous limit-up count (stocks with 2+ consecutive limit-ups)
3. WHEN the Feature_Layer processes sentiment data, THE System SHALL calculate the seal rate for limit-up stocks
4. WHEN the Feature_Layer processes sentiment data, THE System SHALL calculate the next-day premium for yesterday's limit-up stocks
5. WHEN the Feature_Layer processes sentiment data, THE System SHALL calculate turnover rate Z-score relative to historical distribution
6. WHEN the Feature_Layer calculates sentiment features, THE System SHALL compute a composite sentiment score

### Requirement 5: Style Feature Calculation

**User Story:** As a portfolio manager, I want the system to identify style rotation, so that I can adjust factor exposure accordingly.

#### Acceptance Criteria

1. WHEN the Feature_Layer processes style data, THE System SHALL calculate relative strength between large-cap (上证50) and small-cap (创业板指) indices
2. WHEN the Feature_Layer processes style data, THE System SHALL calculate relative strength between 沪深300 and 中证1000
3. WHEN the Feature_Layer processes style data, THE System SHALL calculate relative strength between 中证500 and 中证1000
4. WHEN the Feature_Layer processes style data, THE System SHALL calculate 1-day, 5-day, and 20-day returns for each style index
5. WHEN the Feature_Layer processes style data, THE System SHALL calculate turnover amount share for each style category
6. WHEN the Feature_Layer calculates style features, THE System SHALL identify the dominant style (large-cap defensive, small-cap offensive, growth dominant, dividend defensive, or style conflict)

### Requirement 6: Sector Feature Calculation

**User Story:** As a sector analyst, I want the system to analyze industry strength and sustainability, so that I can identify true themes versus one-day rotations.

#### Acceptance Criteria

1. WHEN the Feature_Layer processes sector data, THE System SHALL calculate 1-day, 5-day, and 20-day returns for each Shenwan Level-1 industry
2. WHEN the Feature_Layer processes sector data, THE System SHALL calculate excess returns relative to 沪深300 for each industry
3. WHEN the Feature_Layer processes sector data, THE System SHALL calculate industry breadth as the ratio of stocks above MA20 within each industry
4. WHEN the Feature_Layer processes sector data, THE System SHALL calculate the new high ratio within each industry
5. WHEN the Feature_Layer processes sector data, THE System SHALL calculate industry turnover amount, amount share, and amount share delta versus 5-day average
6. WHEN the Feature_Layer processes sector data, THE System SHALL calculate industry limit-up count and leadership score
7. WHEN the Feature_Layer calculates sector features, THE System SHALL compute a sector strength score using weighted Z-scores of (0.25×ret_5d_excess + 0.20×ret_20d_excess + 0.20×breadth_20 + 0.10×new_high_ratio + 0.10×amount_share_delta + 0.10×leadership_score - 0.05×crowding_score)
8. WHEN the Feature_Layer calculates sector features, THE System SHALL compute a persistence score based on consecutive days in top-5 rankings and turnover amount share trends

### Requirement 7: Capital Flow Feature Calculation

**User Story:** As a fund manager, I want the system to track capital flow patterns, so that I can distinguish between incremental capital and rotational trading.

#### Acceptance Criteria

1. WHEN the Feature_Layer processes capital flow data, THE System SHALL calculate total market turnover amount
2. WHEN the Feature_Layer processes capital flow data, THE System SHALL calculate turnover amount deviation from 5-day, 20-day, and 60-day moving averages
3. WHEN the Feature_Layer processes capital flow data, THE System SHALL retrieve North Bound Capital net flow and calculate 5-day moving average
4. WHEN the Feature_Layer processes capital flow data, THE System SHALL retrieve margin balance changes
5. WHEN the Feature_Layer processes capital flow data, THE System SHALL calculate main force net flow and ETF net flow proxies
6. WHEN the Feature_Layer processes capital flow data with T+1 delayed data (North Bound Capital, margin balance), THE System SHALL mark these data items with time lag indicators

### Requirement 8: Risk Feature Calculation

**User Story:** As a risk manager, I want the system to measure market risk levels, so that I can adjust position sizing and risk exposure.

#### Acceptance Criteria

1. WHEN the Feature_Layer processes risk data, THE System SHALL calculate realized volatility using 20-day rolling standard deviation of returns
2. WHEN the Feature_Layer processes risk data, THE System SHALL calculate ATR-based volatility for each major index
3. WHEN the Feature_Layer processes risk data, THE System SHALL calculate the short-term to long-term volatility ratio
4. WHEN the Feature_Layer processes risk data, THE System SHALL calculate index drawdown from recent peaks
5. WHEN the Feature_Layer processes risk data, THE System SHALL calculate cross-asset correlation (index-to-index correlation)
6. WHEN the Feature_Layer processes risk data, THE System SHALL calculate sector correlation elevation relative to historical baseline
7. WHERE C-VIX data is available, THE System SHALL incorporate volatility index readings into risk assessment

### Requirement 9: Trend State Classification

**User Story:** As a systematic trader, I want the system to classify trend states, so that I can apply appropriate trend-following or mean-reversion strategies.

#### Acceptance Criteria

1. WHEN the State_Layer processes trend features with MA5>MA10>MA20>MA60 AND MACD golden cross AND RSRS>0.7, THE System SHALL classify trend state as "强趋势上行" (strong uptrend)
2. WHEN the State_Layer processes trend features with bullish MA alignment BUT MA5<MA10 AND MA20 rising, THE System SHALL classify trend state as "趋势上行中的回调" (pullback in uptrend)
3. WHEN the State_Layer processes trend features with tangled MAs AND MACD near zero, THE System SHALL classify trend state as "震荡" (ranging)
4. WHEN the State_Layer processes trend features with MA5<MA10<MA20 OR MACD death cross, THE System SHALL classify trend state as "趋势转弱" (weakening trend)
5. WHEN the State_Layer processes trend features with price breaking below MA60 AND RSRS<0.3, THE System SHALL classify trend state as "破位下行" (breakdown)
6. WHEN the State_Layer classifies trend state, THE System SHALL calculate a trend score from 0 to 100

### Requirement 10: Breadth State Classification

**User Story:** As a market analyst, I want the system to classify market breadth states, so that I can assess internal market health.

#### Acceptance Criteria

1. WHEN the State_Layer processes breadth features with above_ma20_ratio < 0.20, THE System SHALL classify breadth state as "极弱" (extreme weak)
2. WHEN the State_Layer processes breadth features with 0.20 ≤ above_ma20_ratio < 0.35, THE System SHALL classify breadth state as "偏弱" (weak)
3. WHEN the State_Layer processes breadth features with 0.35 ≤ above_ma20_ratio < 0.55, THE System SHALL classify breadth state as "中性" (neutral)
4. WHEN the State_Layer processes breadth features with 0.55 ≤ above_ma20_ratio < 0.70, THE System SHALL classify breadth state as "偏强" (strong)
5. WHEN the State_Layer processes breadth features with above_ma20_ratio ≥ 0.70, THE System SHALL classify breadth state as "过热" (overheated)
6. WHEN the State_Layer classifies breadth state, THE System SHALL calculate a breadth score from 0 to 100

### Requirement 11: Sentiment State Classification

**User Story:** As a trader, I want the system to classify sentiment states, so that I can gauge market emotion and risk appetite.

#### Acceptance Criteria

1. WHEN the State_Layer processes sentiment features indicating extremely low limit-up rate, high limit-down rate, and low seal rate, THE System SHALL classify sentiment state as "冰点" (frozen)
2. WHEN the State_Layer processes sentiment features indicating recovering limit-up rate and improving seal rate, THE System SHALL classify sentiment state as "回暖" (warming)
3. WHEN the State_Layer processes sentiment features indicating moderate limit-up rate and seal rate, THE System SHALL classify sentiment state as "中性" (neutral)
4. WHEN the State_Layer processes sentiment features indicating high limit-up rate, high seal rate, and positive next-day premium, THE System SHALL classify sentiment state as "活跃" (active)
5. WHEN the State_Layer processes sentiment features indicating extreme limit-up rate, very high seal rate, and strong continuous limit-ups, THE System SHALL classify sentiment state as "狂热" (euphoric)
6. WHEN the State_Layer classifies sentiment state, THE System SHALL calculate a sentiment score from 0 to 100

### Requirement 12: Style State Classification

**User Story:** As a portfolio manager, I want the system to classify style states, so that I can adjust factor tilts.

#### Acceptance Criteria

1. WHEN the State_Layer processes style features with large-cap indices outperforming small-cap AND dividend style outperforming growth, THE System SHALL classify style state as "大盘防守" (large-cap defensive)
2. WHEN the State_Layer processes style features with small-cap indices outperforming large-cap, THE System SHALL classify style state as "小盘进攻" (small-cap offensive)
3. WHEN the State_Layer processes style features with growth indices significantly outperforming value, THE System SHALL classify style state as "成长主导" (growth dominant)
4. WHEN the State_Layer processes style features with dividend indices outperforming growth, THE System SHALL classify style state as "红利防守" (dividend defensive)
5. WHEN the State_Layer processes style features with conflicting signals across multiple style dimensions, THE System SHALL classify style state as "风格冲突" (style conflict)

### Requirement 13: Sector State Classification

**User Story:** As a sector analyst, I want the system to classify sector rotation patterns, so that I can identify market themes.

#### Acceptance Criteria

1. WHEN the State_Layer processes sector features with no sector having strength_score > 1.5, THE System SHALL classify sector state as "无主线" (no theme)
2. WHEN the State_Layer processes sector features with exactly one sector having strength_score > 2.0 AND persistence_score > 0.7, THE System SHALL classify sector state as "单主线" (single theme)
3. WHEN the State_Layer processes sector features with two sectors having strength_score > 1.8 AND persistence_score > 0.6, THE System SHALL classify sector state as "双主线并行" (dual theme)
4. WHEN the State_Layer processes sector features with top-5 sector rankings changing significantly over 5 days, THE System SHALL classify sector state as "高速轮动" (fast rotation)
5. WHEN the State_Layer processes sector features with declining strength scores and breadth across previously strong sectors, THE System SHALL classify sector state as "退潮分化" (fading)

### Requirement 14: Risk State Classification

**User Story:** As a risk manager, I want the system to classify risk states, so that I can adjust position sizing.

#### Acceptance Criteria

1. WHEN the State_Layer processes risk features with low realized volatility, low drawdown, and no risk flags, THE System SHALL classify risk state as "低风险" (low risk)
2. WHEN the State_Layer processes risk features with moderate volatility and drawdown, THE System SHALL classify risk state as "中性风险" (neutral risk)
3. WHEN the State_Layer processes risk features with elevated volatility OR significant drawdown OR 1-2 risk flags, THE System SHALL classify risk state as "高风险" (high risk)
4. WHEN the State_Layer processes risk features with extreme volatility OR severe drawdown OR 3+ risk flags, THE System SHALL classify risk state as "极端风险" (extreme risk)
5. WHEN the State_Layer detects volatility spike, THE System SHALL set risk flag "vol_spike"
6. WHEN the State_Layer detects breadth collapse (above_ma20_ratio dropping below 0.15), THE System SHALL set risk flag "breadth_collapse"
7. WHEN the State_Layer detects sector overcrowding (top sector amount_share > 0.25), THE System SHALL set risk flag "sector_overcrowding"
8. WHEN the State_Layer detects significant North Bound Capital outflow, THE System SHALL set risk flag "northbound_outflow"
9. WHEN the State_Layer detects leadership breakdown (top stocks underperforming), THE System SHALL set risk flag "leadership_breakdown"
10. WHEN the State_Layer detects index breaking key support levels, THE System SHALL set risk flag "index_break_support"

### Requirement 15: Composite Regime Classification

**User Story:** As a strategy allocator, I want the system to synthesize all dimensions into a composite regime, so that I can make holistic allocation decisions.

#### Acceptance Criteria

1. WHEN the State_Layer processes states with trend="强趋势上行" AND breadth="偏强" AND style="成长主导", THE System SHALL classify composite regime as "trend_risk_on_growth"
2. WHEN the State_Layer processes states with trend="强趋势上行" AND breadth="偏强" AND style="小盘进攻", THE System SHALL classify composite regime as "trend_risk_on_smallcap"
3. WHEN the State_Layer processes states with trend="震荡" AND breadth="中性", THE System SHALL classify composite regime as "balanced_rotation"
4. WHEN the State_Layer processes states with trend="趋势转弱" AND style="红利防守", THE System SHALL classify composite regime as "defensive_dividend"
5. WHEN the State_Layer processes states with risk="高风险" OR risk="极端风险", THE System SHALL classify composite regime as "high_volatility_warning"
6. WHEN the State_Layer processes states with breadth="极弱" AND sentiment="冰点", THE System SHALL classify composite regime as "panic_bottoming"
7. WHEN the State_Layer processes states with trend="破位下行" AND breadth="偏弱", THE System SHALL classify composite regime as "broad_weakness_hold"
8. WHEN the State_Layer classifies composite regime, THE System SHALL calculate a regime score from 0 to 100 using formula (0.20×trend_score + 0.15×breadth_score + 0.15×sentiment_score + 0.15×style_score + 0.15×sector_score - 0.20×risk_score)

### Requirement 16: Sector Classification

**User Story:** As a sector analyst, I want the system to classify each sector's state, so that I can distinguish true trends from temporary bounces.

#### Acceptance Criteria

1. WHEN the State_Layer processes sector features with strength_score > 2.0 AND persistence_score > 0.7, THE System SHALL classify the sector as "主升趋势" (main uptrend)
2. WHEN the State_Layer processes sector features with strength_score > 1.5 AND persistence_score between 0.4 and 0.7, THE System SHALL classify the sector as "趋势强化" (trend strengthening)
3. WHEN the State_Layer processes sector features with strength_score between -0.5 and 1.5, THE System SHALL classify the sector as "震荡整理" (consolidation)
4. WHEN the State_Layer processes sector features with strength_score between 0.5 and 1.5 AND ret_20d < -0.10, THE System SHALL classify the sector as "超跌反弹" (oversold bounce)
5. WHEN the State_Layer processes sector features with strength_score < -0.5, THE System SHALL classify the sector as "弱势退潮" (weak fading)

### Requirement 17: Evidence and Confidence Assessment

**User Story:** As a decision maker, I want the system to provide evidence and confidence levels, so that I can assess the reliability of conclusions.

#### Acceptance Criteria

1. WHEN the State_Layer generates a market state result, THE System SHALL identify the 3 most important supporting evidence items
2. WHEN the State_Layer generates a market state result, THE System SHALL identify counter-evidence that contradicts the main conclusion
3. WHEN the State_Layer calculates confidence, THE System SHALL reduce confidence by 0.2 for each missing core indicator
4. WHEN the State_Layer calculates confidence, THE System SHALL increase confidence by 0.1 when signals across dimensions are consistent
5. WHEN the State_Layer calculates confidence, THE System SHALL reduce confidence by 0.1 when extreme anomalous values are detected
6. WHEN the State_Layer calculates confidence, THE System SHALL reduce confidence by 0.05 for each data item relying on estimation or proxy
7. WHEN the State_Layer generates a market state result, THE System SHALL output a confidence score between 0 and 1

### Requirement 18: Structured JSON Output

**User Story:** As a strategy system developer, I want the system to output structured JSON, so that I can programmatically consume diagnostic results.

#### Acceptance Criteria

1. WHEN the Report_Layer generates output, THE System SHALL produce a JSON document containing date, all state classifications, all scores, and all metrics
2. WHEN the Report_Layer generates JSON output, THE System SHALL include an indices array with price data and technical indicators for all 9 core indices
3. WHEN the Report_Layer generates JSON output, THE System SHALL include a breadth_metrics object with all breadth indicators
4. WHEN the Report_Layer generates JSON output, THE System SHALL include a sentiment_metrics object with all sentiment indicators
5. WHEN the Report_Layer generates JSON output, THE System SHALL include a style_metrics object with relative strength ratios for all style pairs
6. WHEN the Report_Layer generates JSON output, THE System SHALL include a sector_table array with all 31 industries and their diagnostic metrics
7. WHEN the Report_Layer generates JSON output, THE System SHALL include a capital_metrics object with turnover, North Bound Capital, and margin data
8. WHEN the Report_Layer generates JSON output, THE System SHALL include a risk_flags array listing all active risk warnings
9. WHEN the Report_Layer generates JSON output, THE System SHALL include key_evidence, counter_evidence, and confidence fields
10. WHEN the Report_Layer generates JSON output, THE System SHALL include a missing_data array listing any unavailable data items

### Requirement 19: Markdown Report Generation

**User Story:** As a market analyst, I want the system to generate a human-readable Markdown report, so that I can quickly understand market conditions.

#### Acceptance Criteria

1. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a one-sentence summary at the top
2. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a state dashboard table showing all dimension states and scores
3. WHEN the Report_Layer generates a Markdown report, THE System SHALL include an index structure section with price data and technical indicators
4. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a market breadth section with breadth metrics table
5. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a sentiment section with sentiment metrics table
6. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a style rotation section with style relative strength table
7. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a sector diagnosis section with top-5 strongest and weakest sectors
8. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a capital flow section with turnover and flow metrics
9. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a risk alert section listing all active risk flags
10. WHEN the Report_Layer generates a Markdown report, THE System SHALL include a strategy mapping section with recommended strategy groups for the current regime
11. WHEN the Report_Layer generates a Markdown report, THE System SHALL include an evidence and confidence section with supporting evidence, counter-evidence, and confidence score
12. WHERE LLM narrative generation is enabled, THE Report_Layer SHALL append an LLM-generated narrative analysis section

### Requirement 20: Strategy Mapping

**User Story:** As a portfolio manager, I want the system to map market regimes to strategy groups, so that I can adjust strategy allocation.

#### Acceptance Criteria

1. WHEN the System classifies composite regime as "trend_risk_on_growth" OR "trend_risk_on_smallcap", THE System SHALL recommend trend ETF group, sector rotation group, and small-cap offensive group
2. WHEN the System classifies composite regime as "balanced_rotation", THE System SHALL recommend sector rotation group, dividend value group, and stock-bond balance group
3. WHEN the System classifies composite regime as "defensive_dividend", THE System SHALL recommend dividend value group, stock-bond balance group, and all-weather group
4. WHEN the System classifies composite regime as "high_volatility_warning", THE System SHALL recommend stock-bond balance group, all-weather group, and high cash allocation
5. WHEN the System classifies composite regime as "panic_bottoming", THE System SHALL recommend small position probing with trend ETF group and small-cap observation
6. WHEN the System classifies composite regime as "broad_weakness_hold", THE System SHALL recommend defensive positioning with stock-bond balance and all-weather groups
7. WHEN the System generates strategy mapping, THE System SHALL output a list of recommended strategy groups with allocation weight suggestions

### Requirement 21: Integration with Existing Components

**User Story:** As a system maintainer, I want the diagnostic system to integrate seamlessly with existing components, so that I can leverage existing infrastructure.

#### Acceptance Criteria

1. WHEN the System initializes, THE System SHALL reuse DataFetcherManager from base.py for data fetching
2. WHEN the System fetches index data, THE System SHALL call DataFetcherManager.get_main_indices()
3. WHEN the System fetches market statistics, THE System SHALL call DataFetcherManager.get_market_stats()
4. WHEN the System fetches sector rankings, THE System SHALL call DataFetcherManager.get_sector_rankings()
5. WHEN the System fetches data via AkShare, THE System SHALL reuse AkShare interfaces from akshare_fetcher.py
6. WHERE LLM narrative generation is enabled, THE System SHALL call GeminiAnalyzer.generate_text() from analyzer.py
7. WHEN MarketAnalyzer is initialized with enable_diagnostic=True, THE System SHALL instantiate MarketDiagnosticEngine
8. WHEN MarketAnalyzer.run_full_analysis() is called with diagnostic enabled, THE System SHALL execute the full diagnostic workflow and return the Markdown report

### Requirement 22: Data Quality and Error Handling

**User Story:** As a system operator, I want the system to handle data quality issues gracefully, so that partial data failures do not block the entire diagnostic process.

#### Acceptance Criteria

1. WHEN the Data_Layer encounters a data fetching error, THE System SHALL log the error with timestamp and data source information
2. WHEN the Data_Layer encounters missing data for a non-critical indicator, THE System SHALL continue processing and mark the indicator as unavailable
3. WHEN the Data_Layer encounters missing data for a critical indicator (e.g., index prices), THE System SHALL attempt to use cached data from the previous trading day
4. WHEN the Feature_Layer encounters insufficient historical data for indicator calculation, THE System SHALL skip that indicator and add it to the missing_data list
5. WHEN the State_Layer encounters missing features, THE System SHALL classify states using available features and reduce confidence score accordingly
6. WHEN the Report_Layer generates output with missing data, THE System SHALL include a missing_data section listing all unavailable indicators
7. WHEN the System completes execution with partial data, THE System SHALL set confidence score to reflect data completeness

### Requirement 23: Performance and Caching

**User Story:** As a system operator, I want the system to execute efficiently, so that daily diagnostic reports can be generated within reasonable time.

#### Acceptance Criteria

1. WHEN the Data_Layer fetches data that was previously fetched for the same date, THE System SHALL use cached data instead of making redundant API calls
2. WHEN the Data_Layer caches data, THE System SHALL store data with date-based keys for efficient retrieval
3. WHEN the Feature_Layer calculates indicators, THE System SHALL use vectorized operations (numpy/pandas) for computational efficiency
4. WHEN the System processes 31 sectors, THE System SHALL calculate sector features in parallel where possible
5. WHEN the System completes a full diagnostic run, THE execution time SHALL be less than 60 seconds for a single trading day analysis

### Requirement 24: Configuration Management

**User Story:** As a system administrator, I want the system to support configuration management, so that I can adjust thresholds and parameters without code changes.

#### Acceptance Criteria

1. THE System SHALL define index pool configuration containing all 9 core indices with codes and names
2. THE System SHALL define style pair configuration for relative strength calculations
3. THE System SHALL define Shenwan Level-1 industry code list
4. THE System SHALL define threshold configurations for state classification (e.g., breadth state thresholds: 0.20, 0.35, 0.55, 0.70)
5. THE System SHALL define weight configurations for composite score calculations
6. WHERE configuration values are modified, THE System SHALL apply new configurations on the next execution without requiring code redeployment

### Requirement 25: Extensibility for Future Enhancements

**User Story:** As a product owner, I want the system architecture to support future enhancements, so that I can add new dimensions and features incrementally.

#### Acceptance Criteria

1. THE System architecture SHALL separate data, feature, diagnostic, state, and report layers to enable independent enhancement
2. WHEN a new diagnostic dimension is added, THE System SHALL allow adding new feature calculators without modifying existing ones
3. WHEN a new state classification is added, THE System SHALL allow adding new state classifiers without modifying existing ones
4. WHEN a new data source is added, THE System SHALL allow adding new data fetchers by implementing the data fetcher interface
5. WHEN a new output format is required, THE System SHALL allow adding new report renderers without modifying existing ones
6. THE System SHALL support adding intraday diagnostic capabilities (10:30, 11:30, 14:00, 14:45 snapshots) in future phases without architectural changes
