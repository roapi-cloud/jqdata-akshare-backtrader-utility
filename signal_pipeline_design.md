# 技术指标与信号生成流水线 - 设计文档

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        SignalPipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐              │
│  │  Data    │───▶│  Indicator   │───▶│  Signal  │              │
│  │  Layer   │    │  Calculator  │    │ Generator│              │
│  └──────────┘    └──────────────┘    └──────────┘              │
│                            │                      │             │
│                            ▼                      ▼             │
│                     ┌──────────────┐    ┌──────────────┐        │
│                     │  Indicator   │    │   Signal     │        │
│                     │  Registry    │    │   Fusion     │        │
│                     └──────────────┘    └──────────────┘        │
│                                                 │               │
│                                                 ▼               │
│                                          ┌──────────────┐       │
│                                          │   Output     │       │
│                                          │  (CSV/Chart) │       │
│                                          └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## 二、核心设计原则

### 2.1 统一数据输入
所有指标接收相同格式的 DataFrame:
```python
# 标准 OHLCV 格式
DataFrame columns: ['datetime', 'open', 'high', 'low', 'close', 'volume']
```

### 2.2 信号标准化输出
所有指标输出统一信号格式:
```python
@dataclass
class Signal:
    timestamp: datetime        # 信号产生时间
    asset: str                 # 标的代码
    signal_type: SignalType    # BUY / SELL / NEUTRAL
    strength: float            # 信号强度 [0.0, 1.0]
    source: str                # 指标来源标识
    price: float               # 触发时价格
    stop_loss: Optional[float] # 建议止损价
    metadata: dict             # 附加信息（因指标而异）
```

### 2.3 指标可插拔
通过注册表模式实现指标的动态加载与组合:
```python
# 注册指标
registry.register("chan_theory", ChanTheorySignalGenerator)
registry.register("rounding_bottom", RoundingBottomSignalGenerator)
registry.register("mesa", MESASignalGenerator)

# 组合使用
pipeline = SignalPipeline(registry=registry)
pipeline.add_indicator("chan_theory", weight=0.3)
pipeline.add_indicator("rounding_bottom", weight=0.25)
pipeline.add_indicator("mesa", weight=0.2)
```

## 三、核心类设计

### 3.1 SignalType 枚举
```python
class SignalType(Enum):
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2
```

### 3.2 BaseSignalGenerator 抽象基类
```python
class BaseSignalGenerator(ABC):
    """所有信号生成器的基类"""
    
    name: str  # 指标名称
    
    @abstractmethod
    def generate(self, data: pd.DataFrame) -> List[Signal]:
        """
        输入: OHLCV DataFrame
        输出: Signal 列表
        """
        pass
    
    @abstractmethod
    def get_latest_signal(self, data: pd.DataFrame) -> Signal:
        """获取最新一根K线的信号"""
        pass
```

### 3.3 IndicatorRegistry 注册表
```python
class IndicatorRegistry:
    """指标注册与发现"""
    
    def register(self, name: str, generator_class: type)
    def get(self, name: str) -> BaseSignalGenerator
    def list_all(self) -> List[str]
    def create_pipeline(self, names: List[str], weights: List[float]) -> SignalPipeline
```

### 3.4 SignalPipeline 流水线
```python
class SignalPipeline:
    """信号生成与融合流水线"""
    
    def add_indicator(self, name: str, weight: float = 1.0)
    def run(self, data: pd.DataFrame) -> SignalReport
    def get_fused_signal(self, data: pd.DataFrame) -> FusedSignal
```

### 3.5 SignalFusion 融合器
```python
class SignalFusion:
    """多信号融合策略"""
    
    # 融合方法
    - weighted_vote(): 加权投票
    - majority_vote(): 简单多数
    - consensus(): 共识机制（需N个以上同向信号）
    - conflict_resolve(): 冲突解决规则
```

## 四、样例实现：缠论信号生成器

### 4.1 缠论信号逻辑

基于你现有的 `16 研究 缠论工具.ipynb`，提取关键信号:

| 信号类型 | 触发条件 | 强度计算 |
|----------|----------|----------|
| BUY | 出现底分型 + 笔向上 | 笔的长度 / ATR |
| SELL | 出现顶分型 + 笔向下 | 笔的长度 / ATR |
| STRONG_BUY | 线段底确认 + 三买 | 结构完整度 |
| STRONG_SELL | 线段顶确认 + 三卖 | 结构完整度 |

### 4.2 伪代码

```python
class ChanTheorySignalGenerator(BaseSignalGenerator):
    name = "chan_theory"
    
    def __init__(self, min_bi_length: float = 0.03):
        self.min_bi_length = min_bi_length  # 最小笔长度阈值
    
    def generate(self, data: pd.DataFrame) -> List[Signal]:
        # 1. 初始化缠论处理器
        kbar_chan = KBarChan(data)
        
        # 2. 标准化K线（处理包含关系）
        kbar_chan.standardize()
        
        # 3. 识别笔
        bi_df = kbar_chan.process_bi()
        
        # 4. 识别线段
        xd_df = kbar_chan.process_xd()
        
        # 5. 生成信号
        signals = []
        for i, row in enumerate(bi_df):
            signal = self._analyze_bi(row, bi_df, xd_df, data)
            if signal:
                signals.append(signal)
        
        return signals
    
    def _analyze_bi(self, bi, bi_df, xd_df, raw_data) -> Optional[Signal]:
        """分析单笔产生信号"""
        
        # 判断笔类型
        if bi['tb'] == TopBotType.bot.value:  # 底分型
            # 计算笔长度
            bi_length = abs(bi['close'] - prev_bi['close'])
            atr = calculate_atr(raw_data, period=14)
            
            # 强度 = 笔长度 / ATR
            strength = min(bi_length / atr, 1.0)
            
            if strength > self.min_bi_length:
                return Signal(
                    timestamp=bi['date'],
                    asset="UNKNOWN",  # 由外部注入
                    signal_type=SignalType.BUY,
                    strength=strength,
                    source="chan_theory",
                    price=bi['close'],
                    stop_loss=bi['low'],
                    metadata={
                        'bi_type': 'bottom',
                        'bi_length': bi_length,
                        'xd_confirmed': self._is_xd_confirmed(bi, xd_df)
                    }
                )
        
        elif bi['tb'] == TopBotType.top.value:  # 顶分型
            # 类似逻辑，返回 SELL 信号
            ...
```

## 五、其他指标整合清单

| 序号 | 指标 | 源文件 | 信号类型 | 优先级 |
|------|------|--------|----------|--------|
| 1 | 缠论笔/线段 | 16 缠论工具.ipynb | 趋势转折 | P0 |
| 2 | 圆弧底 | 57 圆弧底.ipynb | 底部反转 | P0 |
| 3 | MESA频谱 | 83 MESA.ipynb | 趋势/震荡判别 | P1 |
| 4 | 通达信公式 | 92 myTT通达信.ipynb | 多种 | P1 |
| 5 | RSRS择时 | 59/60 RSRS.ipynb | 顶底判断 | P1 |
| 6 | 波动率牛熊 | 63 华泰波动率.ipynb | 牛熊指标 | P2 |
| 7 | C-VIX | 64 C-VIX.ipynb | 恐慌指数 | P2 |
| 8 | 趋势动量 | 81 趋与势.ipynb | 趋势强度 | P1 |
| 9 | 拥挤率 | 82 拥挤率.ipynb | 顶底判断 | P2 |
| 10 | 市场宽度 | 45/52/97 市场宽度.ipynb | 大盘情绪 | P2 |

## 六、信号融合策略

### 6.1 加权投票算法
```python
def weighted_vote(signals: List[Signal], weights: Dict[str, float]) -> FusedSignal:
    buy_score = 0
    sell_score = 0
    
    for signal in signals:
        weight = weights.get(signal.source, 1.0)
        if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
            buy_score += signal.strength * weight * abs(signal.signal_type.value)
        elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
            sell_score += signal.strength * weight * abs(signal.signal_type.value)
    
    net_score = buy_score - sell_score
    
    if net_score > threshold_buy:
        return FusedSignal(type=BUY, confidence=normalize(net_score))
    elif net_score < threshold_sell:
        return FusedSignal(type=SELL, confidence=normalize(abs(net_score)))
    else:
        return FusedSignal(type=NEUTRAL, confidence=0)
```

### 6.2 冲突解决规则
```
优先级: STRONG_BUY/STRONG_SELL > 趋势类指标 > 震荡类指标 > 形态类指标

冲突场景:
- 缠论看涨 + MESA看跌 → 降低仓位或观望
- 圆弧底 + 趋势向下 → 等待趋势确认再入场
- 3个以上指标同向 → 提高仓位权重
```

## 七、与 Backtrader 集成

### 7.1 适配器模式
```python
class SignalPipelineStrategy(BaseStrategy):
    """将 SignalPipeline 接入 Backtrader"""
    
    params = (
        ('indicators', ['chan_theory', 'rounding_bottom']),
        ('weights', [0.3, 0.25]),
    )
    
    def __init__(self):
        self.pipeline = SignalPipeline()
        for name, weight in zip(self.p.indicators, self.p.weights):
            self.pipeline.add_indicator(name, weight)
    
    def next(self):
        # 获取历史数据
        data = self.get_recent_data(periods=100)
        
        # 生成融合信号
        fused = self.pipeline.get_fused_signal(data)
        
        # 执行交易逻辑
        if fused.type == SignalType.BUY and not self.position:
            self.buy()
        elif fused.type == SignalType.SELL and self.position:
            self.sell()
```

## 八、输出格式

### 8.1 信号日志 (CSV)
```csv
timestamp,asset,signal_type,strength,source,price,stop_loss,metadata
2024-01-15,sh600000,BUY,0.75,chan_theory,12.5,11.8,"{""bi_length"":0.05}"
2024-01-15,sh600000,BUY,0.60,rounding_bottom,12.5,11.5,"{""correlation"":0.85}"
```

### 8.2 融合信号报告
```json
{
  "timestamp": "2024-01-15",
  "asset": "sh600000",
  "fused_signal": "BUY",
  "confidence": 0.72,
  "component_signals": {
    "chan_theory": {"type": "BUY", "strength": 0.75},
    "rounding_bottom": {"type": "BUY", "strength": 0.60},
    "mesa": {"type": "NEUTRAL", "strength": 0.30}
  },
  "action": "买入，仓位建议 60%"
}
```

## 九、文件组织结构

```
signal_pipeline/
├── __init__.py
├── core/
│   ├── signal.py           # Signal 数据类
│   ├── base_generator.py   # BaseSignalGenerator 抽象基类
│   ├── registry.py         # IndicatorRegistry
│   ├── pipeline.py         # SignalPipeline
│   └── fusion.py           # SignalFusion 融合器
├── generators/
│   ├── chan_theory.py      # 缠论信号生成器
│   ├── rounding_bottom.py  # 圆弧底信号生成器
│   ├── mesa.py             # MESA 信号生成器
│   ├── tdx_formulas.py     # 通达信公式集
│   └── ...
├── utils/
│   ├── indicators.py       # 通用指标计算工具
│   └── visualization.py    # 可视化
└── examples/
    └── demo_pipeline.ipynb # 使用示例
```

## 十、后续扩展方向

1. **机器学习增强**: 用历史信号+价格数据训练分类器，优化信号权重
2. **动态权重**: 根据市场环境（趋势/震荡）自动调整指标权重
3. **多时间框架**: 同时分析日线/周线/分钟线，跨周期信号确认
4. **实时流处理**: 接入实时数据源，支持盘中信号推送
