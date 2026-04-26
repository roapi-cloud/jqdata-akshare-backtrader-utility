# 技术指标与信号生成流水线 - 深度设计文档

> 基于对现有 6 个核心笔记本的逐行代码分析，覆盖所有边界情况、异常处理、参数调优、多时间框架融合等。

---

## 一、总体架构与数据流

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            SignalPipeline v2.0                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────────┐           │
│  │  DataLayer  │───▶│ IndicatorEngine  │───▶│ SignalGenerator   │           │
│  │             │    │                  │    │                   │           │
│  │ • OHLCV     │    │ • 缠论笔/线段     │    │ • 信号标准化       │           │
│  │ • 复权处理   │    │ • 圆弧底形态      │    │ • 强度归一化       │           │
│  │ • 缺失值填充 │    │ • MESA频谱分析    │    │ • 置信度计算       │           │
│  │ • 异常值检测 │    │ • RSRS择时       │    │ • 止损/止盈建议    │           │
│  │ • 多周期对齐 │    │ • 趋与势量化      │    │ • 元数据附加       │           │
│  │ • 停牌处理   │    │ • 拥挤率指标      │    │                   │           │
│  └─────────────┘    │ • 通达信公式集    │    └─────────┬─────────┘           │
│                     │ • 波动率/ATR     │              │                       │
│                     └────────┬─────────┘              ▼                       │
│                              │               ┌───────────────────┐           │
│                              ▼               │  SignalFusion     │           │
│                     ┌──────────────────┐     │                   │           │
│                     │ IndicatorRegistry│     │ • 加权投票         │           │
│                     │                  │     │ • 共识机制         │           │
│                     │ • 指标注册/发现   │     │ • 冲突消解         │           │
│                     │ • 参数管理       │     │ • 动态权重调整     │           │
│                     │ • 依赖图解析     │     │ • 市场环境判别     │           │
│                     │ • 缓存管理       │     │   (趋势/震荡)      │           │
│                     └──────────────────┘     └─────────┬─────────┘           │
│                                                        │                     │
│                                                        ▼                     │
│                                               ┌───────────────────┐          │
│                                               │  OutputLayer      │          │
│                                               │                   │          │
│                                               │ • CSV/JSON日志    │          │
│                                               │ • 可视化图表       │          │
│                                               │ • Backtrader适配  │          │
│                                               │ • 实时推送接口     │          │
│                                               └───────────────────┘          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、数据层 (DataLayer) - 深度设计

### 2.1 统一数据格式

```python
@dataclass
class MarketData:
    """统一市场数据容器，兼容所有指标输入需求"""
    
    # 核心 OHLCV
    datetime: pd.DatetimeIndex
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    
    # 扩展字段（按需填充）
    money: Optional[np.ndarray] = None      # 成交额（拥挤率需要）
    pre_close: Optional[np.ndarray] = None  # 昨收（RSRS需要）
    openinterest: Optional[np.ndarray] = None
    
    # 元数据
    symbol: str
    frequency: str = '1d'  # '1m', '5m', '15m', '30m', '60m', '1d', '1w'
    adjusted: str = 'qfq'  # None, 'qfq', 'hfq'
    
    # 数据质量标记
    is_suspended: Optional[np.ndarray] = None  # 停牌标记
    data_quality: DataQualityReport = None
```

### 2.2 数据预处理流水线

```python
class DataPreprocessor:
    """
    数据预处理流水线，处理所有边缘情况
    
    边界情况处理清单:
    1. 缺失值: 前向填充 > 线性插值 > 标记为无效
    2. 异常值: 3σ原则检测，用中位数替换
    3. 停牌日: volume=0 且 price 不变，标记 is_suspended
    4. 复权断裂: 检测复权因子跳变，重新计算
    5. 涨跌停: 价格触及涨跌停板时 volume 可能异常
    6. 新股上市: 前 N 日数据不稳定，需特殊标记
    7. 除权除息: 价格跳空非缺口，需与真实缺口区分
    """
    
    def preprocess(self, raw_data: pd.DataFrame) -> MarketData:
        # Step 1: 列名标准化
        raw_data = self._normalize_columns(raw_data)
        
        # Step 2: 时间索引处理
        raw_data = self._handle_datetime_index(raw_data)
        
        # Step 3: 停牌检测
        raw_data['is_suspended'] = self._detect_suspension(raw_data)
        
        # Step 4: 异常值检测与修正
        raw_data = self._detect_and_fix_outliers(raw_data)
        
        # Step 5: 缺失值处理
        raw_data = self._handle_missing_values(raw_data)
        
        # Step 6: 涨跌停检测
        raw_data['limit_up'] = self._detect_limit_up(raw_data)
        raw_data['limit_down'] = self._detect_limit_down(raw_data)
        
        # Step 7: 复权因子校验
        raw_data = self._validate_adjustment(raw_data)
        
        # Step 8: 计算衍生字段
        raw_data['pre_close'] = raw_data['close'].shift(1)
        raw_data['ret'] = raw_data['close'] / raw_data['pre_close'] - 1
        
        return MarketData.from_dataframe(raw_data)
    
    def _detect_suspension(self, df: pd.DataFrame) -> np.ndarray:
        """
        停牌检测逻辑:
        - volume == 0 且 high == low == open == close
        - 或者连续 N 日价格完全相同
        """
        vol_zero = df['volume'] == 0
        price_unchanged = (
            (df['high'] == df['low']) & 
            (df['low'] == df['open']) & 
            (df['open'] == df['close'])
        )
        return (vol_zero & price_unchanged).values
    
    def _detect_and_fix_outliers(self, df: pd.DataFrame, sigma: float = 3.0) -> pd.DataFrame:
        """
        异常值检测:
        - 使用滚动窗口计算均值和标准差
        - 超过 mean ± sigma*std 的视为异常
        - 用滚动中位数替换
        """
        window = 20
        for col in ['open', 'high', 'low', 'close', 'volume']:
            rolling_mean = df[col].rolling(window).mean()
            rolling_std = df[col].rolling(window).std()
            upper = rolling_mean + sigma * rolling_std
            lower = rolling_mean - sigma * rolling_std
            
            outlier_mask = (df[col] > upper) | (df[col] < lower)
            median = df[col].rolling(window).median()
            df.loc[outlier_mask, col] = median[outlier_mask]
        
        return df
```

### 2.3 多时间框架数据对齐

```python
class MultiTimeframeAligner:
    """
    多时间框架数据对齐器
    
    场景: 缠论需要日线识别线段，但 MESA 需要分钟线做频谱分析
    解决方案:
    1. 统一时间基准（以最小周期为准）
    2. 向上聚合（分钟→日线）时保持信息完整性
    3. 向下对齐（日线→分钟）时用前向填充
    """
    
    def align(self, data_dict: Dict[str, MarketData]) -> Dict[str, MarketData]:
        """
        对齐多个时间框架的数据
        
        Args:
            data_dict: {frequency: MarketData}
            
        Returns:
            对齐后的数据字典
        """
        # 找到共同的时间范围
        common_start = max(d.datetime.min() for d in data_dict.values())
        common_end = min(d.datetime.max() for d in data_dict.values())
        
        # 以最小周期为基准
        min_freq = min(data_dict.keys(), key=self._freq_to_minutes)
        base_data = data_dict[min_freq]
        
        aligned = {}
        for freq, data in data_dict.items():
            if freq == min_freq:
                aligned[freq] = self._trim_to_range(data, common_start, common_end)
            else:
                aligned[freq] = self._resample_and_align(
                    data, base_data.datetime, common_start, common_end
                )
        
        return aligned
```

---

## 三、指标引擎 (IndicatorEngine) - 逐个深度解析

### 3.1 缠论信号生成器 (ChanTheoryGenerator)

#### 3.1.1 原始代码核心逻辑分析

从 `16 研究 缠论工具（笔， 线段）.ipynb` 提取的关键流程:

```
原始K线 → 标准化(处理包含关系) → 标记顶底分型 → 定义笔 → 定义线段 → 信号识别
```

**关键边界情况:**

| 边界情况 | 原始代码处理方式 | 我们的增强处理 |
|----------|------------------|----------------|
| K线包含关系 | `checkInclusive()` 判断，按趋势方向合并 | 增加趋势方向推断的鲁棒性，处理连续包含 |
| 顶底分型间距 < 4根K线 | `clean_first_two_tb()` 清理 | 增加动态阈值，根据波动率调整最小间距 |
| 缺口处理 | `gap_exists()` 检测，`check_gap_qualify()` 验证 | 区分除权缺口与真实缺口，增加缺口回补检测 |
| 笔的破坏 | 回溯 `trace_back_index()` 重新判断 | 增加笔破坏的置信度衰减机制 |
| 线段被缺口升级 | `gap_XD` 列表记录 | 增加缺口线段的有效性验证 |
| 数据不足 7 根K线 | `markTopBot()` 直接返回 | 返回 `InsufficientDataError`，上层处理 |
| MACD 辅助判断 | `prepare_original_kdf()` 计算 MACD | 增加 MACD 背离检测，辅助判断买卖点 |

#### 3.1.2 完整信号定义

```python
class ChanSignalType(Enum):
    """缠论信号类型，覆盖所有买卖点"""
    
    # 一买/一卖（趋势转折）
    FIRST_BUY = "1B"       # 底分型确认，笔向上
    FIRST_SELL = "1S"      # 顶分型确认，笔向下
    
    # 二买/二卖（回踩确认）
    SECOND_BUY = "2B"      # 回踩不破前低，笔向上
    SECOND_SELL = "2S"     # 反弹不破前高，笔向下
    
    # 三买/三卖（趋势确认）
    THIRD_BUY = "3B"       # 回调不进入中枢，笔向上
    THIRD_SELL = "3S"      # 反弹不进入中枢，笔向下
    
    # 线段级别信号
    XD_BOTTOM = "XDB"      # 线段底确认
    XD_TOP = "XDT"         # 线段顶确认
    XD_BREAK_UP = "XDBU"   # 线段向上破坏
    XD_BREAK_DOWN = "XDBD" # 线段向下破坏
    
    # 中枢相关
    ZHONGSHU_FORMED = "ZS"      # 中枢形成
    ZHONGSHU_BREAK_UP = "ZSBU"  # 中枢向上突破
    ZHONGSHU_BREAK_DOWN = "ZSBD" # 中枢向下突破
    ZHONGSHU_THIRD_BUY = "ZS3B" # 中枢三买
    ZHONGSHU_THIRD_SELL = "ZS3S" # 中枢三卖
    
    # 背驰/背离
    DIVERGENCE_PRICE_MACD = "DIV_PM"  # 价格-MACD背离
    DIVERGENCE_TREND = "DIV_T"        # 趋势背驰
    DIVERGENCE_PANZHENG = "DIV_PZ"    # 盘整背驰


class ChanTheoryGenerator(BaseIndicatorGenerator):
    """
    缠论信号生成器 - 完整实现
    
    参数说明:
    - min_bi_kbars: 笔的最小K线数，默认4（缠论标准）
    - min_xd_bi_count: 线段的最小笔数，默认3
    - golden_ratio: 黄金分割比例，默认0.618
    - min_price_unit: 最小价格单位，默认0.01
    - use_macd_divergence: 是否使用MACD背离辅助判断
    - strict_mode: 严格模式（要求缺口验证）
    """
    
    name = "chan_theory"
    version = "2.0"
    
    def __init__(
        self,
        min_bi_kbars: int = 4,
        min_xd_bi_count: int = 3,
        golden_ratio: float = 0.618,
        min_price_unit: float = 0.01,
        use_macd_divergence: bool = True,
        strict_mode: bool = False,
        debug: bool = False
    ):
        self.min_bi_kbars = min_bi_kbars
        self.min_xd_bi_count = min_xd_bi_count
        self.golden_ratio = golden_ratio
        self.min_price_unit = min_price_unit
        self.use_macd_divergence = use_macd_divergence
        self.strict_mode = strict_mode
        self.debug = debug
        
        # 内部状态
        self._kbar_chan = None
        self._bi_df = None
        self._xd_df = None
        self._zhongshu_list = []
        
    def generate(self, data: MarketData) -> List[Signal]:
        """
        生成缠论信号
        
        异常处理:
        - InsufficientDataError: 数据不足7根K线
        - StandardizationError: 标准化失败
        - BiDefinitionError: 笔定义失败
        """
        # Step 0: 数据校验
        if len(data.close) < 7:
            raise InsufficientDataError(
                f"缠论需要至少7根K线，当前只有{len(data.close)}根"
            )
        
        # Step 1: 初始化 KBarChan（复用原始代码逻辑）
        self._kbar_chan = KBarChan(
            self._convert_to_numpy_array(data),
            isdebug=self.debug,
            clean_standardzed=False
        )
        
        # Step 2: 标准化K线（处理包含关系）
        try:
            self._kbar_chan.standardize(initial_state=TopBotType.noTopBot)
        except Exception as e:
            raise StandardizationError(f"K线标准化失败: {e}")
        
        # Step 3: 标记顶底分型
        self._kbar_chan.markTopBot(initial_state=TopBotType.noTopBot)
        
        # Step 4: 定义笔
        try:
            self._bi_df = self._kbar_chan.defineBi()
        except Exception as e:
            raise BiDefinitionError(f"笔定义失败: {e}")
        
        # Step 5: 定义线段
        self._xd_df = self._kbar_chan.process_xd()
        
        # Step 6: 识别中枢
        self._zhongshu_list = self._identify_zhongshu()
        
        # Step 7: 生成信号
        signals = []
        signals.extend(self._generate_bi_signals(data))
        signals.extend(self._generate_xd_signals(data))
        signals.extend(self._generate_zhongshu_signals(data))
        
        if self.use_macd_divergence:
            signals.extend(self._generate_divergence_signals(data))
        
        return signals
    
    def _generate_bi_signals(self, data: MarketData) -> List[Signal]:
        """
        基于笔生成信号
        
        信号规则:
        1. 底分型 + 笔向上 → 一买
        2. 顶分型 + 笔向下 → 一卖
        3. 回踩不破前低 → 二买
        4. 反弹不破前高 → 二卖
        5. 回调不进入中枢 → 三买
        6. 反弹不进入中枢 → 三卖
        """
        signals = []
        
        for i in range(2, len(self._bi_df)):
            current_bi = self._bi_df[i]
            prev_bi = self._bi_df[i-1]
            prev_prev_bi = self._bi_df[i-2]
            
            # 计算笔长度和强度
            bi_length = abs(current_bi['close'] - prev_bi['close'])
            atr = self._calculate_atr(data, period=14)
            strength = min(bi_length / atr, 1.0) if atr > 0 else 0.5
            
            # 判断笔类型
            if current_bi['tb'] == TopBotType.bot.value:  # 底分型
                # 一买判断
                signal_type = ChanSignalType.FIRST_BUY
                
                # 二买判断: 当前底高于前底
                if i >= 2 and current_bi['low'] > prev_prev_bi['low']:
                    signal_type = ChanSignalType.SECOND_BUY
                    strength *= 1.2  # 二买强度加成
                
                # 三买判断: 回调不进入最近中枢
                if self._zhongshu_list and self._is_above_zhongshu(current_bi):
                    signal_type = ChanSignalType.THIRD_BUY
                    strength *= 1.5  # 三买强度最高
                
                signals.append(Signal(
                    timestamp=current_bi['date'],
                    signal_type=signal_type,
                    strength=self._normalize_strength(strength),
                    price=current_bi['close'],
                    stop_loss=current_bi['low'],
                    take_profit=self._calculate_take_profit(current_bi, 'up'),
                    metadata={
                        'bi_index': i,
                        'bi_length': bi_length,
                        'bi_direction': 'up',
                        'is_valid_bi': self._validate_bi(current_bi, prev_bi)
                    }
                ))
            
            elif current_bi['tb'] == TopBotType.top.value:  # 顶分型
                # 类似逻辑，生成卖出信号
                signal_type = ChanSignalType.FIRST_SELL
                
                if i >= 2 and current_bi['high'] < prev_prev_bi['high']:
                    signal_type = ChanSignalType.SECOND_SELL
                    strength *= 1.2
                
                if self._zhongshu_list and self._is_below_zhongshu(current_bi):
                    signal_type = ChanSignalType.THIRD_SELL
                    strength *= 1.5
                
                signals.append(Signal(
                    timestamp=current_bi['date'],
                    signal_type=signal_type,
                    strength=self._normalize_strength(strength),
                    price=current_bi['close'],
                    stop_loss=current_bi['high'],
                    take_profit=self._calculate_take_profit(current_bi, 'down'),
                    metadata={
                        'bi_index': i,
                        'bi_length': bi_length,
                        'bi_direction': 'down',
                        'is_valid_bi': self._validate_bi(current_bi, prev_bi)
                    }
                ))
        
        return signals
    
    def _identify_zhongshu(self) -> List[ZhongShu]:
        """
        识别中枢
        
        中枢定义: 至少三段重叠的价格区间
        重叠条件: max(low1, low2, low3) < min(high1, high2, high3)
        """
        zhongshu_list = []
        
        if len(self._bi_df) < 6:  # 至少需要6笔才能形成中枢
            return zhongshu_list
        
        i = 0
        while i < len(self._bi_df) - 5:
            # 取连续三笔
            bi1 = self._bi_df[i]
            bi2 = self._bi_df[i+1]
            bi3 = self._bi_df[i+2]
            
            # 计算重叠区间
            zg = min(bi1['high'], bi2['high'], bi3['high'])  # 中枢高点
            zd = max(bi1['low'], bi2['low'], bi3['low'])      # 中枢低点
            
            if zg > zd:  # 有效中枢
                zhongshu = ZhongShu(
                    start_date=bi1['date'],
                    end_date=bi3['date'],
                    zg=zg,
                    zd=zd,
                    bi_count=3,
                    direction=self._determine_zhongshu_direction(bi1, bi2, bi3)
                )
                
                # 尝试延伸中枢
                zhongshu = self._extend_zhongshu(zhongshu, self._bi_df, start_idx=i+3)
                zhongshu_list.append(zhongshu)
                
                i += zhongshu.bi_count
            else:
                i += 1
        
        return zhongshu_list
    
    def _generate_divergence_signals(self, data: MarketData) -> List[Signal]:
        """
        背驰/背离信号生成
        
        背驰类型:
        1. 价格-MACD背离: 价格创新高但MACD未创新高
        2. 趋势背驰: 同向两段笔，后段力度小于前段
        3. 盘整背驰: 中枢震荡中，进出中枢的笔力度比较
        """
        signals = []
        
        # 计算 MACD
        dif, dea, macd = talib.MACD(data.close)
        
        for i in range(2, len(self._bi_df)):
            current_bi = self._bi_df[i]
            prev_bi = self._bi_df[i-2]  # 同向比较
            
            if current_bi['tb'] == prev_bi['tb'] == TopBotType.top.value:
                # 顶背驰检测
                if current_bi['high'] > prev_bi['high']:
                    # 价格创新高，检查MACD
                    current_macd_peak = self._get_macd_peak(macd, current_bi)
                    prev_macd_peak = self._get_macd_peak(macd, prev_bi)
                    
                    if current_macd_peak < prev_macd_peak:
                        # 价格新高但MACD未新高 → 顶背驰
                        signals.append(Signal(
                            timestamp=current_bi['date'],
                            signal_type=ChanSignalType.DIVERGENCE_PRICE_MACD,
                            strength=0.8,
                            price=current_bi['close'],
                            stop_loss=current_bi['high'],
                            metadata={
                                'divergence_type': 'top',
                                'price_ratio': current_bi['high'] / prev_bi['high'],
                                'macd_ratio': current_macd_peak / prev_macd_peak
                            }
                        ))
            
            elif current_bi['tb'] == prev_bi['tb'] == TopBotType.bot.value:
                # 底背驰检测（逻辑相反）
                if current_bi['low'] < prev_bi['low']:
                    current_macd_peak = self._get_macd_peak(macd, current_bi)
                    prev_macd_peak = self._get_macd_peak(macd, prev_bi)
                    
                    if current_macd_peak > prev_macd_peak:  # MACD负值，绝对值变小
                        signals.append(Signal(
                            timestamp=current_bi['date'],
                            signal_type=ChanSignalType.DIVERGENCE_PRICE_MACD,
                            strength=0.8,
                            price=current_bi['close'],
                            stop_loss=current_bi['low'],
                            metadata={
                                'divergence_type': 'bottom',
                                'price_ratio': current_bi['low'] / prev_bi['low'],
                                'macd_ratio': current_macd_peak / prev_macd_peak
                            }
                        ))
        
        return signals
```

### 3.2 圆弧底信号生成器 (RoundingBottomGenerator)

#### 3.2.1 原始代码核心逻辑分析

从 `57 【复现】技术分析算法、框架与实战之二：识别"圆弧底".ipynb` 提取:

```
核密度回归 → 寻找局部极值 → 计算相关系数 → 验证突破200日均线 → 生成信号
```

**关键边界情况:**

| 边界情况 | 原始代码处理方式 | 我们的增强处理 |
|----------|------------------|----------------|
| 窗口大小选择 | 固定参数 | 自适应：根据波动率调整窗口 |
| 核回归带宽 | 固定 Silverman 规则 | 交叉验证选择最优带宽 |
| 局部极值检测 | `argrelextrema` | 增加极值有效性验证（幅度阈值） |
| 相关系数阈值 | 固定 0.7 | 动态阈值：根据历史分布调整 |
| 突破验证 | 收盘价 > 200日均线 | 增加成交量确认突破有效性 |
| 假突破处理 | 无 | 增加回踩确认机制 |
| 多个圆弧底重叠 | 无处理 | 优先级排序，取最完整的一个 |

#### 3.2.2 完整实现

```python
class RoundingBottomGenerator(BaseIndicatorGenerator):
    """
    圆弧底形态识别生成器
    
    算法流程:
    1. 核密度回归拟合价格曲线
    2. 寻找局部最小值和最大值
    3. 计算拟合曲线与实际价格的相关系数
    4. 验证形态完整性（左肩-底-右肩）
    5. 确认突破信号（价格+成交量）
    
    参数:
    - lookback_window: 回看窗口，默认60日
    - correlation_threshold: 相关系数阈值，默认0.7
    - ma_period: 均线周期（突破验证），默认200
    - volume_confirm: 是否需要成交量确认
    - min_depth: 最小形态深度（%），默认5%
    """
    
    name = "rounding_bottom"
    
    def __init__(
        self,
        lookback_window: int = 60,
        correlation_threshold: float = 0.7,
        ma_period: int = 200,
        volume_confirm: bool = True,
        min_depth_pct: float = 0.05,
        bandwidth_method: str = 'silverman'
    ):
        self.lookback_window = lookback_window
        self.correlation_threshold = correlation_threshold
        self.ma_period = ma_period
        self.volume_confirm = volume_confirm
        self.min_depth_pct = min_depth_pct
        self.bandwidth_method = bandwidth_method
    
    def generate(self, data: MarketData) -> List[Signal]:
        signals = []
        
        # 数据长度检查
        if len(data.close) < self.lookback_window:
            return signals
        
        # 滑动窗口检测
        for end_idx in range(self.lookback_window, len(data.close)):
            window_close = data.close[end_idx-self.lookback_window:end_idx]
            window_volume = data.volume[end_idx-self.lookback_window:end_idx]
            
            # Step 1: 核密度回归
            fitted_curve = self._kernel_regression(window_close)
            
            # Step 2: 计算相关系数
            correlation = np.corrcoef(window_close, fitted_curve)[0, 1]
            
            if correlation < self.correlation_threshold:
                continue
            
            # Step 3: 寻找局部极值
            local_mins = self._find_local_minima(fitted_curve)
            local_maxs = self._find_local_maxima(fitted_curve)
            
            if len(local_mins) < 1 or len(local_maxs) < 2:
                continue
            
            # Step 4: 验证圆弧底形态
            if self._validate_rounding_bottom(
                fitted_curve, local_mins, local_maxs, window_close
            ):
                # Step 5: 突破验证
                if self._confirm_breakout(
                    data, end_idx, window_close, window_volume
                ):
                    strength = self._calculate_strength(
                        correlation, window_close, local_mins
                    )
                    
                    signals.append(Signal(
                        timestamp=data.datetime[end_idx],
                        signal_type=SignalType.BUY,
                        strength=strength,
                        price=data.close[end_idx],
                        stop_loss=self._calculate_stop_loss(window_close, local_mins),
                        take_profit=self._calculate_take_profit(window_close, local_maxs),
                        metadata={
                            'pattern': 'rounding_bottom',
                            'correlation': correlation,
                            'lookback_window': self.lookback_window,
                            'bottom_index': local_mins[0],
                            'depth_pct': self._calculate_depth(window_close, local_mins)
                        }
                    ))
        
        # 去重：同一时间段只保留最强信号
        return self._deduplicate_signals(signals)
    
    def _kernel_regression(self, y: np.ndarray) -> np.ndarray:
        """
        核密度回归拟合
        
        使用高斯核函数:
        K(u) = (1/√(2π)) * exp(-u²/2)
        
        带宽选择:
        - Silverman: h = 1.06 * σ * n^(-1/5)
        - 交叉验证: 最小化 MSE
        """
        n = len(y)
        x = np.arange(n)
        
        # 计算带宽
        if self.bandwidth_method == 'silverman':
            h = 1.06 * np.std(y) * n ** (-1/5)
        else:
            h = self._cross_validate_bandwidth(x, y)
        
        # 核回归
        fitted = np.zeros(n)
        for i in range(n):
            weights = np.exp(-0.5 * ((x - x[i]) / h) ** 2)
            weights /= weights.sum()
            fitted[i] = np.sum(weights * y)
        
        return fitted
    
    def _validate_rounding_bottom(
        self, fitted: np.ndarray, mins: List[int], maxs: List[int], actual: np.ndarray
    ) -> bool:
        """
        验证圆弧底形态完整性
        
        条件:
        1. 左肩高 > 底 > 右肩高（近似对称）
        2. 底部平滑（二阶导数 > 0）
        3. 形态深度 > min_depth_pct
        4. 左右肩高度差 < 10%
        """
        if len(maxs) < 2:
            return False
        
        left_shoulder = maxs[0]
        right_shoulder = maxs[-1]
        bottom = mins[0]
        
        # 检查顺序: 左肩 → 底 → 右肩
        if not (left_shoulder < bottom < right_shoulder):
            return False
        
        # 检查深度
        depth = (fitted[left_shoulder] - fitted[bottom]) / fitted[left_shoulder]
        if depth < self.min_depth_pct:
            return False
        
        # 检查对称性
        left_height = fitted[left_shoulder] - fitted[bottom]
        right_height = fitted[right_shoulder] - fitted[bottom]
        symmetry_ratio = min(left_height, right_height) / max(left_height, right_height)
        if symmetry_ratio < 0.7:  # 允许30%的不对称
            return False
        
        # 检查底部平滑性（二阶导数）
        second_deriv = np.diff(fitted, n=2)
        bottom_region = second_deriv[bottom-1:bottom+1]
        if np.any(bottom_region < 0):
            return False
        
        return True
    
    def _confirm_breakout(
        self, data: MarketData, end_idx: int, 
        window_close: np.ndarray, window_volume: np.ndarray
    ) -> bool:
        """
        突破确认
        
        条件:
        1. 当前收盘价 > 200日均线
        2. 成交量 > 20日均量 * 1.5（放量突破）
        3. 突破幅度 > 2%（避免假突破）
        """
        current_price = data.close[end_idx]
        
        # 均线突破
        if self.ma_period <= len(data.close):
            ma = np.mean(data.close[end_idx-self.ma_period:end_idx])
            if current_price <= ma:
                return False
        
        # 成交量确认
        if self.volume_confirm:
            avg_volume = np.mean(window_volume[-20:])
            if window_volume[-1] < avg_volume * 1.5:
                return False
        
        # 突破幅度
        pattern_high = np.max(window_close)
        breakout_pct = (current_price - pattern_high) / pattern_high
        if breakout_pct < 0.02:
            return False
        
        return True
```

### 3.3 MESA 信号生成器 (MESAGenerator)

#### 3.3.1 原始代码核心逻辑分析

从 `83 研究 识别趋势震荡之神器 MESA最大熵谱分析（一）：滤波器建立.ipynb` 提取:

```
分钟数据 → ADF平稳性检验 → 差分 → 等间隔采样 → AR模型阶数选择(AIC) → 频谱密度计算 → 趋势/震荡判别
```

**关键边界情况:**

| 边界情况 | 原始代码处理方式 | 我们的增强处理 |
|----------|------------------|----------------|
| 序列不平稳 | 一阶差分 | 自动检测差分阶数，最多2阶 |
| 采样间隔选择 | 手动尝试10/20/30/40 | AIC自动选择最优间隔 |
| AR阶数选择 | 目测 + AIC图 | `ar_select_order` 自动选择 |
| AR(1)特殊情况 | 手动改为AR(2) | 检测频谱平坦度，自动调整 |
| 分钟数据缺失 | 无处理 | 向前填充，标记缺失时段 |
| 交易时段过滤 | 无 | 过滤非交易时段（午休等） |
| 频谱分辨率 | 固定 | 根据数据长度自适应 |

#### 3.3.2 完整实现

```python
class MESAGenerator(BaseIndicatorGenerator):
    """
    MESA最大熵谱分析信号生成器
    
    核心思想:
    - 通过AR模型估计频谱密度
    - 频谱峰值明显 → 震荡市（有主导周期）
    - 频谱平坦 → 趋势市（无主导周期）
    
    参数:
    - max_lag: AR模型最大滞后阶数
    - sampling_intervals: 候选采样间隔列表
    - adf_significance: ADF检验显著性水平
    - trend_threshold: 趋势/震荡判别阈值
    """
    
    name = "mesa"
    
    def __init__(
        self,
        max_lag: int = 40,
        sampling_intervals: List[int] = None,
        adf_significance: float = 0.05,
        trend_threshold: float = 0.6,
        use_minute_data: bool = False
    ):
        self.max_lag = max_lag
        self.sampling_intervals = sampling_intervals or [6, 8, 12, 24]
        self.adf_significance = adf_significance
        self.trend_threshold = trend_threshold
        self.use_minute_data = use_minute_data
    
    def generate(self, data: MarketData) -> List[Signal]:
        signals = []
        
        # Step 1: 数据预处理
        close_series = pd.Series(data.close, index=data.datetime)
        
        # Step 2: 平稳性检验
        is_stationary, diff_order = self._check_stationarity(close_series)
        
        if not is_stationary:
            if diff_order > 0:
                close_series = close_series.diff(diff_order).dropna()
            else:
                # 无法平稳化，返回中性信号
                signals.append(Signal(
                    timestamp=data.datetime[-1],
                    signal_type=SignalType.NEUTRAL,
                    strength=0.0,
                    price=data.close[-1],
                    metadata={'mesa_status': 'non_stationary'}
                ))
                return signals
        
        # Step 3: 最优采样间隔选择
        best_interval, best_aic = self._select_optimal_interval(close_series)
        
        # Step 4: 降采样
        downsampled = close_series.iloc[::best_interval]
        
        # Step 5: AR模型拟合
        ar_order = self._select_ar_order(downsampled)
        ar_model = AutoReg(downsampled, lags=ar_order)
        ar_result = ar_model.fit()
        
        # Step 6: 频谱密度计算
        frequencies, spectrum = self._compute_spectrum(ar_result)
        
        # Step 7: 趋势/震荡判别
        market_regime, confidence = self._classify_regime(spectrum)
        
        # Step 8: 生成信号
        if market_regime == 'trending':
            # 趋势市：顺势交易
            trend_direction = self._detect_trend_direction(downsampled)
            signals.append(Signal(
                timestamp=data.datetime[-1],
                signal_type=SignalType.BUY if trend_direction == 'up' else SignalType.SELL,
                strength=confidence,
                price=data.close[-1],
                metadata={
                    'mesa_regime': 'trending',
                    'ar_order': ar_order,
                    'sampling_interval': best_interval,
                    'trend_direction': trend_direction,
                    'spectrum_flatness': self._calculate_flatness(spectrum)
                }
            ))
        else:
            # 震荡市：高抛低吸
            dominant_period = self._find_dominant_period(frequencies, spectrum)
            signals.append(Signal(
                timestamp=data.datetime[-1],
                signal_type=SignalType.NEUTRAL,
                strength=confidence,
                price=data.close[-1],
                metadata={
                    'mesa_regime': 'oscillating',
                    'ar_order': ar_order,
                    'sampling_interval': best_interval,
                    'dominant_period': dominant_period,
                    'spectrum_peak_ratio': self._calculate_peak_ratio(spectrum)
                }
            ))
        
        return signals
    
    def _check_stationarity(self, series: pd.Series) -> Tuple[bool, int]:
        """
        ADF平稳性检验
        
        返回: (是否平稳, 需要差分的阶数)
        """
        for diff_order in range(3):  # 最多差分2次
            if diff_order == 0:
                test_series = series
            else:
                test_series = series.diff(diff_order).dropna()
            
            if len(test_series) < 10:
                break
            
            adf_result = ADF(test_series)
            p_value = adf_result[1]
            
            if p_value < self.adf_significance:
                return True, diff_order
        
        return False, 0
    
    def _select_optimal_interval(self, series: pd.Series) -> Tuple[int, float]:
        """
        选择最优采样间隔
        
        标准: 最小化 AR 模型的 AIC
        """
        best_interval = self.sampling_intervals[0]
        best_aic = float('inf')
        
        for interval in self.sampling_intervals:
            downsampled = series.iloc[::interval]
            
            if len(downsampled) < self.max_lag + 10:
                continue
            
            try:
                model = AutoReg(downsampled, lags=min(10, len(downsampled)//3))
                result = model.fit()
                
                if result.aic < best_aic:
                    best_aic = result.aic
                    best_interval = interval
            except:
                continue
        
        return best_interval, best_aic
    
    def _select_ar_order(self, series: pd.Series) -> int:
        """
        自动选择AR模型阶数
        
        使用 AIC 准则，避免 AR(1) 导致频谱平坦
        """
        max_order = min(self.max_lag, len(series) // 3)
        
        try:
            selection = ar_select_order(series, maxlag=max_order, ic='aic')
            ar_order = selection.ar_order
            
            # 如果选择AR(1)，强制使用AR(2)以避免频谱为常数
            if ar_order == 1:
                ar_order = 2
        except:
            ar_order = 2  # 默认AR(2)
        
        return ar_order
    
    def _compute_spectrum(self, ar_result) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算频谱密度
        
        基于AR模型参数计算功率谱密度
        """
        ar_coefs = ar_result.params[1:]  # 去掉截距
        sigma2 = ar_result.sigma2
        
        n_freqs = 256
        frequencies = np.linspace(0, 0.5, n_freqs)
        
        # 计算频谱
        spectrum = np.zeros(n_freqs)
        for i, f in enumerate(frequencies):
            denominator = 1.0
            for k, coef in enumerate(ar_coefs):
                denominator -= coef * np.exp(-2j * np.pi * f * (k+1))
            spectrum[i] = sigma2 / np.abs(denominator) ** 2
        
        return frequencies, spectrum
    
    def _classify_regime(self, spectrum: np.ndarray) -> Tuple[str, float]:
        """
        趋势/震荡判别
        
        方法: 计算频谱平坦度 (Spectral Flatness)
        - 平坦度接近1 → 白噪声/趋势市
        - 平坦度接近0 → 有主导频率/震荡市
        """
        # 几何平均 / 算术平均
        log_spectrum = np.log(spectrum + 1e-10)
        geometric_mean = np.exp(np.mean(log_spectrum))
        arithmetic_mean = np.mean(spectrum)
        
        flatness = geometric_mean / (arithmetic_mean + 1e-10)
        
        if flatness > self.trend_threshold:
            return 'trending', min(flatness, 1.0)
        else:
            return 'oscillating', 1.0 - flatness
    
    def _find_dominant_period(self, frequencies: np.ndarray, spectrum: np.ndarray) -> float:
        """
        寻找主导周期
        
        返回: 周期长度（以采样间隔为单位）
        """
        peak_idx = np.argmax(spectrum)
        dominant_freq = frequencies[peak_idx]
        
        if dominant_freq == 0:
            return float('inf')
        
        return 1.0 / dominant_freq
```

### 3.4 RSRS 信号生成器 (RSRSGenerator)

#### 3.4.1 原始代码核心逻辑分析

从 `59 研究 【复现】RSRS择时改进.ipynb` 提取:

```
OLS/WLS回归(high~low) → 计算β和R² → 标准分 → 修正标准分 → 右偏修正 → 钝化RSRS → 成交额加权钝化RSRS
```

**关键边界情况:**

| 边界情况 | 原始代码处理方式 | 我们的增强处理 |
|----------|------------------|----------------|
| 回归NaN处理 | `np.nan_to_num` | 增加异常值过滤，NaN替换为中位数 |
| R²为负 | 无处理 | 截断为0，避免信号反转 |
| 标准分分母为0 | 无处理 | 增加epsilon，避免除零 |
| 钝化分位数计算 | `rank(pct=True)` | 增加窗口最小样本数检查 |
| 成交量权重归一化 | `vol / vol.sum()` | 处理vol.sum()=0的情况 |
| 阈值参数化 | 硬编码 | 支持动态阈值优化 |
| 多信号名称 | 字符串硬编码 | 枚举类管理 |

#### 3.4.2 完整实现

```python
class RSRSVariant(Enum):
    """RSRS信号变体"""
    ORIGINAL = "RSRS"
    STANDARDIZED = "标准分RSRS"
    CORRECTED = "修正标准分RSRS"
    RIGHT_SKEWED = "右偏修正标准分RSRS"
    DAMPENED = "钝化RSRS"
    VOLUME_WEIGHTED_DAMPENED = "成交额加权钝化RSRS"


class RSRSGenerator(BaseIndicatorGenerator):
    """
    RSRS择时信号生成器
    
    支持6种RSRS变体，每种有不同的信号特征
    
    参数:
    - N: 回归窗口（默认18）
    - M: 标准分窗口（默认600）
    - variants: 要计算的RSRS变体列表
    - use_wls: 是否使用加权最小二乘
    - dampen_power: 钝化指数（默认2）
    """
    
    name = "rsrs"
    
    def __init__(
        self,
        N: int = 18,
        M: int = 600,
        variants: List[RSRSVariant] = None,
        use_wls: bool = True,
        dampen_power: float = 2.0,
        entry_threshold: float = 0.7,
        exit_threshold: float = -0.7
    ):
        self.N = N
        self.M = M
        self.variants = variants or [
            RSRSVariant.DAMPENED,
            RSRSVariant.RIGHT_SKEWED
        ]
        self.use_wls = use_wls
        self.dampen_power = dampen_power
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
    
    def generate(self, data: MarketData) -> List[Signal]:
        signals = []
        
        # 数据检查
        if len(data.close) < self.N + self.M:
            return signals
        
        # Step 1: 计算回归参数
        beta_ols, r2_ols, beta_wls, r2_wls = self._regression(data)
        
        # Step 2: 计算收益率波动分位数
        ret_quantile = self._calc_ret_quantile(data)
        
        # Step 3: 计算各变体RSRS
        for variant in self.variants:
            rsrs_series = self._calc_rsrs_variant(
                variant, beta_ols, r2_ols, beta_wls, r2_wls, ret_quantile
            )
            
            # Step 4: 生成交易信号
            variant_signals = self._generate_trade_signals(
                data, rsrs_series, variant
            )
            signals.extend(variant_signals)
        
        return signals
    
    def _regression(self, data: MarketData) -> Tuple:
        """
        计算OLS和WLS回归
        
        回归方程: high = α + β * low + ε
        
        边界处理:
        - 过滤NaN值
        - WLS权重 = volume / sum(volume)
        - 处理volume全为0的情况
        """
        beta_ols = []
        r2_ols = []
        beta_wls = []
        r2_wls = []
        
        for i in range(self.N, len(data.close) + 1):
            low = data.low[i-self.N:i]
            high = data.high[i-self.N:i]
            volume = data.volume[i-self.N:i]
            
            # OLS回归
            ols_result = self._cal_ols(low, high)
            beta_ols.append(ols_result[0])
            r2_ols.append(ols_result[1])
            
            # WLS回归
            if self.use_wls:
                weights = self._get_vol_weights(volume)
                wls_result = self._cal_wls(low, high, weights)
                beta_wls.append(wls_result[0])
                r2_wls.append(wls_result[1])
            else:
                beta_wls.append(ols_result[0])
                r2_wls.append(ols_result[1])
        
        return beta_ols, r2_ols, beta_wls, r2_wls
    
    @staticmethod
    def _cal_ols(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """
        OLS回归计算beta和R²
        
        边界处理:
        - 过滤NaN
        - 处理完全共线性（R²=1）
        - 处理方差为0（R²=0）
        """
        x = np.nan_to_num(x, nan=np.nanmedian(x))
        y = np.nan_to_num(y, nan=np.nanmedian(y))
        
        X = sm.add_constant(x)
        
        try:
            beta = np.linalg.lstsq(X, y, rcond=-1)[0][1]
            r2 = np.corrcoef(x, y)[1, 0] ** 2
            r2 = max(0, min(r2, 1))  # 截断到[0,1]
        except:
            beta = 1.0
            r2 = 0.0
        
        return beta, r2
    
    def _calc_ret_quantile(self, data: MarketData) -> np.ndarray:
        """
        计算收益率波动率分位数
        
        公式: quantile(std(return), M)
        
        边界处理:
        - 最小样本数检查
        - 处理全0波动率
        """
        ret = pd.Series(data.close).pct_change()
        ret_std = ret.rolling(self.N, min_periods=1).std()
        
        # 计算分位数
        ret_quantile = ret_std.rolling(self.M).apply(
            lambda x: x.rank(pct=True).iloc[-1] if len(x) > 1 else 0.5,
            raw=False
        )
        
        return ret_quantile.values
    
    def _calc_rsrs_variant(
        self, variant: RSRSVariant,
        beta_ols, r2_ols, beta_wls, r2_wls, ret_quantile
    ) -> pd.Series:
        """
        计算指定变体的RSRS值
        
        各变体公式:
        - ORIGINAL: β_OLS
        - STANDARDIZED: z_score(β_OLS)
        - CORRECTED: z_score(β_OLS) * R²_OLS
        - RIGHT_SKEWED: z_score(β_OLS) * R²_OLS * β_OLS
        - DAMPENED: z_score(β_OLS) * R²_OLS^(2*quantile)
        - VOLUME_WEIGHTED_DAMPENED: z_score(β_WLS) * R²_WLS^(2*quantile)
        """
        beta = pd.Series(beta_ols)
        r2 = pd.Series(r2_ols)
        beta_w = pd.Series(beta_wls)
        r2_w = pd.Series(r2_wls)
        
        # 计算标准分
        z_beta = (beta - beta.rolling(self.M).mean()) / (
            beta.rolling(self.M).std() + 1e-10  # 避免除零
        )
        z_beta_w = (beta_w - beta_w.rolling(self.M).mean()) / (
            beta_w.rolling(self.M).std() + 1e-10
        )
        
        if variant == RSRSVariant.ORIGINAL:
            return beta
        elif variant == RSRSVariant.STANDARDIZED:
            return z_beta
        elif variant == RSRSVariant.CORRECTED:
            return z_beta * r2
        elif variant == RSRSVariant.RIGHT_SKEWED:
            return z_beta * r2 * beta
        elif variant == RSRSVariant.DAMPENED:
            return z_beta * r2 ** (self.dampen_power * ret_quantile)
        elif variant == RSRSVariant.VOLUME_WEIGHTED_DAMPENED:
            return z_beta_w * r2_w ** (self.dampen_power * ret_quantile)
    
    def _generate_trade_signals(
        self, data: MarketData, rsrs_series: pd.Series, variant: RSRSVariant
    ) -> List[Signal]:
        """
        基于RSRS值生成交易信号
        
        规则:
        - RSRS > entry_threshold → 买入
        - RSRS < exit_threshold → 卖出
        - 中间 → 持有/观望
        """
        signals = []
        
        for i in range(1, len(rsrs_series)):
            current_rsrs = rsrs_series.iloc[i]
            prev_rsrs = rsrs_series.iloc[i-1]
            
            # 金叉: 从下向上穿越买入阈值
            if prev_rsrs <= self.entry_threshold < current_rsrs:
                signals.append(Signal(
                    timestamp=data.datetime[i],
                    signal_type=SignalType.BUY,
                    strength=min(abs(current_rsrs), 1.0),
                    price=data.close[i],
                    stop_loss=data.low[i] * 0.97,
                    metadata={
                        'rsrs_variant': variant.value,
                        'rsrs_value': current_rsrs,
                        'crossover': 'golden'
                    }
                ))
            
            # 死叉: 从上向下穿越卖出阈值
            elif prev_rsrs >= self.exit_threshold > current_rsrs:
                signals.append(Signal(
                    timestamp=data.datetime[i],
                    signal_type=SignalType.SELL,
                    strength=min(abs(current_rsrs), 1.0),
                    price=data.close[i],
                    stop_loss=data.high[i] * 1.03,
                    metadata={
                        'rsrs_variant': variant.value,
                        'rsrs_value': current_rsrs,
                        'crossover': 'death'
                    }
                ))
        
        return signals
```

### 3.5 趋与势信号生成器 (TrendMomentumGenerator)

#### 3.5.1 原始代码核心逻辑分析

从 `81 趋与势的量化定义.ipynb` 提取:

```
价格标准化(单调性/均线/复合) → 波段划分(相对/绝对) → 趋得分(位移和) → 势得分(位移平方和) → 终极势=max(连续波段, 绝对波动)/N^(3/2)
```

**关键边界情况:**

| 边界情况 | 原始代码处理方式 | 我们的增强处理 |
|----------|------------------|----------------|
| 数据长度 < window | 抛异常 | 返回None，上层处理 |
| 标准化序列全相同 | 差分为0 | 返回趋势强度0 |
| 拐点检测 | 差分符号变化 | 增加最小幅度过滤 |
| 绝对极值点 | `argmax/argmin` | 处理多个相同极值 |
| 递归波段划分 | 未实现 | 完整实现递归算法 |
| N^(3/2)归一化 | 直接除 | 处理N=0和N=1 |
| 趋/势分离 | 分别计算 | 联合分析（趋势背离检测） |

#### 3.5.2 完整实现

```python
class NormalizationMethod(Enum):
    """价格标准化方法"""
    MONOTONE = "monotone"       # 收盘价单调性
    MOVING_AVERAGE = "ma"       # 5周期均线
    COMPOUND = "compound"       # 复合（单调性+均线）


class BandDivisionMethod(Enum):
    """波段划分方法"""
    OPPOSITE = "opposite"   # 相对波段（拐点划分）
    ABSOLUTE = "absolute"   # 绝对波段（极值划分）


class TrendMomentumGenerator(BaseIndicatorGenerator):
    """
    趋与势量化信号生成器
    
    趋(Act): 价格位移的代数和，反映方向
    势(Trend): 价格位移的平方和，反映强度
    
    参数:
    - normalization: 标准化方法
    - ma_window: 均线窗口（用于MA和复合标准化）
    - band_method: 波段划分方法
    - min_band_length: 最小波段长度
    """
    
    name = "trend_momentum"
    
    def __init__(
        self,
        normalization: NormalizationMethod = NormalizationMethod.COMPOUND,
        ma_window: int = 5,
        band_method: BandDivisionMethod = BandDivisionMethod.OPPOSITE,
        min_band_length: int = 3,
        lookback_window: int = 20
    ):
        self.normalization = normalization
        self.ma_window = ma_window
        self.band_method = band_method
        self.min_band_length = min_band_length
        self.lookback_window = lookback_window
    
    def generate(self, data: MarketData) -> List[Signal]:
        signals = []
        
        # 滑动窗口计算
        for end_idx in range(self.lookback_window, len(data.close)):
            window_close = data.close[end_idx-self.lookback_window:end_idx]
            close_series = pd.Series(window_close)
            
            # Step 1: 价格标准化
            normalized = self._normalize(close_series)
            
            if normalized is None:
                continue
            
            # Step 2: 计算趋得分
            act_score = self._calc_act_score(normalized)
            
            # Step 3: 计算势得分
            trend_score = self._calc_trend_score(normalized)
            
            # Step 4: 终极势得分
            ultimate_score = self._calc_ultimate_score(normalized)
            
            # Step 5: 生成信号
            signal = self._generate_signal_from_scores(
                data, end_idx, act_score, trend_score, ultimate_score
            )
            if signal:
                signals.append(signal)
        
        return signals
    
    def _normalize(self, close_series: pd.Series) -> Optional[pd.Series]:
        """
        价格标准化
        
        三种方法:
        1. 单调性: sign(pct_change).cumsum()
        2. 均线: sign(close - MA).cumsum()
        3. 复合: (sign(pct_change) + sign(close - MA)) / 2
        """
        if len(close_series) < self.ma_window:
            return None
        
        if self.normalization == NormalizationMethod.MONOTONE:
            sign = close_series.pct_change().apply(np.sign)
            return sign.cumsum().fillna(0)
        
        elif self.normalization == NormalizationMethod.MOVING_AVERAGE:
            ma = close_series.rolling(self.ma_window).mean()
            sign = (close_series - ma).apply(np.sign)
            return sign.iloc[self.ma_window - 2:].cumsum().fillna(0)
        
        elif self.normalization == NormalizationMethod.COMPOUND:
            sign_monotone = close_series.pct_change().apply(np.sign)
            ma = close_series.rolling(self.ma_window).mean()
            sign_ma = (close_series - ma).apply(np.sign)
            
            # 复合逻辑（4种情形）
            sign_compound = (sign_monotone + sign_ma) / 2
            return sign_compound.iloc[self.ma_window - 2:].cumsum().fillna(0)
    
    def _calc_act_score(self, normalized: pd.Series) -> float:
        """
        趋得分 = 标准化序列的差分和
        
        反映价格位移的净方向
        """
        return normalized.diff().sum()
    
    def _calc_trend_score(self, normalized: pd.Series) -> float:
        """
        势得分 = 标准化序列差分的平方和
        
        反映价格波动的强度，连续同向波动得分更高
        """
        if self.band_method == BandDivisionMethod.OPPOSITE:
            # 相对波段：拐点处计算
            cond = self._get_opposite_points(normalized)
            return np.square(normalized[cond].diff()).sum()
        else:
            # 绝对波段：极值处计算
            cond = self._get_absolute_points(normalized)
            return np.square(normalized[cond].diff()).sum()
    
    def _calc_ultimate_score(self, normalized: pd.Series) -> float:
        """
        终极势得分 = max(连续波段势, 绝对波动势) / N^(3/2)
        
        结合两种定义的优势
        """
        N = len(normalized)
        if N <= 1:
            return 0.0
        
        # 连续波段势
        opposite_score = self._calc_trend_score_opposite(normalized)
        
        # 绝对波动势
        absolute_score = self._calc_trend_score_absolute(normalized)
        
        return max(opposite_score, absolute_score) / (N ** 1.5)
    
    def _generate_signal_from_scores(
        self, data: MarketData, end_idx: int,
        act_score: float, trend_score: float, ultimate_score: float
    ) -> Optional[Signal]:
        """
        基于趋/势得分生成信号
        
        信号规则:
        1. 趋 > 0 且 势 > 阈值 → 强势上涨 → 买入
        2. 趋 < 0 且 势 > 阈值 → 强势下跌 → 卖出
        3. 趋 > 0 但 势 < 阈值 → 弱势上涨 → 观望
        4. 趋势背离 → 可能转折
        """
        trend_threshold = self._calc_dynamic_threshold(data, end_idx)
        
        # 强势上涨
        if act_score > 0 and ultimate_score > trend_threshold:
            return Signal(
                timestamp=data.datetime[end_idx],
                signal_type=SignalType.BUY,
                strength=min(ultimate_score, 1.0),
                price=data.close[end_idx],
                stop_loss=data.low[end_idx-self.lookback_window:end_idx].min(),
                metadata={
                    'act_score': act_score,
                    'trend_score': trend_score,
                    'ultimate_score': ultimate_score,
                    'signal_reason': 'strong_uptrend'
                }
            )
        
        # 强势下跌
        elif act_score < 0 and ultimate_score > trend_threshold:
            return Signal(
                timestamp=data.datetime[end_idx],
                signal_type=SignalType.SELL,
                strength=min(ultimate_score, 1.0),
                price=data.close[end_idx],
                stop_loss=data.high[end_idx-self.lookback_window:end_idx].max(),
                metadata={
                    'act_score': act_score,
                    'trend_score': trend_score,
                    'ultimate_score': ultimate_score,
                    'signal_reason': 'strong_downtrend'
                }
            )
        
        # 趋势背离（趋为正但势下降，或趋为负但势上升）
        elif self._detect_divergence(act_score, trend_score):
            return Signal(
                timestamp=data.datetime[end_idx],
                signal_type=SignalType.NEUTRAL,
                strength=0.5,
                price=data.close[end_idx],
                metadata={
                    'act_score': act_score,
                    'trend_score': trend_score,
                    'ultimate_score': ultimate_score,
                    'signal_reason': 'act_trend_divergence'
                }
            )
        
        return None
```

### 3.6 拥挤率信号生成器 (CrowdingRateGenerator)

#### 3.6.1 原始代码核心逻辑分析

从 `82 拥挤率指标-择时大盘顶底-Clone1-第二版.ipynb` 提取:

```
全市场成交额 → 排序 → 前5%成交额占比 → 拥挤率时间序列 → 与指数对比 → 顶底判断
```

**关键边界情况:**

| 边界情况 | 原始代码处理方式 | 我们的增强处理 |
|----------|------------------|----------------|
| 全市场股票列表获取 | `get_all_securities(date)` | 增加ST/停牌过滤 |
| 成交额数据缺失 | 无处理 | 向前填充，标记缺失 |
| 前5%计算 | `int(len(h) / 20)` | 处理股票数量变化 |
| 拥挤率极端值 | 无处理 | Winsorize处理（1%-99%） |
| 顶底判断 | 目测图表 | 增加统计检验（分位数） |
| 多日并行计算 | 分片处理 | 增加进度回调和错误恢复 |

#### 3.6.2 完整实现

```python
class CrowdingRateGenerator(BaseIndicatorGenerator):
    """
    拥挤率指标生成器
    
    核心思想:
    - 前5%股票的成交额占全市场成交额的比例
    - 拥挤率高 → 资金集中 → 可能见顶
    - 拥挤率低 → 资金分散 → 可能见底
    
    参数:
    - top_pct: 头部股票比例，默认0.05
    - lookback_window: 历史分位数计算窗口
    - overbought_threshold: 超买阈值（分位数）
    - oversold_threshold: 超卖阈值（分位数）
    """
    
    name = "crowding_rate"
    
    def __init__(
        self,
        top_pct: float = 0.05,
        lookback_window: int = 250,
        overbought_threshold: float = 0.8,
        oversold_threshold: float = 0.2,
        use_winsorize: bool = True
    ):
        self.top_pct = top_pct
        self.lookback_window = lookback_window
        self.overbought_threshold = overbought_threshold
        self.oversold_threshold = oversold_threshold
        self.use_winsorize = use_winsorize
    
    def generate(self, data: MarketData) -> List[Signal]:
        """
        注意: 拥挤率需要全市场数据，这里假设data包含market_money字段
        或者通过外部数据源获取
        """
        signals = []
        
        if not hasattr(data, 'market_crowding_rate'):
            return signals
        
        crowding_rate = data.market_crowding_rate
        
        # 计算历史分位数
        if len(crowding_rate) < self.lookback_window:
            return signals
        
        current_rate = crowding_rate[-1]
        historical_rates = crowding_rate[-self.lookback_window:-1]
        
        percentile = self._calc_percentile(current_rate, historical_rates)
        
        # 超买信号（拥挤率过高）
        if percentile > self.overbought_threshold:
            signals.append(Signal(
                timestamp=data.datetime[-1],
                signal_type=SignalType.SELL,
                strength=(percentile - self.overbought_threshold) / (1 - self.overbought_threshold),
                price=data.close[-1],
                metadata={
                    'crowding_rate': current_rate,
                    'percentile': percentile,
                    'signal_reason': 'overcrowded'
                }
            ))
        
        # 超卖信号（拥挤率过低）
        elif percentile < self.oversold_threshold:
            signals.append(Signal(
                timestamp=data.datetime[-1],
                signal_type=SignalType.BUY,
                strength=(self.oversold_threshold - percentile) / self.oversold_threshold,
                price=data.close[-1],
                metadata={
                    'crowding_rate': current_rate,
                    'percentile': percentile,
                    'signal_reason': 'undercrowded'
                }
            ))
        
        return signals
    
    def _calc_percentile(self, value: float, historical: np.ndarray) -> float:
        """
        计算当前值在历史中的分位数
        """
        return (historical < value).sum() / len(historical)
```

---

## 四、信号融合层 (SignalFusion) - 深度设计

### 4.1 融合策略矩阵

```python
class FusionStrategy(Enum):
    """融合策略"""
    WEIGHTED_VOTE = "weighted_vote"      # 加权投票
    MAJORITY_VOTE = "majority_vote"      # 简单多数
    CONSENSUS = "consensus"              # 共识机制
    MARKET_REGIME_ADAPTIVE = "regime_adaptive"  # 市场环境自适应
    MACHINE_LEARNING = "ml_ensemble"     # 机器学习集成


class SignalFusion:
    """
    多信号融合引擎
    
    融合流程:
    1. 信号对齐（同一时间点）
    2. 信号标准化（统一到[-1, 1]）
    3. 市场环境判别（趋势/震荡）
    4. 权重分配（动态调整）
    5. 融合计算
    6. 冲突消解
    7. 输出最终信号
    """
    
    def __init__(
        self,
        strategy: FusionStrategy = FusionStrategy.MARKET_REGIME_ADAPTIVE,
        base_weights: Dict[str, float] = None,
        consensus_threshold: int = 3
    ):
        self.strategy = strategy
        self.base_weights = base_weights or {
            'chan_theory': 0.25,
            'rounding_bottom': 0.15,
            'mesa': 0.20,
            'rsrs': 0.20,
            'trend_momentum': 0.15,
            'crowding_rate': 0.05
        }
        self.consensus_threshold = consensus_threshold
    
    def fuse(self, signals: List[Signal], market_data: MarketData) -> FusedSignal:
        """
        融合多指标信号
        
        返回: FusedSignal（包含最终方向、强度、置信度、建议仓位）
        """
        # Step 1: 按时间对齐
        aligned = self._align_signals_by_time(signals)
        
        # Step 2: 市场环境判别
        regime = self._detect_market_regime(market_data)
        
        # Step 3: 动态权重调整
        weights = self._adjust_weights_by_regime(regime)
        
        # Step 4: 融合计算
        if self.strategy == FusionStrategy.WEIGHTED_VOTE:
            result = self._weighted_vote(aligned, weights)
        elif self.strategy == FusionStrategy.CONSENSUS:
            result = self._consensus(aligned, weights)
        elif self.strategy == FusionStrategy.MARKET_REGIME_ADAPTIVE:
            result = self._regime_adaptive_fusion(aligned, weights, regime)
        
        # Step 5: 冲突消解
        result = self._resolve_conflicts(result, aligned)
        
        # Step 6: 仓位建议
        result.position_suggestion = self._calculate_position_suggestion(
            result, regime
        )
        
        return result
    
    def _adjust_weights_by_regime(self, regime: str) -> Dict[str, float]:
        """
        根据市场环境动态调整权重
        
        趋势市: 缠论、趋与势、RSRS 权重提高
        震荡市: MESA、圆弧底、拥挤率 权重提高
        """
        if regime == 'trending':
            return {
                'chan_theory': 0.30,
                'rounding_bottom': 0.05,
                'mesa': 0.10,
                'rsrs': 0.25,
                'trend_momentum': 0.25,
                'crowding_rate': 0.05
            }
        elif regime == 'oscillating':
            return {
                'chan_theory': 0.15,
                'rounding_bottom': 0.25,
                'mesa': 0.25,
                'rsrs': 0.10,
                'trend_momentum': 0.10,
                'crowding_rate': 0.15
            }
        else:  # transition
            return self.base_weights
    
    def _regime_adaptive_fusion(
        self, aligned: Dict, weights: Dict, regime: str
    ) -> FusedSignal:
        """
        市场环境自适应融合
        
        核心逻辑:
        1. 趋势市: 趋势类指标主导，形态类指标辅助确认
        2. 震荡市: 形态类指标主导，趋势类指标过滤假信号
        3. 转换期: 等权重，等待方向明确
        """
        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        
        for source, signal in aligned.items():
            weight = weights.get(source, 1.0)
            
            if regime == 'trending':
                # 趋势市: 趋势类指标权重翻倍
                if source in ['chan_theory', 'rsrs', 'trend_momentum']:
                    weight *= 2.0
            elif regime == 'oscillating':
                # 震荡市: 形态类指标权重翻倍
                if source in ['rounding_bottom', 'mesa', 'crowding_rate']:
                    weight *= 2.0
            
            if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                buy_score += signal.strength * weight * abs(signal.signal_type.value)
            elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
                sell_score += signal.strength * weight * abs(signal.signal_type.value)
            
            total_weight += weight
        
        # 归一化
        if total_weight > 0:
            buy_score /= total_weight
            sell_score /= total_weight
        
        net_score = buy_score - sell_score
        
        return FusedSignal(
            timestamp=aligned[list(aligned.keys())[0]].timestamp,
            net_score=net_score,
            buy_score=buy_score,
            sell_score=sell_score,
            regime=regime
        )
    
    def _resolve_conflicts(
        self, result: FusedSignal, aligned: Dict
    ) -> FusedSignal:
        """
        冲突消解规则
        
        规则1: 如果买卖分数接近（差值 < 0.1），标记为观望
        规则2: 如果缠论与MESA冲突，降低仓位
        规则3: 如果3个以上指标同向，提高置信度
        """
        # 规则1: 接近阈值
        if abs(result.buy_score - result.sell_score) < 0.1:
            result.signal_type = SignalType.NEUTRAL
            result.confidence = 0.0
            return result
        
        # 规则2: 缠论 vs MESA 冲突
        chan_signal = aligned.get('chan_theory')
        mesa_signal = aligned.get('mesa')
        
        if chan_signal and mesa_signal:
            if (chan_signal.is_buy() and mesa_signal.is_sell()) or \
               (chan_signal.is_sell() and mesa_signal.is_buy()):
                result.confidence *= 0.7  # 降低置信度
                result.position_suggestion *= 0.5  # 减半仓位
        
        # 规则3: 多指标共识
        buy_count = sum(1 for s in aligned.values() if s.is_buy())
        sell_count = sum(1 for s in aligned.values() if s.is_sell())
        
        if buy_count >= self.consensus_threshold:
            result.confidence = min(result.confidence * 1.3, 1.0)
        elif sell_count >= self.consensus_threshold:
            result.confidence = min(result.confidence * 1.3, 1.0)
        
        return result
```

---

## 五、完整指标清单与参数矩阵

| 指标 | 源文件 | 信号类型 | 核心参数 | 适用场景 | 时间框架 | 计算复杂度 |
|------|--------|----------|----------|----------|----------|------------|
| 缠论笔/线段 | 16 | 趋势转折 | min_bi_kbars=4, min_xd_bi_count=3 | 所有 | 日线 | O(N²) |
| 缠论中枢 | 16 | 区间突破 | zg/zd计算 | 所有 | 日线 | O(N²) |
| 缠论背驰 | 16 | 顶底背离 | use_macd_divergence=True | 趋势末端 | 日线 | O(N) |
| 圆弧底 | 57 | 底部反转 | lookback=60, corr_thresh=0.7 | 底部 | 日线 | O(N*W) |
| MESA频谱 | 83 | 趋势/震荡 | max_lag=40, intervals=[6,8,12,24] | 环境判别 | 分钟 | O(N*p²) |
| RSRS原始 | 59 | 择时 | N=18, M=600 | 宽基指数 | 日线 | O(N*M) |
| RSRS钝化 | 59 | 择时(改进) | dampen_power=2 | 震荡市 | 日线 | O(N*M) |
| RSRS成交额加权 | 59 | 择时(改进) | use_wls=True | 中小盘 | 日线 | O(N*M) |
| 趋与势-单调 | 81 | 趋势强度 | normalization=monotone | 所有 | 日线 | O(N) |
| 趋与势-复合 | 81 | 趋势强度 | normalization=compound | 所有 | 日线 | O(N) |
| 拥挤率 | 82 | 顶底判断 | top_pct=0.05 | 大盘 | 日线 | O(N*S) |

---

## 六、异常处理与边界情况总览

### 6.1 数据层异常

| 异常类型 | 检测方式 | 处理策略 |
|----------|----------|----------|
| 数据不足 | len < min_required | 返回空信号或NEUTRAL |
| 缺失值 | isnull().sum() > threshold | 前向填充 > 插值 > 丢弃 |
| 异常值 | 3σ原则 / IQR | 中位数替换 |
| 停牌 | volume=0 & price不变 | 标记is_suspended，跳过计算 |
| 涨跌停 | price == limit_price | 标记，信号强度打折 |
| 复权断裂 | 价格跳空 > 10% | 检测除权日，重新计算复权因子 |

### 6.2 指标层异常

| 异常类型 | 检测方式 | 处理策略 |
|----------|----------|----------|
| 除零 | denominator == 0 | 加epsilon(1e-10) |
| NaN传播 | isnull().any() | 向前填充或返回None |
| 数值溢出 | abs(value) > 1e10 | 截断或返回None |
| 矩阵奇异 | np.linalg.cond > 1e10 | 使用伪逆或正则化 |
| AR不平稳 | 特征根模 >= 1 | 增加差分阶数 |

### 6.3 融合层异常

| 异常类型 | 检测方式 | 处理策略 |
|----------|----------|----------|
| 信号冲突 | buy_count > 0 and sell_count > 0 | 降低仓位或观望 |
| 权重和为0 | sum(weights) == 0 | 使用等权重 |
| 全中性信号 | all(signal == NEUTRAL) | 保持当前仓位 |
| 极端置信度 | confidence > 1.0 | 截断到1.0 |

---

## 七、与 Backtrader 集成

```python
class SignalPipelineStrategy(bt.Strategy):
    """
    将 SignalPipeline 接入 Backtrader 的策略类
    
    特性:
    - 支持多指标动态加载
    - 支持参数优化
    - 支持实时信号日志
    - 支持止损/止盈自动执行
    """
    
    params = (
        ('indicators', ['chan_theory', 'rsrs', 'trend_momentum']),
        ('weights', [0.3, 0.3, 0.2]),
        ('fusion_strategy', 'regime_adaptive'),
        ('risk_per_trade', 0.02),  # 每笔风险
        ('max_position', 0.8),     # 最大仓位
    )
    
    def __init__(self):
        # 初始化流水线
        self.pipeline = SignalPipeline(
            indicators=self.p.indicators,
            weights=self.p.weights,
            fusion_strategy=self.p.fusion_strategy
        )
        
        # 数据缓冲区
        self.data_buffer = deque(maxlen=500)
        
        # 信号日志
        self.signal_log = []
        
        # 订单跟踪
        self.order = None
    
    def next(self):
        # 收集数据
        self.data_buffer.append({
            'datetime': self.datas[0].datetime[0],
            'open': self.datas[0].open[0],
            'high': self.datas[0].high[0],
            'low': self.datas[0].low[0],
            'close': self.datas[0].close[0],
            'volume': self.datas[0].volume[0],
        })
        
        # 数据长度检查
        if len(self.data_buffer) < 100:
            return
        
        # 转换为 MarketData
        market_data = MarketData.from_buffer(self.data_buffer)
        
        # 生成融合信号
        fused = self.pipeline.run(market_data)
        
        # 记录信号
        self.signal_log.append(fused)
        
        # 执行交易
        self._execute_trade(fused)
    
    def _execute_trade(self, fused: FusedSignal):
        """
        执行交易逻辑
        
        规则:
        1. 有仓位且卖出信号 → 平仓
        2. 无仓位且买入信号 → 开仓
        3. 根据置信度调整仓位
        """
        if self.position:
            if fused.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
                self.close()
        else:
            if fused.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                # 计算仓位
                position_size = self._calculate_position_size(fused)
                self.buy(size=position_size)
    
    def _calculate_position_size(self, fused: FusedSignal) -> int:
        """
        基于Kelly公式计算仓位
        
        position = capital * risk_per_trade * confidence / stop_loss_distance
        """
        capital = self.broker.get_value()
        risk = capital * self.p.risk_per_trade
        
        # 根据置信度和仓位建议调整
        adjusted_risk = risk * fused.confidence * fused.position_suggestion
        
        # 限制最大仓位
        max_risk = capital * self.p.max_position
        adjusted_risk = min(adjusted_risk, max_risk)
        
        # 转换为股数
        price = self.datas[0].close[0]
        size = int(adjusted_risk / price / 100) * 100  # A股100股整数倍
        
        return max(size, 100)  # 最小100股
```

---

## 八、性能优化建议

| 优化点 | 方法 | 预期收益 |
|--------|------|----------|
| 缠论标准化 | 使用numpy替代numpy结构化数组 | 3-5x |
| 核回归 | 使用FFT加速卷积 | 10x |
| MESA AR拟合 | 使用Levinson-Durbin递归 | 2x |
| RSRS滚动回归 | 使用递推最小二乘(RLS) | 5x |
| 多指标并行 | 使用concurrent.futures | N倍(N=指标数) |
| 缓存 | 指标结果缓存（lru_cache） | 避免重复计算 |
| 增量计算 | 只计算新增数据 | O(1) per bar |

---

## 九、测试策略

```python
class TestSignalPipeline(unittest.TestCase):
    """信号流水线测试套件"""
    
    def test_chan_theory_insufficient_data(self):
        """测试缠论数据不足情况"""
        data = MarketData(close=np.random.rand(5), ...)
        with self.assertRaises(InsufficientDataError):
            ChanTheoryGenerator().generate(data)
    
    def test_mesa_non_stationary(self):
        """测试MESA非平稳序列处理"""
        data = MarketData(close=np.cumsum(np.random.rand(1000)), ...)
        signals = MESAGenerator().generate(data)
        self.assertTrue(all(s.metadata.get('mesa_status') == 'non_stationary' 
                           for s in signals))
    
    def test_rsrs_division_by_zero(self):
        """测试RSRS除零保护"""
        data = MarketData(
            high=np.ones(700),
            low=np.ones(700),
            ...
        )
        signals = RSRSGenerator().generate(data)
        # 应该不抛异常
        self.assertIsInstance(signals, list)
    
    def test_fusion_conflict_resolution(self):
        """测试融合冲突消解"""
        signals = [
            Signal(source='chan_theory', type=BUY, strength=0.8),
            Signal(source='mesa', type=SELL, strength=0.7),
        ]
        fused = SignalFusion().fuse(signals, market_data)
        self.assertLess(fused.confidence, 0.7)  # 冲突应降低置信度
    
    def test_backtrader_integration(self):
        """测试Backtrader集成"""
        cerebro = bt.Cerebro()
        cerebro.addstrategy(SignalPipelineStrategy)
        cerebro.run()
        # 应该不抛异常
```

---

## 十、后续扩展方向

1. **在线学习**: 使用历史信号准确率动态调整指标权重
2. **多标的联动**: 板块/行业指数信号传导
3. **事件驱动**: 财报、政策事件对信号的修正
4. **强化学习**: 基于信号组合的自动交易策略优化
5. **实时流处理**: Kafka + Flink 实现毫秒级信号推送
6. **可视化大屏**: Grafana + WebSocket 实时监控
