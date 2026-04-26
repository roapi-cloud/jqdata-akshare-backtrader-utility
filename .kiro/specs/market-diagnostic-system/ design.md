大盘全维度诊断系统 — 技术设计文档
1. 系统概述
本系统在 daily_stock_analysis 现有架构基础上，新增一套全维度市场诊断引擎，将当前"文章式复盘"升级为"结构化诊断机"。

核心目标：每个交易日盘后，自动输出：

一份面向人的 Markdown 诊断报告（含量化证据）
一份面向策略系统的结构化 JSON（含 Regime 状态）
2. 高层架构
2.1 五层架构
daily_stock_analysis/
└── src/
    └── market_diagnostic/          ← 新增模块（本系统）
        ├── data/                   # 数据层：拉取、缓存、清洗
        ├── features/               # 特征层：指标计算
        ├── diagnostics/            # 诊断层：维度分析
        ├── states/                 # 状态层：Regime 分类
        └── reports/                # 报告层：输出渲染
2.2 数据流
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
2.3 与现有代码的集成点
现有组件	集成方式
base.py
 DataFetcherManager	复用 get_main_indices()、get_market_stats()、get_sector_rankings()
market_analyzer.py
 MarketAnalyzer	扩展：在 generate_market_review() 前注入诊断结果
market_analyzer.py
 MarketOverview	扩展字段：增加 diagnostic_result
akshare_fetcher.py
复用 AkShare 接口拉取北向/融资/行业数据
analyzer.py
 GeminiAnalyzer.generate_text()	复用 LLM 调用生成叙述性报告段落
3. 低层设计
3.1 数据层
3.1.1 核心数据类
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
    amount: float          # 成交额（元）
    change_pct: float
    # 历史序列（用于指标计算）
    close_series: List[float] = field(default_factory=list)   # 近60日收盘价
    volume_series: List[float] = field(default_factory=list)  # 近60日成交量

@dataclass
class MarketBreadthData:
    date: str
    up_count: int           # 上涨家数
    down_count: int         # 下跌家数
    flat_count: int         # 平盘家数
    limit_up_count: int     # 涨停家数
    limit_down_count: int   # 跌停家数
    explode_count: int      # 炸板家数（涨停后跌破）
    seal_rate: float        # 封板率 = 涨停/(涨停+炸板)
    continuous_limit_up: int  # 连板家数（2板以上）
    above_ma20_ratio: float   # 站上MA20个股比例
    above_ma60_ratio: float   # 站上MA60个股比例
    new_high_count: int       # 创20日新高家数
    new_low_count: int        # 创20日新低家数
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
    new_high_ratio: float     # 行业内创新高比例
    amount: float             # 行业成交额（亿元）
    amount_share: float       # 行业成交额占比
    amount_share_delta: float # 成交额占比变化（vs 5日均）
    limit_up_count: int       # 行业内涨停数
    turnover: float           # 行业换手率

@dataclass
class CapitalFlowData:
    date: str
    north_net_flow: float     # 北向净流入（亿元），T+1数据
    north_5d_avg: float       # 北向5日均值
    margin_balance: float     # 融资余额（亿元），T+1数据
    margin_delta: float       # 融资余额变化
    main_net_flow: float      # 主力净流入（亿元）
    etf_net_flow: float       # ETF净申购代理（亿元）
3.1.2 数据获取器
# src/market_diagnostic/data/fetchers.py

class DiagnosticDataFetcher:
    """统一数据获取入口，复用 DataFetcherManager 并扩展诊断所需数据"""

    def __init__(self, data_manager: DataFetcherManager):
        self._dm = data_manager

    def fetch_index_series(self, codes: List[str], lookback: int = 60) -> Dict[str, IndexDailyData]:
        """拉取指数历史序列，用于计算MA/MACD/ATR等"""
        ...

    def fetch_breadth_data(self, date: str) -> MarketBreadthData:
        """
        拉取全市场广度数据
        数据源优先级：AkShare(东财) → Tushare → efinance
        注意：above_ma20_ratio 需要个股截面数据，计算成本较高，
              建议缓存或使用代理指标（如涨跌家数比）
        """
        ...

    def fetch_sector_data(self, date: str) -> List[SectorDailyData]:
        """
        拉取申万一级行业数据
        复用现有 get_sector_rankings()，扩展多日收益和广度字段
        """
        ...

    def fetch_capital_flow(self, date: str) -> CapitalFlowData:
        """
        拉取资金流数据
        注意：北向资金和融资余额为T+1数据，需标注数据时效
        """
        ...
3.2 特征层
3.2.1 趋势特征
# src/market_diagnostic/features/trend.py

@dataclass
class TrendFeatures:
    code: str
    # 均线
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    ma120: float
    ma_alignment: str          # "多头排列" / "空头排列" / "缠绕"
    # 乖离率
    bias_ma5: float            # (close - ma5) / ma5
    bias_ma20: float
    bias_ma60: float
    # MACD
    macd_dif: float
    macd_dea: float
    macd_bar: float            # 柱体
    macd_signal: str           # "金叉" / "死叉" / "中性"
    # ATR
    atr_20: float
    # RSRS（线性回归斜率比）
    rsrs_score: float          # 标准化后的RSRS分数
    # 突破状态
    near_high_20d: bool        # 是否接近20日高点（5%以内）
    break_support: bool        # 是否跌破关键支撑
    # 相对强弱
    rs_vs_300: float           # 相对沪深300的相对强弱比值

def compute_trend_features(data: IndexDailyData) -> TrendFeatures:
    """
    计算单个指数的趋势特征
    使用 pandas/numpy 计算，不依赖外部库
    """
    closes = np.array(data.close_series)
    ma5 = np.mean(closes[-5:])
    ma10 = np.mean(closes[-10:])
    ma20 = np.mean(closes[-20:])
    ma60 = np.mean(closes[-60:]) if len(closes) >= 60 else np.nan
    ...
3.2.2 广度特征
# src/market_diagnostic/features/breadth.py

@dataclass
class BreadthFeatures:
    # 直接来自 MarketBreadthData
    up_down_ratio: float       # 上涨/下跌家数比
    limit_up_rate: float       # 涨停率 = 涨停/总家数
    seal_rate: float           # 封板率
    above_ma20_ratio: float    # 站上MA20比例
    new_high_ratio: float      # 创新高比例
    # 计算得出
    amount_deviation_5d: float  # 成交额相对5日均值偏离度
    amount_deviation_20d: float # 成交额相对20日均值偏离度
    # 状态判断
    breadth_score: float        # 0-100综合广度分

def compute_breadth_features(data: MarketBreadthData) -> BreadthFeatures:
    ...
3.2.3 行业强度分
# src/market_diagnostic/features/sector.py

def compute_sector_strength_score(sector: SectorDailyData, all_sectors: List[SectorDailyData]) -> float:
    """
    行业强度分（Z-score加权）
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

def classify_sector_state(strength_score: float, persistence_score: float) -> str:
    """
    将行业分为5类：
    - 主升趋势：strength高 + persistence高
    - 趋势强化：strength高 + persistence中
    - 震荡整理：strength中
    - 超跌反弹：strength中 + ret_20d低（跌深后反弹）
    - 弱势退潮：strength低
    """
    ...

3.2.4 估值特征
# src/market_diagnostic/features/valuation.py

@dataclass
class ValuationFeatures:
    # 指数估值
    csi300_pe: float              # 沪深300市盈率
    csi300_pb: float              # 沪深300市净率
    csi300_pe_percentile: float   # PE历史分位数（0-1）
    csi300_pb_percentile: float   # PB历史分位数（0-1）
    csi500_pe: float              # 中证500市盈率
    csi500_pb: float              # 中证500市净率
    csi1000_pe: float             # 中证1000市盈率
    csi1000_pb: float             # 中证1000市净率
    
    # 股债收益差
    fed_spread: float             # FED模型：1/PE - 10Y国债收益率
    graham_index: float           # 格雷厄姆指数：PE * PB
    
    # 宏观锚
    bond_10y_yield: float         # 10年期国债收益率（%）
    bond_1y_yield: float          # 1年期国债收益率（%）
    term_spread: float            # 期限利差：10Y - 1Y
    credit_spread: float          # 信用利差（估算）
    usd_cny: float                # 美元兑人民币汇率
    
    # 估值状态
    valuation_level: str          # "低估" / "合理" / "高估" / "泡沫"
    risk_premium: float           # 风险溢价：1/PE - 无风险利率

def compute_valuation_features(
    index_data: Dict[str, IndexDailyData],
    valuation_data: Dict[str, float],
    macro_data: Dict[str, float]
) -> ValuationFeatures:
    """
    计算估值特征
    
    数据来源：
    - valuation_data: 来自 ak.stock_zh_index_value_csindex()
    - macro_data: 来自 ak.bond_zh_us_rate() 和 ak.currency_boc_sina()
    
    计算逻辑：
    1. 获取指数PE/PB
    2. 计算历史分位数（需要历史估值数据）
    3. 计算FED Spread = 1/PE - 国债收益率
    4. 计算格雷厄姆指数 = PE * PB
    5. 判断估值水平
    """
    # 获取沪深300估值
    csi300_pe = valuation_data.get('csi300_pe', 0)
    csi300_pb = valuation_data.get('csi300_pb', 0)
    
    # 计算FED Spread
    bond_10y = macro_data.get('bond_10y_yield', 0)
    fed_spread = (1 / csi300_pe * 100) - bond_10y if csi300_pe > 0 else 0
    
    # 计算格雷厄姆指数
    graham_index = csi300_pe * csi300_pb
    
    # 判断估值水平
    # 格雷厄姆建议：PE*PB < 22.5 为合理
    if graham_index < 15:
        valuation_level = "低估"
    elif graham_index < 22.5:
        valuation_level = "合理"
    elif graham_index < 35:
        valuation_level = "高估"
    else:
        valuation_level = "泡沫"
    
    return ValuationFeatures(
        csi300_pe=csi300_pe,
        csi300_pb=csi300_pb,
        fed_spread=fed_spread,
        graham_index=graham_index,
        bond_10y_yield=bond_10y,
        valuation_level=valuation_level,
        ...
    )

3.3 状态层
3.3.1 状态枚举
# src/market_diagnostic/states/enums.py

from enum import Enum

class TrendState(str, Enum):
    STRONG_UP = "强趋势上行"
    PULLBACK_IN_UPTREND = "趋势上行中的回调"
    RANGING = "震荡"
    WEAKENING = "趋势转弱"
    BREAKDOWN = "破位下行"

class BreadthState(str, Enum):
    EXTREME_WEAK = "极弱"
    WEAK = "偏弱"
    NEUTRAL = "中性"
    STRONG = "偏强"
    OVERHEATED = "过热"

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
3.3.2 状态分类器
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
    # 评分
    trend_score: float        # 0-100
    breadth_score: float
    sentiment_score: float
    risk_score: float         # 越高越危险
    regime_score: float       # 综合得分（仅用于排序）
    # 证据
    key_evidence: List[str]   # 支持结论的3条关键证据
    counter_evidence: List[str]  # 反向证据
    confidence: float         # 0-1 置信度
    risk_flags: List[str]     # 风险标志位列表
    missing_data: List[str]   # 缺失数据说明

class MarketStateClassifier:
    """将特征层输出映射为结构化状态"""

    def classify(
        self,
        trend_features: Dict[str, TrendFeatures],  # key=指数代码
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
    ) -> MarketStateResult:
        trend_state = self._classify_trend(trend_features)
        breadth_state = self._classify_breadth(breadth_features)
        sentiment_state = self._classify_sentiment(sentiment_features)
        style_state = self._classify_style(style_features)
        sector_state = self._classify_sector(sector_features)
        risk_state = self._classify_risk(risk_features, capital_features)
        composite = self._classify_composite(
            trend_state, breadth_state, sentiment_state,
            style_state, sector_state, risk_state
        )
        confidence = self._compute_confidence(...)
        return MarketStateResult(...)

    def _classify_trend(self, features: Dict[str, TrendFeatures]) -> TrendState:
        """
        基于沪深300和上证指数的均线排列、MACD、RSRS判断趋势状态
        规则：
        - 强趋势上行：MA5>MA10>MA20>MA60 且 MACD金叉 且 RSRS>0.7
        - 趋势上行中的回调：多头排列但短期回调（MA5<MA10但MA20向上）
        - 震荡：均线缠绕，MACD在零轴附近
        - 趋势转弱：MA5<MA10<MA20 或 MACD死叉
        - 破位下行：跌破MA60 且 RSRS<0.3
        """
        ...

    def _classify_breadth(self, features: BreadthFeatures) -> BreadthState:
        """
        基于站上MA20比例阈值判断：
        <20%→极弱, 20-35%→偏弱, 35-55%→中性, 55-70%→偏强, >70%→过热
        """
        ratio = features.above_ma20_ratio
        if ratio < 0.20: return BreadthState.EXTREME_WEAK
        if ratio < 0.35: return BreadthState.WEAK
        if ratio < 0.55: return BreadthState.NEUTRAL
        if ratio < 0.70: return BreadthState.STRONG
        return BreadthState.OVERHEATED

    def _classify_composite(self, *states) -> CompositeRegime:
        """
        综合状态映射规则：
        - 强趋势 + 偏强广度 + 成长/小盘风格 → trend_risk_on_growth/smallcap
        - 震荡 + 中性广度 → balanced_rotation
        - 趋势转弱 + 偏弱广度 + 红利风格 → defensive_dividend
        - 高风险/极端风险 → high_volatility_warning
        - 极弱广度 + 冰点情绪 → panic_bottoming
        - 破位下行 + 偏弱广度 → broad_weakness_hold
        """
        ...

    def _compute_confidence(self, ...) -> float:
        """
        置信度 = f(数据完整性, 信号一致性, 异常值检测)
        - 核心指标缺失：-0.2/项
        - 各维度信号一致：+0.1
        - 存在极端异常值：-0.1
        - 依赖估计数据：-0.05/项
        """
        ...
3.4 报告层
3.4.1 结构化 JSON 输出
# src/market_diagnostic/reports/schema.py

@dataclass
class DiagnosticReport:
    """面向策略系统的结构化输出"""
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
    indices: List[Dict]          # 指数行情 + 技术指标
    breadth_metrics: Dict        # 广度指标
    sentiment_metrics: Dict      # 情绪指标
    style_metrics: Dict          # 风格相对强弱
    sector_table: List[Dict]     # 行业诊断表（含strength_score等）
    capital_metrics: Dict        # 资金流指标
    risk_flags: List[str]        # 风险标志位
    # 结论
    one_sentence_summary: str    # 一句话结论
    key_evidence: List[str]      # 3条关键证据
    counter_evidence: List[str]  # 反向证据
    strategy_mapping: List[Dict] # 策略组映射建议
    confidence: float            # 0-1 置信度
    missing_data: List[str]      # 缺失数据说明

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)
3.4.2 Markdown 报告渲染
# src/market_diagnostic/reports/markdown_renderer.py

class DiagnosticMarkdownRenderer:
    """
    渲染面向人的诊断报告
    结构：先结构化数据表，后叙述性分析
    """

    def render(self, report: DiagnosticReport, llm_narrative: str = "") -> str:
        """
        输出格式：
        ## {date} 大盘全维度诊断

        ### 🎯 一句话结论
        {one_sentence_summary}

        ### 📊 状态仪表盘
        | 维度 | 状态 | 得分 |
        |------|------|------|
        | 趋势 | {trend_state} | {trend_score} |
        ...
        综合 Regime: **{composite_regime}**

        ### 📈 指数与价格结构
        {indices_table}

        ### 🌊 市场广度
        {breadth_table}

        ### 🌡️ 情绪与赚钱效应
        {sentiment_table}

        ### 🔄 风格轮动
        {style_table}

        ### 🏭 板块主线诊断
        {sector_table}

        ### 💰 资金流向
        {capital_table}

        ### ⚠️ 风险警报
        {risk_flags}

        ### 🗺️ 策略映射建议
        {strategy_mapping}

        ### 📝 证据与置信度
        支持证据：{key_evidence}
        反向证据：{counter_evidence}
        置信度：{confidence}

        ---
        {llm_narrative}  ← 可选：LLM生成的叙述性分析
        """
        ...
3.5 主入口
# src/market_diagnostic/engine.py

class MarketDiagnosticEngine:
    """
    诊断引擎主入口
    协调数据层→特征层→诊断层→状态层→报告层的完整流程
    """

    def __init__(
        self,
        data_manager: DataFetcherManager,
        analyzer=None,           # 可选：GeminiAnalyzer，用于生成叙述段落
        enable_llm_narrative: bool = True,
    ):
        self.fetcher = DiagnosticDataFetcher(data_manager)
        self.classifier = MarketStateClassifier()
        self.renderer = DiagnosticMarkdownRenderer()
        self.analyzer = analyzer
        self.enable_llm_narrative = enable_llm_narrative

    def run(self, date: str = None) -> Tuple[DiagnosticReport, str]:
        """
        执行完整诊断流程
        Returns: (structured_report, markdown_report)
        """
        date = date or datetime.now().strftime('%Y-%m-%d')

        # Step 1: 拉取数据
        index_data = self.fetcher.fetch_index_series(INDEX_POOL, lookback=60)
        breadth_data = self.fetcher.fetch_breadth_data(date)
        sector_data = self.fetcher.fetch_sector_data(date)
        capital_data = self.fetcher.fetch_capital_flow(date)

        # Step 2: 计算特征
        trend_features = {code: compute_trend_features(d) for code, d in index_data.items()}
        breadth_features = compute_breadth_features(breadth_data)
        sentiment_features = compute_sentiment_features(breadth_data)
        style_features = compute_style_features(index_data)
        sector_features = [compute_sector_features(s, sector_data) for s in sector_data]
        capital_features = compute_capital_features(capital_data)
        risk_features = compute_risk_features(index_data, breadth_data)

        # Step 3: 状态分类
        state_result = self.classifier.classify(
            trend_features, breadth_features, sentiment_features,
            style_features, sector_features, capital_features, risk_features
        )

        # Step 4: 生成结构化报告
        structured_report = self._build_structured_report(date, state_result, ...)

        # Step 5: 渲染 Markdown（可选接 LLM 叙述）
        llm_narrative = ""
        if self.enable_llm_narrative and self.analyzer:
            llm_narrative = self._generate_llm_narrative(structured_report)
        markdown_report = self.renderer.render(structured_report, llm_narrative)

        return structured_report, markdown_report
3.6 与 MarketAnalyzer 的集成
# 修改 src/market_analyzer.py

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

    def run_full_analysis(self) -> str:
        """
        新增方法：运行完整诊断（替代或增强现有 generate_market_review）
        """
        overview = self.get_market_overview()
        news = self.search_market_news()

        if self.diagnostic_engine:
            # 全维度诊断模式
            structured, markdown = self.diagnostic_engine.run()
            return markdown
        else:
            # 降级到现有复盘模式
            return self.generate_market_review(overview, news)
4. 指数池配置

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

# 风格对比对
STYLE_PAIRS = [
    ("sh000016", "sz399006", "大盘vs创业板"),
    ("sh000300", "sh000852", "沪深300vs中证1000"),
    ("sh000905", "sh000852", "中证500vs中证1000"),
]

# 申万一级行业代码（31个）
SW_INDUSTRY_CODES = [
    "801010", "801020", "801030", ...  # 完整列表
]

## 5. 数据源与接口映射

### 5.1 AkShare接口清单

本系统所需数据均可通过AkShare获取，以下是详细的接口映射：

#### 5.1.1 已验证可用接口

| 数据类型 | AkShare接口 | 返回字段 | 用途 |
|---------|------------|---------|------|
| A股日线 | `ak.stock_zh_a_hist()` | 日期,开盘,收盘,最高,最低,成交量,成交额,涨跌幅 | 指数历史数据 |
| ETF日线 | `ak.fund_etf_hist_em()` | 日期,开盘,收盘,最高,最低,成交量,成交额,涨跌幅 | ETF历史数据 |
| 实时行情 | `ak.stock_zh_a_spot_em()` | 代码,名称,最新价,涨跌幅,成交量,成交额,量比,换手率,市盈率,市净率,总市值,流通市值 | 全市场实时数据 |
| 行业板块 | `ak.stock_board_industry_name_em()` | 板块名称,板块代码 | 行业列表 |
| 北向资金 | `ak.stock_hsgt_hist_em()` | 日期,当日成交净买额,当日资金流向 | 北向资金流入 |
| 融资融券 | `ak.stock_margin_detail_em()` | 日期,融资余额,融资买入额 | 融资余额数据 |

#### 5.1.2 需要验证的接口

| 数据类型 | AkShare接口 | 验证状态 | 备注 |
|---------|------------|---------|------|
| 涨停池 | `ak.stock_zt_pool_em()` | ⚠️ 需验证 | 涨停股票列表 |
| 跌停池 | `ak.stock_dt_pool_em()` | ⚠️ 需验证 | 跌停股票列表 |
| 行业日线 | `ak.stock_board_industry_hist_em()` | ⚠️ 需验证 | 行业指数历史数据 |
| 行业成分股 | `ak.stock_board_industry_cons_em()` | ⚠️ 需验证 | 行业成分股列表 |
| 行业资金流 | `ak.stock_sector_fund_flow_rank()` | ⚠️ 需验证 | 行业资金流排名 |
| 指数估值 | `ak.stock_zh_index_value_csindex()` | ⚠️ 需验证 | 中证指数PE/PB |
| 国债收益率 | `ak.bond_zh_us_rate()` | ⚠️ 需验证 | 中美国债收益率 |
| 汇率 | `ak.currency_boc_sina()` | ⚠️ 需验证 | 中国银行外汇牌价 |

#### 5.1.3 需要自行计算的指标

| 指标 | 计算方法 | 数据来源 |
|-----|---------|---------|
| 站上MA20比例 | 拉取全市场个股 + 计算MA20 | `ak.stock_zh_a_spot_em()` + 历史数据 |
| 创新高/新低比例 | 基于历史数据计算20日高低点 | 个股历史数据 |
| 行业内部广度 | 拉取行业成分股 + 计算个股指标 | `ak.stock_board_industry_cons_em()` |
| C-VIX | 基于期权数据计算隐含波动率 | `ak.option_finance_board()` |

### 5.2 数据获取策略

#### 5.2.1 分层缓存

```python
# 第一层：日线数据缓存（T日盘后拉取一次）
cache_daily = {
    'index_series': 60,      # 指数60天历史
    'sector_series': 60,     # 行业60天历史
    'northbound': 60,        # 北向60天历史
    'margin': 60,            # 融资60天历史
}

# 第二层：实时数据缓存（TTL=20分钟）
cache_realtime = {
    'market_snapshot': 1200,  # 全市场实时行情
    'etf_snapshot': 1200,     # ETF实时行情
}

# 第三层：计算结果缓存（T日盘后计算一次）
cache_computed = {
    'breadth_metrics': None,   # 市场广度指标
    'sector_strength': None,   # 行业强度分
    'style_rs': None,          # 风格相对强弱
}
```

#### 5.2.2 防封禁策略

```python
# 已在 AkshareFetcher 中实现
class DiagnosticDataFetcher:
    def __init__(self, data_manager: DataFetcherManager):
        self._dm = data_manager
        self.sleep_min = 2.0
        self.sleep_max = 5.0
    
    def _enforce_rate_limit(self):
        """随机休眠2-5秒"""
        time.sleep(random.uniform(self.sleep_min, self.sleep_max))
    
    def _set_random_user_agent(self):
        """随机轮换User-Agent"""
        random_ua = random.choice(USER_AGENTS)
        # 设置到requests session
```

#### 5.2.3 数据拉取优先级

**P0（核心数据，必须有）**：
1. 9支宽基指数日线
2. 全市场实时行情（用于统计广度）
3. 申万一级行业日线
4. 北向资金日线
5. 融资余额日线

**P1（重要数据，尽量有）**：
1. 涨停池/跌停池数据
2. 行业成分股列表
3. 行业资金流数据
4. 指数估值数据（PE/PB）

**P2（增强数据，可选）**：
1. 国债收益率
2. 汇率数据
3. 大宗商品价格
4. 期权数据（用于C-VIX）

### 5.3 数据质量保障

#### 5.3.1 数据清洗规则

```python
# 在 fetch_breadth_data() 中实现
def _filter_valid_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """过滤有效股票"""
    # 1. 排除ST股票
    df = df[~df['名称'].str.contains('ST|退')]
    
    # 2. 排除停牌股票
    df = df[df['成交量'] > 0]
    
    # 3. 排除次新股（上市60天内）
    df = df[df['上市天数'] > 60]
    
    # 4. 排除异常样本（涨跌幅>20%的非ST股）
    df = df[df['涨跌幅'].abs() <= 20]
    
    return df
```

#### 5.3.2 数据完整性检查

```python
def validate_data_completeness(self, date: str) -> Dict[str, bool]:
    """检查核心数据是否完整"""
    checks = {
        'index_data': len(self.index_data) == 9,
        'breadth_data': self.breadth_data is not None,
        'sector_data': len(self.sector_data) == 31,
        'capital_flow': self.capital_flow is not None,
    }
    
    missing = [k for k, v in checks.items() if not v]
    if missing:
        logger.warning(f"数据不完整: {missing}")
    
    return checks
```

#### 5.3.3 T+1数据标注

```python
@dataclass
class CapitalFlowData:
    date: str
    north_net_flow: float     # 北向净流入（亿元），T+1数据
    north_5d_avg: float       # 北向5日均值
    margin_balance: float     # 融资余额（亿元），T+1数据
    margin_delta: float       # 融资余额变化
    main_net_flow: float      # 主力净流入（亿元）
    etf_net_flow: float       # ETF净申购代理（亿元）
    
    # 数据时效标记
    data_lag: Dict[str, int] = field(default_factory=lambda: {
        'north_net_flow': 1,    # T+1
        'margin_balance': 1,    # T+1
        'main_net_flow': 0,     # T+0
        'etf_net_flow': 0,      # T+0
    })
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Historical Data Completeness

*For any* valid trading date, when the Data_Layer fetches index data, the historical price series SHALL contain at least 60 data points.

**Validates: Requirement 1.2**

### Property 2: Data Structure Completeness

*For any* market breadth data fetch, the returned data structure SHALL contain all required fields (up_count, down_count, limit_up_count, limit_down_count, explode_count, seal_rate, above_ma20_ratio, above_ma60_ratio) with non-null values.

**Validates: Requirement 1.3**

### Property 3: Sector Data Completeness

*For any* valid trading date, when the Data_Layer fetches sector data, the result SHALL contain data for all 31 Shenwan Level-1 industries.

**Validates: Requirement 1.4**

### Property 4: Capital Flow Data Structure

*For any* capital flow data fetch, the returned data structure SHALL contain all required fields (north_net_flow, margin_balance, main_net_flow, etf_net_flow) with appropriate values or null markers.

**Validates: Requirement 1.5**

### Property 5: Error Handling Continuity

*For any* data fetch operation that encounters missing or invalid data for non-critical indicators, the system SHALL log the error and continue processing with available data rather than terminating.

**Validates: Requirement 1.6, 22.1, 22.2**

### Property 6: Stock Filtering Consistency

*For any* stock list containing ST stocks, suspended stocks, newly listed stocks (within 60 days), or anomalous samples, the Data_Layer SHALL exclude these stocks from market breadth calculations.

**Validates: Requirement 1.7**

### Property 7: Moving Average Calculation Completeness

*For any* valid index data with sufficient historical data, the Feature_Layer SHALL calculate all five moving averages (MA5, MA10, MA20, MA60, MA120).

**Validates: Requirement 2.1**

### Property 8: MA Alignment Classification Validity

*For any* index data with calculated moving averages, the MA alignment status SHALL be classified as exactly one of three valid states: "多头排列", "空头排列", or "缠绕".

**Validates: Requirement 2.2**

### Property 9: MACD Calculation Completeness

*For any* valid index data with sufficient history, the Feature_Layer SHALL calculate all MACD components (DIF, DEA, BAR) and identify the signal state as one of "金叉", "死叉", or "中性".

**Validates: Requirement 2.3**

### Property 10: Technical Indicator Calculation

*For any* valid index data with at least 20 days of history, the Feature_Layer SHALL calculate RSRS score, ATR-20, and bias ratios for MA5, MA20, and MA60.

**Validates: Requirements 2.4, 2.5, 2.6**

### Property 11: Relative Strength Calculation

*For any* two valid indices with price data, the Feature_Layer SHALL calculate the relative strength ratio as the ratio of their closing prices.

**Validates: Requirement 2.7**

### Property 12: Breadth Metrics Calculation

*For any* valid market breadth data, the Feature_Layer SHALL calculate up/down ratio, limit-up rate, seal rate, MA penetration ratios, new high ratio, and turnover amount deviations.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

### Property 13: Breadth Score Range Constraint

*For any* valid breadth features, the composite breadth score SHALL be a value between 0 and 100 inclusive.

**Validates: Requirement 3.7**

### Property 14: Division by Zero Handling

*For any* breadth or sentiment data where the denominator in a ratio calculation equals zero, the system SHALL handle the division gracefully by returning a default value (e.g., 0 or null) rather than throwing an error.

**Validates: Requirements 3.3, 4.1**

### Property 15: Sentiment Metrics Calculation

*For any* valid sentiment data, the Feature_Layer SHALL calculate limit-up to limit-down ratio, continuous limit-up count, seal rate, and composite sentiment score.

**Validates: Requirements 4.1, 4.2, 4.3, 4.6**

### Property 16: Historical Context Calculation

*For any* valid sentiment data with T-1 historical data, the Feature_Layer SHALL calculate next-day premium for yesterday's limit-up stocks and turnover rate Z-score.

**Validates: Requirements 4.4, 4.5**

### Property 17: Style Relative Strength Calculation

*For any* valid style data containing the required indices, the Feature_Layer SHALL calculate relative strength ratios for all three style pairs (large-cap vs small-cap, 沪深300 vs 中证1000, 中证500 vs 中证1000).

**Validates: Requirements 5.1, 5.2, 5.3**

### Property 18: Multi-Period Return Calculation

*For any* valid style or sector data with sufficient history, the Feature_Layer SHALL calculate returns for 1-day, 5-day, and 20-day periods.

**Validates: Requirements 5.4, 6.1**

### Property 19: Style Classification Validity

*For any* valid style features, the dominant style SHALL be classified as exactly one of five valid states: "大盘防守", "小盘进攻", "成长主导", "红利防守", or "风格冲突".

**Validates: Requirement 5.6**

### Property 20: Sector Metrics Calculation

*For any* valid sector data with benchmark data, the Feature_Layer SHALL calculate excess returns, industry breadth, new high ratio, turnover metrics, limit-up count, and leadership score for each sector.

**Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6**

### Property 21: Sector Strength Score Formula

*For any* valid sector features and cross-sectional sector data, the sector strength score SHALL be calculated using the weighted Z-score formula: 0.25×z(ret_5d_excess) + 0.20×z(ret_20d_excess) + 0.20×z(breadth_20) + 0.10×z(new_high_ratio) + 0.10×z(amount_share_delta) + 0.10×z(leadership_score) - 0.05×z(crowding_score).

**Validates: Requirement 6.7**

### Property 22: Sector Persistence Score Calculation

*For any* valid sector features with at least 5 days of historical ranking data, the Feature_Layer SHALL compute a persistence score based on consecutive days in top-5 rankings and turnover amount share trends.

**Validates: Requirement 6.8**

### Property 23: Capital Flow Metrics Calculation

*For any* valid capital flow data with historical context, the Feature_Layer SHALL calculate total market turnover, turnover deviations from 5-day/20-day/60-day averages, North Bound Capital 5-day MA, margin balance changes, main force net flow, and ETF net flow.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**

### Property 24: T+1 Data Marking

*For any* capital flow data containing North Bound Capital or margin balance data, these fields SHALL be marked with time lag indicators to denote T+1 availability.

**Validates: Requirement 7.6**

### Property 25: Risk Metrics Calculation

*For any* valid risk data with at least 20 days of history, the Feature_Layer SHALL calculate realized volatility, ATR-based volatility, volatility ratio, index drawdown, cross-asset correlation, and sector correlation elevation.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

### Property 26: Optional Data Incorporation

*For any* risk assessment where C-VIX data is available, the system SHALL incorporate the volatility index readings; when C-VIX data is unavailable, the system SHALL continue processing without it and mark it as missing data.

**Validates: Requirement 8.7**

### Property 27: Trend State Classification Correctness

*For any* trend features meeting the specified threshold conditions (MA alignment, MACD signal, RSRS score), the State_Layer SHALL classify the trend state as the corresponding valid state ("强趋势上行", "趋势上行中的回调", "震荡", "趋势转弱", or "破位下行").

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

### Property 28: Trend Score Range Constraint

*For any* trend state classification, the trend score SHALL be a value between 0 and 100 inclusive.

**Validates: Requirement 9.6**

### Property 29: Breadth State Threshold Classification

*For any* breadth features with a given above_ma20_ratio value, the State_Layer SHALL classify the breadth state according to the threshold rules: <0.20→"极弱", [0.20,0.35)→"偏弱", [0.35,0.55)→"中性", [0.55,0.70)→"偏强", ≥0.70→"过热".

**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**

### Property 30: Breadth Score Range Constraint

*For any* breadth state classification, the breadth score SHALL be a value between 0 and 100 inclusive.

**Validates: Requirement 10.6**

### Property 31: Sentiment State Classification Correctness

*For any* sentiment features meeting the specified indicator conditions (limit-up rate, seal rate, next-day premium, continuous limit-ups), the State_Layer SHALL classify the sentiment state as the corresponding valid state ("冰点", "回暖", "中性", "活跃", or "狂热").

**Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**

### Property 32: Sentiment Score Range Constraint

*For any* sentiment state classification, the sentiment score SHALL be a value between 0 and 100 inclusive.

**Validates: Requirement 11.6**

### Property 33: Style State Classification Correctness

*For any* style features meeting the specified relative strength conditions, the State_Layer SHALL classify the style state as the corresponding valid state ("大盘防守", "小盘进攻", "成长主导", "红利防守", or "风格冲突").

**Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**

### Property 34: Sector State Classification Correctness

*For any* sector features meeting the specified strength and persistence conditions, the State_Layer SHALL classify the sector state as the corresponding valid state ("无主线", "单主线", "双主线并行", "高速轮动", or "退潮分化").

**Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5**

### Property 35: Risk State Classification Correctness

*For any* risk features meeting the specified volatility, drawdown, and risk flag conditions, the State_Layer SHALL classify the risk state as the corresponding valid state ("低风险", "中性风险", "高风险", or "极端风险").

**Validates: Requirements 14.1, 14.2, 14.3, 14.4**

### Property 36: Risk Flag Setting Correctness

*For any* risk features meeting specific risk conditions (volatility spike, breadth collapse, sector overcrowding, northbound outflow, leadership breakdown, index break support), the State_Layer SHALL set the corresponding risk flag.

**Validates: Requirements 14.5, 14.6, 14.7, 14.8, 14.9, 14.10**

### Property 37: Composite Regime Classification Correctness

*For any* combination of sub-states (trend, breadth, sentiment, style, sector, risk) meeting the specified conditions, the State_Layer SHALL classify the composite regime as the corresponding valid regime ("trend_risk_on_growth", "trend_risk_on_smallcap", "balanced_rotation", "defensive_dividend", "high_volatility_warning", "panic_bottoming", or "broad_weakness_hold").

**Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7**

### Property 38: Regime Score Formula and Range

*For any* valid state scores (trend_score, breadth_score, sentiment_score, style_score, sector_score, risk_score), the regime score SHALL be calculated using the formula (0.20×trend_score + 0.15×breadth_score + 0.15×sentiment_score + 0.15×style_score + 0.15×sector_score - 0.20×risk_score) and SHALL be a value between 0 and 100 inclusive.

**Validates: Requirement 15.8**

### Property 39: Individual Sector Classification Correctness

*For any* sector with given strength_score and persistence_score values, the sector SHALL be classified according to the rules: (strength>2.0 AND persistence>0.7)→"主升趋势", (strength>1.5 AND 0.4≤persistence<0.7)→"趋势强化", (-0.5≤strength≤1.5)→"震荡整理", (0.5<strength<1.5 AND ret_20d<-0.10)→"超跌反弹", (strength<-0.5)→"弱势退潮".

**Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**

### Property 40: Evidence Extraction Completeness

*For any* market state result, the State_Layer SHALL identify exactly 3 key supporting evidence items and a list of counter-evidence items.

**Validates: Requirements 17.1, 17.2**

### Property 41: Confidence Penalty for Missing Data

*For any* state calculation with N missing core indicators, the confidence score SHALL be reduced by 0.2×N from the base confidence.

**Validates: Requirement 17.3**

### Property 42: Confidence Boost for Signal Consistency

*For any* state calculation where signals across all dimensions are consistent, the confidence score SHALL be increased by 0.1.

**Validates: Requirement 17.4**

### Property 43: Confidence Penalty for Anomalies

*For any* state calculation where extreme anomalous values are detected, the confidence score SHALL be reduced by 0.1.

**Validates: Requirement 17.5**

### Property 44: Confidence Penalty for Estimated Data

*For any* state calculation with N data items relying on estimation or proxy, the confidence score SHALL be reduced by 0.05×N.

**Validates: Requirement 17.6**

### Property 45: Confidence Range Constraint

*For any* market state result, the confidence score SHALL be a value between 0 and 1 inclusive.

**Validates: Requirement 17.7**

### Property 46: JSON Output Structure Completeness

*For any* diagnostic result, the JSON output SHALL contain all required fields: date, all state classifications (trend_state, breadth_state, sentiment_state, style_state, sector_state, risk_state, composite_regime), all scores (trend_score, breadth_score, sentiment_score, risk_score, regime_score), indices array, breadth_metrics object, sentiment_metrics object, style_metrics object, sector_table array, capital_metrics object, risk_flags array, key_evidence array, counter_evidence array, confidence value, and missing_data array.

**Validates: Requirements 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8, 18.9, 18.10**

### Property 47: Markdown Report Structure Completeness

*For any* diagnostic result, the Markdown report SHALL contain all required sections: one-sentence summary, state dashboard table, index structure section, market breadth section, sentiment section, style rotation section, sector diagnosis section, capital flow section, risk alert section, strategy mapping section, and evidence & confidence section.

**Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7, 19.8, 19.9, 19.10, 19.11**

### Property 48: Strategy Mapping Correctness

*For any* composite regime classification, the System SHALL recommend the appropriate strategy groups according to the mapping rules: ("trend_risk_on_growth" OR "trend_risk_on_smallcap")→[trend ETF, sector rotation, small-cap offensive], "balanced_rotation"→[sector rotation, dividend value, stock-bond balance], "defensive_dividend"→[dividend value, stock-bond balance, all-weather], "high_volatility_warning"→[stock-bond balance, all-weather, high cash], "panic_bottoming"→[small position probing], "broad_weakness_hold"→[defensive positioning].

**Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7**

### Property 49: Error Logging and Continuation

*For any* data fetching error encountered by the Data_Layer, the system SHALL log the error with timestamp and data source information, and SHALL continue processing rather than terminating.

**Validates: Requirements 22.1, 22.2**

### Property 50: Graceful Degradation with Missing Data

*For any* feature calculation that encounters insufficient historical data, the system SHALL skip that specific indicator, add it to the missing_data list, and continue processing other indicators.

**Validates: Requirements 22.3, 22.4**

### Property 51: Confidence Adjustment for Data Completeness

*For any* state classification with missing features, the system SHALL classify states using available features and SHALL reduce the confidence score proportionally to reflect data incompleteness.

**Validates: Requirements 22.5, 22.6, 22.7**

### Property 52: Data Caching Efficiency

*For any* data fetch operation where data for the same date was previously fetched, the Data_Layer SHALL use cached data instead of making redundant API calls.

**Validates: Requirement 23.1**

### Property 53: Configuration Application

*For any* configuration value modification (thresholds, weights, index pool, style pairs, industry codes), the system SHALL apply the new configuration on the next execution without requiring code redeployment.

**Validates: Requirement 24.6**
