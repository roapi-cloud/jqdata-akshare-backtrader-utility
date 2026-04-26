# 大盘全维度诊断系统 — 技术设计文档

## 1. 系统概述

本系统在 `daily_stock_analysis` 现有架构基础上，新增一套**全维度市场诊断引擎**，将当前"文章式复盘"升级为"结构化诊断机"。

**核心目标**：每个交易日盘后，自动输出：
- 一份面向人的 Markdown 诊断报告（含量化证据）
- 一份面向策略系统的结构化 JSON（含 Regime 状态）

---

## 2. 高层架构（High-Level Design）

### 2.1 五层架构

```
daily_stock_analysis/
└── src/
    └── market_diagnostic/          ← 新增模块（本系统）
        ├── data/                   # 数据层：拉取、缓存、清洗
        ├── features/               # 特征层：指标计算
        ├── diagnostics/            # 诊断层：维度分析
        ├── states/                 # 状态层：Regime 分类
        └── reports/                # 报告层：输出渲染
```

### 2.2 数据流

```
DataLayer
  ├── IndexDataFetcher        → 指数日线（9支宽基）
  ├── BreadthDataFetcher      → 全市场个股截面
  ├── SentimentDataFetcher    → 涨停池/跌停池/炸板
  ├── SectorDataFetcher       → 申万一级行业
  ├── CapitalFlowFetcher      → 北向/融资/主力资金
  └── MacroDataFetcher        → 债券/汇率/商品
        ↓
FeatureLayer
  ├── TrendFeatures           → MA排列/MACD/RSRS/ATR
  ├── BreadthFeatures         → 站上MA20比例/新高比例/AD线
  ├── SentimentFeatures       → 涨停率/封板率/情绪综合分
  ├── StyleFeatures           → 大小盘RS/成长价值RS
  ├── SectorFeatures          → 行业强度分/持续性分/拥挤度
  ├── CapitalFeatures         → 成交额偏离/北向5日均
  └── RiskFeatures            → 已实现波动率/回撤/C-VIX代理
        ↓
DiagnosticLayer
  ├── IndexDiagnostic         → 趋势方向/结构背离/支撑压力
  ├── BreadthDiagnostic       → 广度健康度/扩散性
  ├── SentimentDiagnostic     → 情绪温度/赚钱效应
  ├── StyleDiagnostic         → 风格标签/切换信号
  ├── SectorDiagnostic        → 主线识别/板块分类
  ├── CapitalDiagnostic       → 增量/存量/方向
  └── RiskDiagnostic          → 风险水平/风险标志位
        ↓
StateLayer
  ├── TrendState              → 5档：强趋势上行→破位下行
  ├── BreadthState            → 5档：极弱→过热
  ├── SentimentState          → 5档：冰点→狂热
  ├── StyleState              → 5档：大盘防守→风格冲突
  ├── SectorState             → 5档：无主线→退潮分化
  ├── RiskState               → 4档：低风险→极端风险
  └── CompositeRegime         → 7种综合状态
        ↓
ReportLayer
  ├── MarkdownRenderer        → 面向人的复盘报告
  └── JsonExporter            → 面向策略系统的结构化输出
```

### 2.3 与现有代码的集成点

| 现有组件 | 集成方式 |
|---------|---------|
| `data_provider/base.py` DataFetcherManager | 复用 get_main_indices()、get_market_stats()、get_sector_rankings() |
| `src/market_analyzer.py` MarketAnalyzer | 扩展：在 generate_market_review() 前注入诊断结果 |
| `src/market_analyzer.py` MarketOverview | 扩展字段：增加 diagnostic_result |
| `data_provider/akshare_fetcher.py` | 复用 AkShare 接口拉取北向/融资/行业数据 |
| `src/analyzer.py` GeminiAnalyzer.generate_text() | 复用 LLM 调用生成叙述性报告段落 |

### 2.4 实施阶段

| 阶段 | 目标 | 范围 |
|------|------|------|
| P0 | 结构化复盘 | 指数+广度+情绪+风格+板块+资金，输出结构化字段 |
| P1 | Regime 诊断器 | 子状态+综合Regime+打分体系 |
| P2 | 板块/风格深化 | 行业强度表+风格轮动表+持续性分析 |
| P3 | 策略映射+验证 | Regime→策略组映射+历史状态切片验证 |

---

## 3. 低层设计（Low-Level Design）

### 3.1 目录结构

```
src/market_diagnostic/
├── __init__.py
├── engine.py                    # 主入口 MarketDiagnosticEngine
├── config.py                    # 指数池、行业代码、阈值配置
├── data/
│   ├── __init__.py
│   ├── models.py                # 数据类：IndexDailyData, MarketBreadthData 等
│   └── fetchers.py              # DiagnosticDataFetcher
├── features/
│   ├── __init__.py
│   ├── trend.py                 # TrendFeatures, compute_trend_features()
│   ├── breadth.py               # BreadthFeatures, compute_breadth_features()
│   ├── sentiment.py             # SentimentFeatures
│   ├── style.py                 # StyleFeatures
│   ├── sector.py                # SectorFeatureResult, compute_sector_strength_score()
│   ├── capital.py               # CapitalFeatures
│   └── risk.py                  # RiskFeatures
├── states/
│   ├── __init__.py
│   ├── enums.py                 # TrendState, BreadthState 等枚举
│   └── classifier.py            # MarketStateClassifier, MarketStateResult
└── reports/
    ├── __init__.py
    ├── schema.py                # DiagnosticReport dataclass
    ├── markdown_renderer.py     # DiagnosticMarkdownRenderer
    └── json_exporter.py         # to_json()
```

### 3.2 数据层核心类

```python
# src/market_diagnostic/data/models.py

@dataclass
class IndexDailyData:
    code: str
    name: str
    date: str
    close: float
    open: float
    high: float
    low: float
    prev_close: float
    volume: float
    amount: float           # 成交额（元）
    change_pct: float
    close_series: List[float] = field(default_factory=list)   # 近60日收盘价
    volume_series: List[float] = field(default_factory=list)  # 近60日成交量

@dataclass
class MarketBreadthData:
    date: str
    up_count: int
    down_count: int
    flat_count: int
    limit_up_count: int
    limit_down_count: int
    explode_count: int        # 炸板家数
    seal_rate: float          # 封板率 = 涨停/(涨停+炸板)
    continuous_limit_up: int  # 连板家数（2板以上）
    above_ma20_ratio: float   # 站上MA20个股比例（0-1）
    above_ma60_ratio: float
    new_high_count: int       # 创20日新高家数
    new_low_count: int
    total_amount: float       # 两市成交额（亿元）
    amount_ma5: float         # 5日均量（亿元）
    amount_ma20: float        # 20日均量（亿元）

@dataclass
class SectorDailyData:
    date: str
    industry_code: str
    industry_name: str
    ret_1d: float
    ret_5d: float
    ret_20d: float
    excess_ret_1d: float      # 相对沪深300超额
    breadth_20: float         # 行业内站上MA20比例
    new_high_ratio: float
    amount: float             # 行业成交额（亿元）
    amount_share: float       # 行业成交额占比
    amount_share_delta: float # 成交额占比变化（vs 5日均）
    limit_up_count: int
    turnover: float           # 行业换手率

@dataclass
class CapitalFlowData:
    date: str
    north_net_flow: float     # 北向净流入（亿元），T+1数据
    north_5d_avg: float
    margin_balance: float     # 融资余额（亿元），T+1数据
    margin_delta: float
    main_net_flow: float      # 主力净流入（亿元）
    etf_net_flow: float       # ETF净申购代理
    data_freshness: Dict[str, str]  # 各字段数据时效说明
```

### 3.3 特征层核心函数签名

```python
# src/market_diagnostic/features/trend.py

@dataclass
class TrendFeatures:
    code: str
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    ma120: float
    ma_alignment: str          # "多头排列" / "空头排列" / "缠绕"
    bias_ma5: float            # (close - ma5) / ma5
    bias_ma20: float
    bias_ma60: float
    macd_dif: float
    macd_dea: float
    macd_bar: float
    macd_signal: str           # "金叉" / "死叉" / "中性"
    atr_20: float
    rsrs_score: float          # 标准化RSRS分数（0-1）
    near_high_20d: bool
    break_support: bool
    rs_vs_300: float           # 相对沪深300相对强弱

def compute_trend_features(data: IndexDailyData) -> TrendFeatures:
    """使用 numpy 计算，不依赖 ta-lib"""
    ...

# src/market_diagnostic/features/breadth.py

@dataclass
class BreadthFeatures:
    up_down_ratio: float
    limit_up_rate: float
    seal_rate: float
    above_ma20_ratio: float
    new_high_ratio: float
    amount_deviation_5d: float   # (amount - ma5) / ma5
    amount_deviation_20d: float
    breadth_score: float         # 0-100 综合广度分

def compute_breadth_features(data: MarketBreadthData) -> BreadthFeatures:
    ...

# src/market_diagnostic/features/sector.py

@dataclass
class SectorFeatureResult:
    industry_code: str
    industry_name: str
    strength_score: float      # 行业强度分（Z-score加权）
    persistence_score: float   # 行业持续性分
    crowding_score: float      # 行业拥挤度
    leadership_score: float    # 龙头带动分
    state: str                 # 主升趋势/趋势强化/震荡整理/超跌反弹/弱势退潮

def compute_sector_strength_score(
    sector: SectorDailyData,
    all_sectors: List[SectorDailyData]
) -> float:
    """
    strength_score =
        0.25 * z(ret_5d_excess) +
        0.20 * z(ret_20d_excess) +
        0.20 * z(breadth_20) +
        0.10 * z(new_high_ratio) +
        0.10 * z(amount_share_delta) +
        0.10 * z(leadership_score) -
        0.05 * z(crowding_score)
    """
    ...
```

### 3.4 状态层枚举与分类器

```python
# src/market_diagnostic/states/enums.py

class TrendState(str, Enum):
    STRONG_UP = "强趋势上行"
    PULLBACK_IN_UPTREND = "趋势上行中的回调"
    RANGING = "震荡"
    WEAKENING = "趋势转弱"
    BREAKDOWN = "破位下行"

class BreadthState(str, Enum):
    EXTREME_WEAK = "极弱"      # above_ma20 < 20%
    WEAK = "偏弱"              # 20-35%
    NEUTRAL = "中性"           # 35-55%
    STRONG = "偏强"            # 55-70%
    OVERHEATED = "过热"        # > 70%

class SentimentState(str, Enum):
    FROZEN = "冰点"
    WARMING = "回暖"
    NEUTRAL = "中性"
    ACTIVE = "活跃"
    EUPHORIC = "狂热"

class StyleState(str, Enum):
    LARGE_CAP_DEFENSIVE = "大盘防守"
    SMALL_CAP_OFFENSIVE = "小盘进攻"
    GROWTH_DOMINANT = "成长主导"
    DIVIDEND_DEFENSIVE = "红利防守"
    STYLE_CONFLICT = "风格冲突"

class SectorState(str, Enum):
    NO_THEME = "无主线"
    SINGLE_THEME = "单主线"
    DUAL_THEME = "双主线并行"
    FAST_ROTATION = "高速轮动"
    FADING = "退潮分化"

class RiskState(str, Enum):
    LOW = "低风险"
    NEUTRAL = "中性风险"
    HIGH = "高风险"
    EXTREME = "极端风险"

class CompositeRegime(str, Enum):
    TREND_RISK_ON_GROWTH = "trend_risk_on_growth"
    TREND_RISK_ON_SMALLCAP = "trend_risk_on_smallcap"
    BALANCED_ROTATION = "balanced_rotation"
    DEFENSIVE_DIVIDEND = "defensive_dividend"
    HIGH_VOL_WARNING = "high_volatility_warning"
    PANIC_BOTTOMING = "panic_bottoming"
    BROAD_WEAKNESS_HOLD = "broad_weakness_hold"

# src/market_diagnostic/states/classifier.py

@dataclass
class MarketStateResult:
    date: str
    trend_state: TrendState
    breadth_state: BreadthState
    sentiment_state: SentimentState
    style_state: StyleState
    sector_state: SectorState
    risk_state: RiskState
    composite_regime: CompositeRegime
    trend_score: float
    breadth_score: float
    sentiment_score: float
    risk_score: float
    regime_score: float        # 0.20*trend + 0.15*breadth + 0.15*sentiment + 0.15*style + 0.15*sector - 0.20*risk
    key_evidence: List[str]    # 3条关键支持证据
    counter_evidence: List[str]
    confidence: float          # 0-1
    risk_flags: List[str]      # vol_spike / breadth_collapse / northbound_outflow 等
    missing_data: List[str]

class MarketStateClassifier:
    def classify(
        self,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
    ) -> MarketStateResult: ...

    def _classify_trend(self, features: Dict[str, TrendFeatures]) -> TrendState:
        """
        基于沪深300(sh000300)判断：
        - 强趋势上行：MA5>MA10>MA20>MA60 且 MACD金叉 且 RSRS>0.7
        - 趋势上行中的回调：多头排列但MA5<MA10
        - 震荡：均线缠绕，MACD在零轴附近
        - 趋势转弱：MA5<MA10<MA20 或 MACD死叉
        - 破位下行：跌破MA60 且 RSRS<0.3
        """
        ...

    def _classify_breadth(self, f: BreadthFeatures) -> BreadthState:
        r = f.above_ma20_ratio
        if r < 0.20: return BreadthState.EXTREME_WEAK
        if r < 0.35: return BreadthState.WEAK
        if r < 0.55: return BreadthState.NEUTRAL
        if r < 0.70: return BreadthState.STRONG
        return BreadthState.OVERHEATED

    def _classify_composite(
        self,
        trend: TrendState,
        breadth: BreadthState,
        sentiment: SentimentState,
        style: StyleState,
        sector: SectorState,
        risk: RiskState,
    ) -> CompositeRegime:
        """
        映射规则（优先级从高到低）：
        1. risk==EXTREME → HIGH_VOL_WARNING
        2. breadth==EXTREME_WEAK and sentiment==FROZEN → PANIC_BOTTOMING
        3. trend in (BREAKDOWN, WEAKENING) and breadth in (EXTREME_WEAK, WEAK) → BROAD_WEAKNESS_HOLD
        4. trend==STRONG_UP and style==GROWTH_DOMINANT → TREND_RISK_ON_GROWTH
        5. trend==STRONG_UP and style==SMALL_CAP_OFFENSIVE → TREND_RISK_ON_SMALLCAP
        6. style==DIVIDEND_DEFENSIVE → DEFENSIVE_DIVIDEND
        7. default → BALANCED_ROTATION
        """
        ...

    def _compute_confidence(self, missing_data: List[str], states: List) -> float:
        """
        base = 1.0
        - 每缺失一个核心指标: -0.15
        - 各维度信号一致（trend/breadth/sentiment同向）: +0.10
        - 存在极端异常值: -0.10
        - 依赖估计/代理数据: -0.05/项
        clamp to [0.1, 1.0]
        """
        ...
```

### 3.5 报告层

```python
# src/market_diagnostic/reports/schema.py

@dataclass
class DiagnosticReport:
    """面向策略系统的结构化 JSON 输出"""
    date: str
    # 状态
    trend_state: str
    breadth_state: str
    sentiment_state: str
    style_state: str
    sector_state: str
    risk_state: str
    composite_regime: str
    # 评分
    trend_score: float
    breadth_score: float
    sentiment_score: float
    risk_score: float
    regime_score: float
    # 详细数据
    indices: List[Dict]           # 指数行情 + 技术指标
    breadth_metrics: Dict         # 广度指标
    sentiment_metrics: Dict       # 情绪指标
    style_metrics: Dict           # 风格相对强弱
    sector_table: List[Dict]      # 行业诊断表（含strength_score等）
    capital_metrics: Dict         # 资金流指标
    risk_flags: List[str]         # 风险标志位
    # 结论
    one_sentence_summary: str
    key_evidence: List[str]
    counter_evidence: List[str]
    strategy_mapping: List[Dict]  # Regime→策略组映射
    confidence: float
    missing_data: List[str]

    def to_json(self) -> str:
        from dataclasses import asdict
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

# src/market_diagnostic/reports/markdown_renderer.py

class DiagnosticMarkdownRenderer:
    """
    输出格式（先结构化，后叙述）：

    ## {date} 大盘全维度诊断

    ### 🎯 一句话结论
    {one_sentence_summary}

    ### 📊 状态仪表盘
    | 维度 | 状态 | 得分 |
    综合 Regime: **{composite_regime}**

    ### 📈 指数与价格结构
    {indices_table with MA/MACD/ATR}

    ### 🌊 市场广度
    {breadth_table: 上涨/下跌/涨停/封板率/MA20比例/新高比例/成交额偏离}

    ### ��️ 情绪与赚钱效应
    {sentiment_table}

    ### 🔄 风格轮动
    {style_table: 大小盘RS/成长价值RS/风格标签}

    ### 🏭 板块主线诊断
    {sector_table: TOP5强势行业 with strength_score/state/amount_share}

    ### 💰 资金流向
    {capital_table: 成交额偏离/北向/融资/主力}

    ### ⚠️ 风险警报
    {risk_flags list}

    ### 🗺️ 策略映射建议
    {strategy_mapping table}

    ### 📝 证据与置信度
    支持证据 | 反向证据 | 置信度: {confidence:.0%}

    ---
    {llm_narrative}  ← LLM生成的叙述性分析（可选）
    """

    def render(self, report: DiagnosticReport, llm_narrative: str = "") -> str: ...
```

### 3.6 主引擎

```python
# src/market_diagnostic/engine.py

class MarketDiagnosticEngine:
    def __init__(
        self,
        data_manager: DataFetcherManager,
        analyzer=None,
        enable_llm_narrative: bool = True,
    ):
        self.fetcher = DiagnosticDataFetcher(data_manager)
        self.classifier = MarketStateClassifier()
        self.renderer = DiagnosticMarkdownRenderer()
        self.analyzer = analyzer
        self.enable_llm_narrative = enable_llm_narrative

    def run(self, date: str = None) -> Tuple[DiagnosticReport, str]:
        """
        完整诊断流程：
        Step 1: 拉取数据（index_series / breadth / sector / capital）
        Step 2: 计算特征（trend / breadth / sentiment / style / sector / capital / risk）
        Step 3: 状态分类（MarketStateClassifier.classify()）
        Step 4: 构建结构化报告（DiagnosticReport）
        Step 5: 渲染 Markdown（可选接 LLM 叙述段落）
        Returns: (DiagnosticReport, markdown_str)
        """
        ...
```

### 3.7 MarketAnalyzer 集成

```python
# 修改 src/market_analyzer.py（向后兼容）

class MarketAnalyzer:
    def __init__(self, ..., enable_diagnostic: bool = False):
        ...
        self.diagnostic_engine = None
        if enable_diagnostic:
            from src.market_diagnostic.engine import MarketDiagnosticEngine
            self.diagnostic_engine = MarketDiagnosticEngine(
                data_manager=self.data_manager,
                analyzer=self.analyzer,
            )

    def run_full_analysis(self) -> Tuple[Optional[DiagnosticReport], str]:
        """
        新增方法，不破坏现有 generate_market_review()。
        enable_diagnostic=True 时走全维度诊断；
        否则降级到现有复盘流程。
        """
        if self.diagnostic_engine:
            return self.diagnostic_engine.run()
        overview = self.get_market_overview()
        news = self.search_market_news()
        return None, self.generate_market_review(overview, news)
```

---

## 4. 配置

```python
# src/market_diagnostic/config.py

INDEX_POOL = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000016": "上证50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
    "sh000852": "中证1000",
}

STYLE_PAIRS = [
    ("sh000016", "sz399006", "大盘vs创业板"),
    ("sh000300", "sh000852", "沪深300vs中证1000"),
    ("sh000905", "sh000852", "中证500vs中证1000"),
]

BREADTH_THRESHOLDS = {
    "extreme_weak": 0.20,
    "weak": 0.35,
    "neutral": 0.55,
    "strong": 0.70,
}

RISK_FLAGS = [
    "vol_spike",           # 已实现波动率 > 2倍历史均值
    "breadth_collapse",    # 站上MA20比例单日下降 > 10pct
    "sector_overcrowding", # 单行业成交额占比 > 历史均值 + 2σ
    "northbound_outflow",  # 北向连续3日净流出
    "leadership_breakdown",# 前5强势行业龙头股平均跌幅 > 2%
    "index_break_support", # 沪深300跌破MA60
]

REGIME_STRATEGY_MAPPING = {
    "trend_risk_on_growth":    ["趋势ETF组", "行业轮动组", "小市值进攻组"],
    "trend_risk_on_smallcap":  ["趋势ETF组", "小市值进攻组"],
    "balanced_rotation":       ["行业轮动组", "红利价值组", "股债平衡组"],
    "defensive_dividend":      ["红利价值组", "股债平衡组"],
    "high_volatility_warning": ["红利价值组", "股债平衡组", "全天候组"],
    "panic_bottoming":         ["趋势ETF组小仓试探"],
    "broad_weakness_hold":     ["股债平衡组", "全天候组", "高现金"],
}
```

---

## 5. 数据可用性与降级策略

| 数据项 | 理想来源 | 降级方案 | 影响维度 |
|--------|---------|---------|---------|
| 站上MA20比例 | 个股截面计算 | 用涨跌家数比代理 | 广度 |
| 北向资金 | AkShare北向接口 | 标注"T+1不可用"，置信度-0.10 | 资金 |
| 融资余额 | AkShare融资接口 | 标注"T+1不可用"，置信度-0.05 | 资金 |
| 炸板/封板率 | 涨停池数据 | 用涨停/跌停比代理 | 情绪 |
| 行业5日收益 | 行业历史日线 | 用当日收益代替，标注 | 板块 |
| C-VIX | 期权数据 | 用ATR代理，标注 | 风险 |

---

## 6. 属性正确性约束（用于 Property-Based Testing）

1. **广度状态单调性**：`above_ma20_ratio` 越高，`BreadthState` 档位越高（严格单调）
2. **置信度有界性**：`confidence` 始终在 `[0.1, 1.0]` 范围内
3. **Regime 完备性**：任意合法的 (TrendState, BreadthState, RiskState) 组合都能映射到一个 `CompositeRegime`
4. **强度分归一化**：`strength_score` 经 Z-score 标准化后，跨行业均值≈0，标准差≈1
5. **风险标志一致性**：`RiskState.EXTREME` 时，`risk_flags` 列表不为空
6. **报告完整性**：`DiagnosticReport.to_json()` 输出的 JSON 必须包含所有必填字段，且可被 schema 验证通过
