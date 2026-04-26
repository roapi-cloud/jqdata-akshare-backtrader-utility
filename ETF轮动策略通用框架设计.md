# ETF轮动策略通用框架设计

## 一、策略类型概述

### 核心逻辑
ETF轮动策略的核心思想是：**在多个ETF品种之间，定期选择表现最强（动量最高）的品种持有，同时通过择时信号控制仓位**。其本质是"强者恒强"的动量效应 + "趋势过滤"的择时保护。

### 适用场景
- A股市场ETF（宽基/行业/商品/海外/债券）
- 中低频调仓（日频/周频/月频）
- 适合趋势性行情，震荡市可能频繁磨损

### 风险特征
- **优势**: 分散风险、自动追涨杀跌、回撤可控（配合择时）
- **劣势**: 趋势反转时滞后、震荡市频繁换仓磨损、极端行情可能失效

---

## 二、子策略变体分类

| 编号 | 策略变体 | 核心差异 | 代表文件 |
|------|---------|---------|---------|
| V1 | **基础动量轮动** | 年化收益×R²打分，无择时 | `03 核心资产轮动`, `43 窄基ETF轮动`, `17 多品种+EPO` |
| V2 | **动量+RSRS择时** | 标准RSRS(斜率zscore×R²) | `88 基于动量因子+RSRS`, `17 8年13倍`, `55 入门1.0` |
| V3 | **动量+RSRS+MA双择时** | RSRS + MA均线趋势确认 | `02 魔改3小优化`, `75 入门2.0`, `31 核心资产+RSRS每日` |
| V4 | **动量+钝化RSRS** | RSRS分数乘以波动率分位数调整 | `24 宽基钝化RSRS` |
| V5 | **动量+RSRS+卡尔曼滤波** | 动量计算前用卡尔曼滤波降噪 | `48 卡尔曼滤波`, `16 升级`, `58 北上择时` |
| V6 | **动量+RSRS+低通滤波** | 动量计算前用FFT低通滤波 | `38 低通滤波` |
| V7 | **动量+RSRS+北向资金** | 北向资金净流入作为额外过滤 | `38 北向资金择时`, `58 北上择时+股债平衡` |
| V8 | **乖离动量** | 相对MA90均线的乖离率做动量 | `16 升级`, `60 v2`, `50 V2.1`, `10 多因子改进版` |
| V9 | **动量一阶导数风控** | 监控动量变化速度，过快则空仓 | `10 多因子改进版`, `50 V2.1` |
| V10 | **BBI多空指标轮动** | 用BBI=(3MA+6MA+12MA+24MA)/4排序 | `57 韶华研究`, `21 行业ETF+BBI` |
| V11 | **涨幅+均线差值轮动** | 周期涨幅+均线差值双因子 | `82 动态选择etf`, `25 基本不耍六毛`, `30 宽基轮动` |
| V12 | **成交量筛选轮动** | 先按成交量筛ETF池再轮动 | `82 动态选择etf`, `25 基本不耍六毛` |
| V13 | **股债平衡+回撤控制** | 根据回撤状态动态分配股债比例 | `76 国债ETF增强`, `58 股债平衡` |
| V14 | **EPO优化权重** | 用Exponential Portfolio Optimization分配权重 | `17 多品种+EPO优化` |
| V15 | **核心资产+反转因子** | 短期动量 - 长期动量/6（反转） | `38 核心资产增强版` |
| V16 | **MA乖离择时** | 相对60日MA的乖离率做择时（替代RSRS） | `66 MA乖离择时` |
| V17 | **T+0日内动量** | 开盘高开买入、收盘卖出 | `91 T0动量策略` |
| V18 | **多类别轮动** | 按A股/海外/商品分类分别轮动 | `64 多类别低回撤` |
| V19 | **MACD条件轮动** | 用MACD正负决定持仓品种 | `85 稳健型ETF` |

---

## 三、通用代码框架

### 3.1 框架架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     ETFRotationStrategy                         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ ETFPoolManager│→│ MomentumCalc  │→│    TimingSignalGen   │  │
│  │ (候选池管理)  │  │ (动量计算器)   │  │    (择时信号器)       │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│         │                  │                      │             │
│         ▼                  ▼                      ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  FilterPipe  │→│   EFTRanker   │→│  PositionAllocator   │  │
│  │ (过滤管道)    │  │  (ETF排序器)   │  │   (仓位分配器)        │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                    │            │
│                                                    ▼            │
│                                          ┌──────────────────┐  │
│                                          │  TradeExecutor   │  │
│                                          │  (交易执行器)     │  │
│                                          └──────────────────┘  │
│                                                    │            │
│                   ┌────────────────────────────────┘            │
│                   ▼                                             │
│          ┌──────────────────┐                                   │
│          │  RiskManager     │                                   │
│          │  (风控管理器)     │                                   │
│          └──────────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心模块定义

#### 模块1: ETF候选池管理器 (ETFPoolManager)

```python
class ETFPoolManager:
    """管理ETF候选池，支持按类别筛选和动态过滤"""
    
    # 实际文件中的ETF池定义模式 (来自 `88 基于动量因子+RSRS`):
    # g.index_pool = [
    #     ('000016.XSHG', '510050.XSHG'),  # 上证50
    #     ('000300.XSHG', '510300.XSHG'),  # 沪深300
    #     ('399905.XSHE', '510500.XSHG'),  # 中证500
    #     ('399006.XSHE', '159915.XSHE'),  # 创业板指
    # ]
    
    # 核心资产轮动池 (来自 `03 核心资产轮动`):
    # g.etf_pool = [
    #     '518880.XSHG',  # 黄金ETF（大宗商品）
    #     '513100.XSHG',  # 纳指100（海外资产）
    #     '159915.XSHE',  # 创业板100（成长股）
    #     '510180.XSHG',  # 上证180（价值股）
    # ]
    
    # 窄基ETF池 (来自 `43 窄基ETF轮动`):
    # g.etf_pool = [
    #     '161725.XSHE',  # 白酒
    #     '159992.XSHE',  # 创新药
    #     '515700.XSHG',  # 新能源车
    #     '518880.XSHG',  # 黄金ETF
    #     '513100.XSHG',  # 纳指100
    # ]
    
    ETF_CATEGORIES = {
        'broad': ['510050.XSHG', '510300.XSHG', '510500.XSHG', '159915.XSHE', '512100.XSHG'],
        'sector': ['159928.XSHE', '512010.XSHE', '512880.XSHG', '512660.XSHG'],
        'commodity': ['518880.XSHG', '159985.XSHE', '159980.XSHG'],
        'overseas': ['513100.XSHG', '513500.XSHG', '513030.XSHG', '159920.XSHE'],
        'bond': ['511010.XSHG', '511260.XSHG', '511880.XSHG'],
    }
    
    def get_pool(self, categories: List[str] = None) -> List[str]:
        """获取ETF池，支持按类别组合"""
        if categories is None:
            return self.default_pool
        pool = []
        for cat in categories:
            pool.extend(self.ETF_CATEGORIES.get(cat, []))
        return list(set(pool))
    
    def filter_available(self, etf_list: List[str], date: str, min_list_days: int = 20) -> List[str]:
        """过滤未上市或上市不足min_list_days天的ETF"""
        # 来自 `57 韶华研究`:
        # by_date = get_trade_days(end_date=lastd_date, count=5)[0]
        # all_funds = get_all_securities(types='fund', date=by_date)
        # for idx in g.etf_list:
        #     if idx in all_indexes.index:
        #         etf = g.etf_list[idx]
        #         if etf in all_funds.index:
        #             g.available_indexs.append(idx)
        pass
```

#### 模块2: 动量计算器 (MomentumCalculator)

```python
class MomentumCalculator:
    """计算ETF动量得分，支持多种动量方法"""
    
    def calculate(self, etf_list: List[str], date: str, period: int, method: str) -> pd.DataFrame:
        """
        计算动量得分
        method: 'annualized_r2' | 'slope' | 'bias' | 'simple_return'
        """
        scores = {}
        for etf in etf_list:
            if method == 'annualized_r2':
                scores[etf] = self._annualized_r2_momentum(etf, period)
            elif method == 'slope':
                scores[etf] = self._slope_momentum(etf, period)
            elif method == 'bias':
                scores[etf] = self._bias_momentum(etf, period)
            elif method == 'kalman_slope':
                scores[etf] = self._kalman_slope_momentum(etf, period)
            elif method == 'fft_slope':
                scores[etf] = self._fft_slope_momentum(etf, period)
        return pd.DataFrame(scores.items(), columns=['etf', 'score']).sort_values('score', ascending=False)
    
    def _annualized_r2_momentum(self, etf: str, period: int) -> float:
        """
        年化收益率 × R² (最常用)
        来自 `88 基于动量因子+RSRS` 的 get_socre():
        """
        data = attribute_history(etf, period, '1d', ['close'])
        y = np.log(data.close)
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        return annualized_returns * r_squared
    
    def _slope_momentum(self, etf: str, period: int) -> float:
        """
        简单斜率动量
        来自 `02 魔改3小优化` 的 get_rank():
        """
        data = attribute_history(etf, period, '1d', ['close'])
        score = np.polyfit(np.arange(len(data)), data.close / data.close[0], 1)[0]
        return score
    
    def _bias_momentum(self, etf: str, period: int, bias_period: int = 90) -> float:
        """
        乖离动量 (相对MA的乖离率拟合斜率)
        来自 `16 升级` 的 get_rank():
        """
        data = attribute_history(etf, bias_period + period, '1d', ['close'])
        bias = (data.close / data.close.rolling(bias_period).mean())[-period:]
        score = np.polyfit(np.arange(period), bias / bias[0], 1)[0].real
        return score
    
    def _kalman_slope_momentum(self, etf: str, period: int) -> float:
        """
        卡尔曼滤波后的斜率动量
        来自 `48 卡尔曼滤波` 的 get_rank():
        """
        from pykalman import KalmanFilter
        data = attribute_history(etf, 250, '1d', ['close'])
        dr = np.log(data.close / data.close[0])
        pred_data = self._kalman_filter(np.array(dr), damping=0.15)
        score = np.polyfit(np.arange(period), pred_data[-period:], 1)[0]
        return score
    
    def _fft_slope_momentum(self, etf: str, period: int) -> float:
        """
        FFT低通滤波后的斜率动量
        来自 `38 低通滤波` 的 get_rank():
        """
        data = attribute_history(etf, 250, '1d', ['close'])
        dr = np.log(data.close / data.close[0])
        newdr = self._fft_filter(fs=60, N=250, dr=dr)
        score = np.polyfit(np.arange(period), newdr[-period:], 1)[0].real
        return score
    
    @staticmethod
    def _kalman_filter(observations, damping=1):
        from pykalman import KalmanFilter
        kf = KalmanFilter(
            initial_state_mean=observations[0],
            initial_state_covariance=damping,
            transition_matrices=1,
            observation_covariance=damping,
            transition_covariance=0.1)
        pre, _ = kf.smooth(observations)
        return pre
    
    @staticmethod
    def _fft_filter(fs, N, dr):
        y = np.fft.fft(dr)
        for i in range(len(y)):
            if (i > fs) and (i < N - fs):
                y[i] = 0.0
        return np.fft.ifft(y)
```

#### 模块3: 择时信号器 (TimingSignalGenerator)

```python
class TimingSignalGenerator:
    """生成买卖信号，支持多种择时方法"""
    
    def generate_signal(self, ref_etf: str, date: str, method: str, **kwargs) -> str:
        """
        返回: "BUY" | "SELL" | "KEEP"
        """
        if method == 'rsrs':
            return self._rsrs_signal(ref_etf, date, **kwargs)
        elif method == 'rsrs_ma':
            return self._rsrs_ma_signal(ref_etf, date, **kwargs)
        elif method == 'rsrs_blunt':
            return self._rsrs_blunt_signal(ref_etf, date, **kwargs)
        elif method == 'ma_bias':
            return self._ma_bias_signal(ref_etf, date, **kwargs)
        elif method == 'north_money':
            return self._north_money_signal(ref_etf, date, **kwargs)
        elif method == 'bbi':
            return self._bbi_signal(ref_etf, date, **kwargs)
        elif method == 'volume_emotion':
            return self._volume_emotion_signal(ref_etf, date, **kwargs)
        elif method == 'none':
            return "BUY"
        return "KEEP"
    
    def _rsrs_signal(self, etf: str, date: str, N: int = 18, M: int = 600, 
                     threshold: float = 0.7, slope_series: List = None) -> str:
        """
        标准RSRS择时
        来自 `88 基于动量因子+RSRS` 的 get_signal():
        """
        data = attribute_history(etf, N, '1d', ['high', 'low'])
        intercept, slope, r2 = self._get_ols(data.low, data.high)
        slope_series.append(slope)
        rsrs_score = self._get_zscore(slope_series[-M:]) * r2  # 修正标准分
        
        if rsrs_score > threshold:
            return "BUY"
        elif rsrs_score < -threshold:
            return "SELL"
        else:
            return "KEEP"
    
    def _rsrs_ma_signal(self, etf: str, date: str, N: int = 18, M: int = 600,
                        threshold: float = 0.7, mean_day: int = 20, 
                        mean_diff_day: int = 3, slope_series: List = None) -> str:
        """
        RSRS + MA双择时
        来自 `55 入门1.0` 的 get_timing_signal():
        """
        # MA信号
        close_data = attribute_history(etf, mean_day + mean_diff_day, '1d', ['close'])
        today_MA = close_data.close[mean_diff_day:].mean()
        before_MA = close_data.close[:-mean_diff_day].mean()
        
        # RSRS信号
        high_low_data = attribute_history(etf, N, '1d', ['high', 'low'])
        intercept, slope, r2 = self._get_ols(high_low_data.low, high_low_data.high)
        slope_series.append(slope)
        rsrs_score = self._get_zscore(slope_series[-M:]) * r2
        
        # 综合判断
        if rsrs_score > threshold and today_MA > before_MA:
            return "BUY"
        elif rsrs_score < -threshold and today_MA < before_MA:
            return "SELL"
        else:
            return "KEEP"
    
    def _rsrs_blunt_signal(self, etf: str, date: str, N: int = 18, M: int = 700,
                           threshold: float = 0.7, slope_series: List = None) -> str:
        """
        钝化RSRS择时 (用波动率分位数调整RSRS分数)
        来自 `24 宽基钝化RSRS` 的 get_timing_signal():
        """
        data = attribute_history(etf, M + N, '1d', ['high', 'low', 'close'])
        data['pre_close'] = data.shift(1)['close']
        data['ret'] = data['close'] / data['pre_close'] - 1
        ret_std = data['ret'].rolling(N).std()
        ret_quantile = ret_std.tail(M).rank(pct=True)[-1]
        
        intercept, slope, r2 = self._get_ols(data.tail(N).low, data.tail(N).high)
        slope_series_local = [self._get_ols(data.low[i:i+N], data.high[i:i+N])[1] for i in range(M)]
        slope_series_local.append(slope)
        zscore = self._get_zscore(slope_series_local[-M:])
        rsrs_score = zscore * r2 ** (2 * ret_quantile)  # 钝化公式
        
        if rsrs_score > threshold:
            return "BUY"
        elif rsrs_score < -threshold:
            return "SELL"
        else:
            return "KEEP"
    
    def _ma_bias_signal(self, etf: str, date: str, score_threshold: float = 4.0) -> str:
        """
        MA乖离择时 (替代RSRS)
        来自 `66 MA乖离择时` 的 get_timing_signal():
        """
        data = attribute_history(etf, 200, '1d', ['close'])
        data['bias'] = data.close / data.close.rolling(60).mean()
        data['biasma'] = data.bias.rolling(10).mean()
        score = self._get_zscore(data.biasma[-30:])
        
        if score > score_threshold:
            return 'BUY'
        if score < -score_threshold:
            return 'SELL'
        return 'KEEP'
    
    def _get_ols(self, x, y) -> Tuple[float, float, float]:
        """OLS回归: 返回 (intercept, slope, r2)"""
        slope, intercept = np.polyfit(x, y, 1)
        r2 = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        return (intercept, slope, r2)
    
    def _get_zscore(self, series: List) -> float:
        """计算标准分"""
        mean = np.mean(series)
        std = np.std(series)
        return (series[-1] - mean) / std if std > 0 else 0
```

### 3.3 RSRS择时模块详解

RSRS (Resistance Support Relative Strength) 是ETF轮动策略中最核心的择时方法，由广发证券研报提出。

#### 计算步骤

```python
def rsrs_full_calculation(etf: str, N: int = 18, M: int = 600) -> dict:
    """
    RSRS完整计算流程
    
    Step 1: 对过去N天的最低价(x)和最高价(y)做OLS线性回归
            y = slope * x + intercept
            得到斜率slope和拟合度r2
    
    Step 2: 维护一个长度为M的斜率时间序列 slope_series
            每天追加新的slope值
    
    Step 3: 计算当前slope的标准分(z-score)
            zscore = (slope_latest - mean(slope_series[-M:])) / std(slope_series[-M:])
    
    Step 4: 计算RSRS分数 (有多种变体)
            - 仅斜率:        rsrs = slope
            - 仅标准分:      rsrs = zscore
            - 修正标准分:    rsrs = zscore * r2          ← 最常用
            - 右偏标准分:    rsrs = zscore * r2 * slope
            - 钝化标准分:    rsrs = zscore * r2^(2*quantile)
    
    Step 5: 根据阈值判断信号
            rsrs > threshold  → BUY
            rsrs < -threshold → SELL
            其他              → KEEP
    
    参数说明:
        N=18: 回归窗口，研报推荐最优值
        M=600: 标准分计算窗口，研报推荐最优值
        threshold=0.7: 信号阈值，研报推荐最优值
    """
    pass
```

#### RSRS变体对比

| 变体 | 公式 | 效果 | 使用文件 |
|------|------|------|---------|
| 仅斜率 | `slope` | 一般 | 早期版本 |
| 仅标准分 | `zscore` | 不错 | 部分策略 |
| 修正标准分 | `zscore * r2` | **最佳** | `88`, `17`, `55`, `03` |
| 右偏标准分 | `zscore * r2 * slope` | 不错 | `88`, `31` |
| 钝化标准分 | `zscore * r2^(2*ret_quantile)` | 回撤小 | `24` |

#### 初始化斜率序列

```python
def initial_slope_series(etf: str, N: int, M: int) -> List[float]:
    """
    回测开始前初始化M天的斜率序列
    来自 `88 基于动量因子+RSRS` 的 initial_slope_series():
    """
    data = attribute_history(etf, N + M, '1d', ['high', 'low'])
    return [get_ols(data.low[i:i+N], data.high[i:i+N])[1] for i in range(M)]
```

### 3.4 框架配置类

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class ETFRotationConfig:
    """ETF轮动策略配置类"""
    
    # ========== ETF池配置 ==========
    etf_pool: List[str] = field(default_factory=lambda: [
        '510050.XSHG',  # 上证50ETF
        '510300.XSHG',  # 沪深300ETF
        '510500.XSHG',  # 中证500ETF
        '159915.XSHE',  # 创业板ETF
    ])
    etf_categories: List[str] = None  # ['broad', 'sector', 'commodity', 'overseas', 'bond']
    index_to_etf: Dict[str, str] = None  # 指数→ETF映射，如 {'000300.XSHG': '510300.XSHG'}
    
    # ========== 动量配置 ==========
    momentum_period: int = 20           # 动量计算周期 (常见: 10, 15, 20, 25, 27, 29)
    momentum_method: str = "annualized_r2"  # 动量方法
    # 可选: "annualized_r2" | "slope" | "bias" | "kalman_slope" | "fft_slope"
    
    # 乖离动量专用参数
    bias_period: int = 90               # 乖离动量的MA周期
    
    # ========== 择时配置 ==========
    timing_method: str = "rsrs_ma"      # 择时方法
    # 可选: "rsrs" | "rsrs_ma" | "rsrs_blunt" | "ma_bias" | "north_money" | "bbi" | "volume_emotion" | "none"
    
    # RSRS参数
    rsrs_n: int = 18                    # RSRS回归窗口
    rsrs_m: int = 600                   # RSRS标准分窗口
    rsrs_threshold: float = 0.7         # RSRS信号阈值
    rsrs_variant: str = "corrected"     # RSRS变体: "slope" | "zscore" | "corrected" | "right_skewed" | "blunt"
    
    # MA择时参数 (配合RSRS使用)
    ma_period: int = 20                 # MA均线周期
    ma_diff_period: int = 3             # MA比较偏移
    
    # 北向资金参数
    north_money_days: int = 3           # 北向资金统计天数
    
    # BBI参数
    bbi_periods: List[int] = field(default_factory=lambda: [3, 6, 12, 24])
    bbi_unit: str = '30m'              # BBI计算周期单位
    
    # ========== 仓位配置 ==========
    position_mode: str = "single"       # 仓位模式
    # 可选: "single" | "equal" | "momentum_weight" | "volatility_inverse" | "epo"
    max_etf_num: int = 1                # 最大持仓ETF数量
    
    # 股债平衡配置
    use_bond_balance: bool = False      # 是否启用股债平衡
    bond_etf: str = '511010.XSHG'       # 债券ETF (国债)
    money_etf: str = '511880.XSHG'      # 货币基金ETF (银华日利)
    stock_bond_ratios: Dict[int, tuple] = field(default_factory=lambda: {
        0: (0.3, 0.7),  # 正常: 30%股票 70%债券
        1: (0.4, 0.6),  # 轻度回撤
        2: (0.5, 0.5),  # 重度回撤
    })
    
    # ========== 调仓配置 ==========
    rebalance_frequency: str = "daily"  # 调仓频率: "daily" | "weekly" | "monthly"
    rebalance_time: str = "9:30"        # 调仓时间
    rebalance_weekday: int = 3          # 周频调仓的星期 (0=周一)
    rebalance_monthday: int = 1         # 月频调仓的日期
    
    # ========== 风控配置 ==========
    stop_loss_pct: float = -90          # 止损百分比 (-90表示几乎不止损)
    intraday_stop_loss: bool = False    # 是否启用盘中止损
    intraday_ma_period: int = 20        # 盘中止损MA周期 (60分钟线)
    momentum_1diff_threshold: float = 19  # 动量一阶导数风控阈值
    max_drawdown_level: bool = False    # 是否启用最大回撤分级
    
    # ========== 过滤配置 ==========
    filter_paused: bool = True          # 过滤停牌
    filter_st: bool = True              # 过滤ST
    filter_limitup: bool = True         # 过滤涨停
    filter_limitdown: bool = True       # 过滤跌停
    min_list_days: int = 20             # 最小上市天数
    
    # ========== 交易成本配置 ==========
    open_commission: float = 0.0003     # 买入佣金
    close_commission: float = 0.0003    # 卖出佣金
    slippage: float = 0.001             # 滑点
    min_commission: float = 5           # 最低佣金
```

### 3.5 框架主类

```python
class ETFRotationStrategy:
    """ETF轮动策略主类"""
    
    def __init__(self, config: ETFRotationConfig):
        self.config = config
        self.pool_manager = ETFPoolManager(config)
        self.momentum_calc = MomentumCalculator()
        self.timing_gen = TimingSignalGenerator()
        self.ranker = EFTRanker()
        self.allocator = PositionAllocator(config)
        self.executor = TradeExecutor()
        self.risk_manager = RiskManager(config)
        
        # 状态变量
        self.slope_series = []
        self.rsrs_score_history = []
        self.stock_motion = {}  # 动量历史队列 (用于一阶导数风控)
    
    def initialize(self, context):
        """策略初始化 (聚宽initialize函数)"""
        c = self.config
        
        # 基础设置
        set_benchmark('000300.XSHG')
        set_option('use_real_price', True)
        set_option("avoid_future_data", True)
        set_slippage(FixedSlippage(c.slippage))
        set_order_cost(OrderCost(
            open_tax=0, close_tax=0,
            open_commission=c.open_commission,
            close_commission=c.close_commission,
            close_today_commission=0,
            min_commission=c.min_commission
        ), type='fund')
        log.set_level('order', 'error')
        
        # 初始化RSRS斜率序列
        self.slope_series = self._init_slope_series()
        
        # 设置定时任务
        self._setup_schedule(context)
    
    def rebalance(self, context):
        """
        核心调仓逻辑
        
        流程:
        1. 获取ETF候选池
        2. 过滤不可交易ETF
        3. 计算动量得分
        4. 生成择时信号
        5. ETF排序
        6. 仓位分配
        7. 执行交易
        """
        # Step 1: 获取候选池
        etf_pool = self.pool_manager.get_pool(self.config.etf_categories)
        
        # Step 2: 过滤
        etf_pool = self._apply_filters(context, etf_pool)
        
        # Step 3: 计算动量
        momentum_df = self.momentum_calc.calculate(
            etf_pool, 
            context.current_dt,
            self.config.momentum_period,
            self.config.momentum_method
        )
        
        # Step 4: 择时信号
        timing_signal = self.timing_gen.generate_signal(
            ref_etf='000300.XSHG',
            date=context.current_dt,
            method=self.config.timing_method,
            N=self.config.rsrs_n,
            M=self.config.rsrs_m,
            threshold=self.config.rsrs_threshold,
            slope_series=self.slope_series,
            mean_day=self.config.ma_period,
            mean_diff_day=self.config.ma_diff_period,
        )
        
        # Step 5: 排序 (结合择时信号)
        ranked_etfs = self.ranker.rank(momentum_df, timing_signal)
        
        # Step 6: 仓位分配
        target_positions = self.allocator.allocate(
            target_etfs=ranked_etfs[:self.config.max_etf_num],
            total_value=context.portfolio.total_value,
            timing_signal=timing_signal,
        )
        
        # Step 7: 执行交易
        self.executor.execute(
            current_positions=dict(context.portfolio.positions),
            target_positions=target_positions,
        )
        
        # 风控检查
        self.risk_manager.check(context)
    
    def _init_slope_series(self) -> List[float]:
        """初始化RSRS斜率序列"""
        c = self.config
        data = attribute_history('000300.XSHG', c.rsrs_n + c.rsrs_m, '1d', ['high', 'low'])
        slopes = []
        for i in range(c.rsrs_m):
            low = data.low[i:i+c.rsrs_n]
            high = data.high[i:i+c.rsrs_n]
            slope, _ = np.polyfit(low, high, 1)
            slopes.append(slope)
        return slopes
    
    def _apply_filters(self, context, etf_list: List[str]) -> List[str]:
        """应用过滤条件"""
        c = self.config
        if c.filter_paused:
            etf_list = self._filter_paused(etf_list)
        if c.filter_st:
            etf_list = self._filter_st(etf_list)
        if c.filter_limitup:
            etf_list = self._filter_limitup(context, etf_list)
        if c.filter_limitdown:
            etf_list = self._filter_limitdown(context, etf_list)
        return etf_list
    
    def _filter_paused(self, stock_list):
        current_data = get_current_data()
        return [s for s in stock_list if not current_data[s].paused]
    
    def _filter_st(self, stock_list):
        current_data = get_current_data()
        return [s for s in stock_list 
                if not current_data[s].is_st 
                and 'ST' not in current_data[s].name 
                and '*' not in current_data[s].name]
    
    def _filter_limitup(self, context, stock_list):
        current_data = get_current_data()
        return [s for s in stock_list 
                if s in context.portfolio.positions.keys() 
                or current_data[s].last_price < current_data[s].high_limit]
    
    def _filter_limitdown(self, context, stock_list):
        current_data = get_current_data()
        return [s for s in stock_list 
                if s in context.portfolio.positions.keys() 
                or current_data[s].last_price > current_data[s].low_limit]
```

#### 模块4: ETF排序器 (EFTRanker)

```python
class EFTRanker:
    """ETF排序器"""
    
    def rank(self, momentum_df: pd.DataFrame, timing_signal: str) -> List[str]:
        """
        根据动量得分排序
        来自 `88 基于动量因子+RSRS` 的 get_stock_pool():
        """
        if timing_signal == "SELL":
            return []
        # 按score降序排列
        return momentum_df.sort_values('score', ascending=False)['etf'].tolist()
```

#### 模块5: 仓位分配器 (PositionAllocator)

```python
class PositionAllocator:
    """仓位分配器"""
    
    def __init__(self, config: ETFRotationConfig):
        self.config = config
    
    def allocate(self, target_etfs: List[str], total_value: float, 
                 timing_signal: str) -> Dict[str, float]:
        """
        返回: {etf_code: target_value}
        """
        if timing_signal == "SELL" or not target_etfs:
            return {}
        
        mode = self.config.position_mode
        
        if mode == "single":
            # 全仓一只 (来自 `03 核心资产轮动`):
            # value = context.portfolio.available_cash / (target_num - len(hold_list))
            return {target_etfs[0]: total_value}
        
        elif mode == "equal":
            # 等权分配 (来自 `88 基于动量因子+RSRS`):
            # cash = context.portfolio.available_cash / stock_num
            n = len(target_etfs)
            value = total_value / n
            return {etf: value for etf in target_etfs}
        
        elif mode == "volatility_inverse":
            # 波动率倒数加权 (来自 `58 股债平衡`):
            # g.position["position"] = g.position.weight / g.position.wave ** 2
            return self._volatility_inverse(target_etfs, total_value)
        
        elif mode == "epo":
            # EPO优化权重 (来自 `17 多品种+EPO`):
            return self._epo_allocate(target_etfs, total_value)
        
        return {target_etfs[0]: total_value}
    
    def _volatility_inverse(self, etfs, total_value):
        """波动率倒数加权"""
        vols = {}
        for etf in etfs:
            data = attribute_history(etf, 60, '1d', ['close'])
            rets = np.log(data.close / data.close.shift(1)).dropna()
            vols[etf] = rets.std() * math.sqrt(250)
        
        inv_vols = {etf: 1/v for etf, v in vols.items()}
        total_inv = sum(inv_vols.values())
        return {etf: (inv_v / total_inv) * total_value for etf, inv_v in inv_vols.items()}
    
    def _epo_allocate(self, etfs, total_value):
        """EPO优化权重 (简化版)"""
        prices = get_price(etfs, count=250, frequency='daily', fields=['close'])['close']
        returns = prices.pct_change().dropna()
        signal = returns.mean()
        cov = returns.cov()
        weights = np.linalg.solve(cov.values, signal.values)
        weights = np.maximum(weights, 0)
        weights = weights / weights.sum()
        return {etf: w * total_value for etf, w in zip(etfs, weights)}
```

#### 模块6: 交易执行器 (TradeExecutor)

```python
class TradeExecutor:
    """交易执行器"""
    
    def execute(self, current_positions: Dict, target_positions: Dict) -> List[Dict]:
        """
        执行调仓
        来自 `55 入门1.0` 的 adjust_position():
        """
        orders = []
        current_set = set(current_positions.keys())
        target_set = set(target_positions.keys())
        
        # 卖出不在目标中的
        for etf in current_set - target_set:
            order_target_value(etf, 0)
            orders.append({'action': 'sell', 'etf': etf, 'value': 0})
        
        # 买入/调整目标中的
        for etf in target_set:
            target_value = target_positions[etf]
            if etf not in current_set or current_positions[etf].total_amount == 0:
                order_target_value(etf, target_value)
                orders.append({'action': 'buy', 'etf': etf, 'value': target_value})
        
        return orders
```

#### 模块7: 风控管理器 (RiskManager)

```python
class RiskManager:
    """风控管理器"""
    
    def __init__(self, config: ETFRotationConfig):
        self.config = config
        self.max_value = None
        self.last_value = None
    
    def check(self, context):
        """执行风控检查"""
        self._check_stop_loss(context)
        if self.config.intraday_stop_loss:
            self._check_intraday_stop(context)
        if self.config.max_drawdown_level:
            self._check_drawdown_level(context)
        if self.config.momentum_1diff_threshold:
            self._check_momentum_velocity(context)
    
    def _check_stop_loss(self, context):
        """止损检查 (来自 `17 8年13倍` 的 check_lose())"""
        for position in context.portfolio.positions.values():
            ret = 100 * (position.price / position.avg_cost - 1)
            if ret <= self.config.stop_loss_pct:
                order_target_value(position.security, 0)
    
    def _check_intraday_stop(self, context):
        """
        盘中动态止损 (60分钟线跌破MA20)
        来自 `16 升级` 的 hold_check():
        """
        for stk in context.portfolio.positions:
            dt = attribute_history(stk, 22, '60m', ['close'])
            dt['ma'] = dt.close / dt.close.rolling(20).mean()
            if dt['ma'].iloc[-1] < 1.0:
                order_target_value(stk, 0)
    
    def _check_drawdown_level(self, context):
        """
        回撤分级控制 (来自 `76 国债ETF增强` 的 cash_management())
        """
        total = context.portfolio.total_value
        if self.max_value is None:
            self.max_value = total
        
        if total < self.max_value * 0.95:
            level = 2
        elif total < self.max_value * 0.975:
            level = 1
        else:
            level = 0
        
        if total > self.max_value:
            self.max_value = total
        
        return level
    
    def _check_momentum_velocity(self, context):
        """
        动量变化速度风控 (来自 `10 多因子改进版`)
        如果动量一阶导数过大，则强制SELL
        """
        pass
```

---

## 四、典型策略映射示例

### 映射1: `88 基于动量因子的ETF轮动加上RSRS择时` → V2变体

```python
config = ETFRotationConfig(
    etf_pool=['510050.XSHG', '510300.XSHG', '510500.XSHG', '159915.XSHE', 
              '510880.XSHG', '159928.XSHE', '512010.XSHG'],
    momentum_period=15,
    momentum_method='annualized_r2',
    timing_method='rsrs_ma',
    rsrs_n=18, rsrs_m=600, rsrs_threshold=0.7,
    ma_period=20, ma_diff_period=3,
    position_mode='equal',
    max_etf_num=2,
    rebalance_frequency='weekly',
)
# 核心代码对应: get_socre() → MomentumCalculator._annualized_r2_momentum()
#              get_signal() → TimingSignalGenerator._rsrs_ma_signal()
#              change_position() → PositionAllocator.allocate() + TradeExecutor.execute()
```

### 映射2: `03 高评分ETF策略之核心资产轮动` → V1变体

```python
config = ETFRotationConfig(
    etf_pool=['518880.XSHG', '513100.XSHG', '159915.XSHE', '510180.XSHG'],
    momentum_period=25,
    momentum_method='annualized_r2',
    timing_method='none',  # 无择时
    position_mode='single',
    max_etf_num=1,
    rebalance_frequency='daily',
    rebalance_time='9:30',
)
# 核心代码对应: get_rank() → MomentumCalculator._annualized_r2_momentum()
#              trade() → 直接取rank_list[0]全仓买入
```

### 映射3: `24 宽基ETF动量轮动钝化RSRS择时` → V4变体

```python
config = ETFRotationConfig(
    etf_pool=['000300.XSHG', '000905.XSHG', '399006.XSHE'],  # 用指数代码
    momentum_period=29,
    momentum_method='annualized_r2',
    timing_method='rsrs_blunt',
    rsrs_n=18,
    rsrs_m={'000300.XSHG': 700, '000905.XSHG': 800, '399006.XSHE': 500},  # 每个标的独立参数
    rsrs_threshold={'000300.XSHG': 0.7, '000905.XSHG': 1.0, '399006.XSHE': 0.4},
    position_mode='single',
    max_etf_num=1,
    stop_loss_pct=-2,  # 组合市值2%极速下跌清仓
)
# 核心代码对应: get_timing_signal() → TimingSignalGenerator._rsrs_blunt_signal()
#              钝化公式: rsrs_score = zscore * r2**(2*ret_quantile)
```

### 映射4: `48 动量ETF轮动-RSRS择时-卡尔曼滤波` → V5变体

```python
config = ETFRotationConfig(
    etf_pool=['510050.XSHG', '159928.XSHE', '510300.XSHG', '159949.XSHE'],
    momentum_period=20,
    momentum_method='kalman_slope',  # 卡尔曼滤波动量
    timing_method='rsrs',
    rsrs_n=18, rsrs_m=600, rsrs_threshold=0.7,
    position_mode='single',
    max_etf_num=1,
)
# 核心代码对应: get_rank() → MomentumCalculator._kalman_slope_momentum()
#              kalman_filter() → MomentumCalculator._kalman_filter()
```

### 映射5: `58 ETF动量轮动RSRS与北上择时-股债平衡-盘中止损` → V7+V13变体

```python
config = ETFRotationConfig(
    etf_pool=['510050.XSHG', '510500.XSHG', '510300.XSHG', '512100.XSHG', 
              '159949.XSHE', '163417.XSHE', '161005.XSHE'],
    momentum_period=20,
    momentum_method='bias',  # 乖离动量
    bias_period=90,
    timing_method='north_money',
    rsrs_n=18, rsrs_m=600, rsrs_threshold=0.7,
    use_bond_balance=True,
    bond_etf='511010.XSHG',
    intraday_stop_loss=True,
    intraday_ma_period=20,
    position_mode='volatility_inverse',  # 波动率倒数加权
    max_etf_num=3,  # 持有3只: ETF + 纳指 + 国债
)
# 核心代码对应: get_rank() → MomentumCalculator._bias_momentum()
#              get_north_money() → TimingSignalGenerator._north_money_signal()
#              calc_volatility() + rebalance() → PositionAllocator._volatility_inverse()
#              hold_check() → RiskManager._check_intraday_stop()
```

### 映射6: `64 ETF轮动策略升级-增加盘中止损` → V18变体 (多类别)

```python
config = ETFRotationConfig(
    etf_categories=['broad', 'sector', 'commodity', 'overseas'],  # 多类别
    momentum_period=13,
    momentum_method='simple_return',  # (now_close - previous_close) / previous_close
    timing_method='none',  # 用涨幅>0且均线状态>0作为过滤
    position_mode='single',
    max_etf_num=1,
    intraday_stop_loss=True,
    filter_paused=True,
)
# 核心代码对应: get_signal() → 涨幅>0 且 均线状态>0 的品种
#              按类别分别计算: g.df_local_stocks, g.df_global_stocks 等
```

### 映射7: `17 多品种ETF动量轮动+EPO优化` → V14变体

```python
config = ETFRotationConfig(
    etf_pool=['518880.XSHG', '159985.XSHE', '513100.XSHG', '510300.XSHG', 
              '159915.XSHE', '159992.XSHE', '515700.XSHG', '510150.XSHG',
              '515790.XSHG', '515880.XSHG', '512720.XSHG', '512660.XSHG', '159740.XSHE'],
    momentum_period=34,
    momentum_method='annualized_r2',
    timing_method='none',
    position_mode='epo',  # EPO优化
    max_etf_num=3,
    rebalance_frequency='monthly',
)
# 核心代码对应: epo() → PositionAllocator._epo_allocate()
#              run_optimization() → 使用协方差矩阵和信号向量计算最优权重
```

### 映射8: `21 行业ETF轮动+择时` → V10变体 (BBI)

```python
config = ETFRotationConfig(
    etf_categories=['sector'],
    momentum_method='bbi',
    timing_method='bbi',
    bbi_periods=[21, 34, 55, 89],  # 斐波那契数列
    bbi_unit='30m',
    position_mode='single',
    max_etf_num=1,
    rebalance_frequency='weekly',
    rebalance_weekday=3,  # 周三
    rebalance_time='11:15',
    bond_etf='511880.XSHG',
)
# 核心代码对应: BBI() → TimingSignalGenerator._bbi_signal()
#              BBI = (3MA + 6MA + 12MA + 24MA) / 4
```

### 映射9: `76 ETF-控制回撤性能拉满（国债ETF增强）` → V13变体

```python
config = ETFRotationConfig(
    etf_pool=['510300.XSHG', '510220.XSHG', '513500.XSHG', '513100.XSHG'],
    bond_etf='511010.XSHG',
    use_bond_balance=True,
    max_drawdown_level=True,
    stock_bond_ratios={0: (0.3, 0.7), 1: (0.4, 0.6), 2: (0.5, 0.5)},
    rebalance_frequency='daily',
)
# 核心代码对应: cash_management() → RiskManager._check_drawdown_level()
#              根据回撤状态动态分配股债比例
```

### 映射10: `85 稳健型ETF策略` → V19变体 (MACD条件)

```python
config = ETFRotationConfig(
    momentum_method='macd_condition',
    timing_method='macd',
    position_mode='fixed_weight',  # 固定权重: 12.5%, 12.5%, 25%, 25%, 25%
    max_etf_num=5,
    rebalance_frequency='monthly',
    rebalance_monthday=1,
)
# 核心代码对应: get_macd_M() → MACD月度指标判断正负
#              根据MACD正负和红利ETF年度涨幅决定5个持仓品种
```

---

## 五、策略扩展指南

### 5.1 添加新的动量方法

```python
# 在 MomentumCalculator 中添加新方法
def _new_momentum_method(self, etf: str, period: int) -> float:
    data = attribute_history(etf, period, '1d', ['close'])
    # 自定义动量计算逻辑
    return score
```

### 5.2 添加新的择时方法

```python
# 在 TimingSignalGenerator 中添加新方法
def _new_timing_signal(self, etf: str, date: str, **kwargs) -> str:
    # 自定义择时逻辑
    return "BUY" | "SELL" | "KEEP"
```

### 5.3 添加新的仓位分配方式

```python
# 在 PositionAllocator 中添加新方法
def _new_allocate_method(self, etfs, total_value):
    # 自定义权重计算逻辑
    return {etf: value for etf, value in weights.items()}
```

### 5.4 常见扩展方向

| 扩展方向 | 实现方式 | 参考文件 |
|---------|---------|---------|
| 加入北向资金过滤 | 扩展 TimingSignalGenerator | `38 北向资金择时` |
| 加入波动率过滤 | 扩展 FilterPipe | `26 波动率过滤` |
| 加入相关性优化 | 扩展 PositionAllocator | `28 相关系数`, `32 EPO低相关` |
| 加入趋势筛选 | 扩展 TimingSignalGenerator | `97 趋势筛选` |
| 加入盘中动态止损 | 扩展 RiskManager | `64 盘中止损`, `16 升级` |
| 多资产类别轮动 | 扩展 ETFPoolManager | `64 多类别` |
| 加入机器学习 | 替换 MomentumCalculator | `61 BiLSTM` |

### 5.5 参数优化建议

| 参数 | 推荐范围 | 说明 |
|------|---------|------|
| momentum_period | 10-34 | 短周期更灵敏但噪声大，长周期更稳定但滞后 |
| rsrs_n | 15-22 | 研报推荐18为最优 |
| rsrs_m | 400-1100 | 研报推荐600，部分策略用700-1100 |
| rsrs_threshold | 0.4-1.0 | 越低越激进，越高越保守 |
| max_etf_num | 1-3 | 1只收益最高，2-3只分散风险 |

---

## 六、完整文件索引

### 核心ETF轮动策略文件 (按变体分类)

#### V1 基础动量轮动
| 文件 | 特点 |
|------|------|
| `03 高评分ETF策略之核心资产轮动.txt` | 黄金+纳指+创业板+上证180，年化收益×R² |
| `43 窄基ETF轮动.txt` | 14只窄基ETF(白酒/创新药/新能源车等) |
| `31 ETF核心资产轮动动量因子加RSRS择时每日策略.txt` | 核心资产+RSRS+MA每日调仓 |
| `38 核心资产轮动（线性增加权重）.txt` | 核心资产轮动变体 |

#### V2 动量+RSRS择时
| 文件 | 特点 |
|------|------|
| `88 基于动量因子的ETF轮动加上RSRS择时.txt` | 经典版本：7只ETF，修正标准分，周频 |
| `17 8年13倍的ETF动量轮动策略.txt` | 优化版：单只持仓，日频，防未来函数 |
| `55 ETF轮动策略-入门1.0.txt` | 入门版：3只宽基ETF |
| `02 ETF动量轮动RSRS择时-魔改3小优化.txt` | 魔改版：去掉MA条件，仅RSRS |
| `60 ETF动量轮动RSRS择时-v2.txt` | V2版：加入RSRS均线 |
| `50 ETF动量轮动RSRS择时-V2.1.txt` | V2.1版：加入动量一阶导数风控 |
| `75 ETF轮动策略-入门2.0.txt` | 入门2.0：加入北向资金优化300ETF |

#### V3 动量+RSRS+MA双择时
| 文件 | 特点 |
|------|------|
| `38 回顾3 ETF策略之核心资产轮动-增强版.txt` | 核心资产+反转因子+RSRS beta过滤 |

#### V4 动量+钝化RSRS
| 文件 | 特点 |
|------|------|
| `24 宽基ETF动量轮动钝化RSRS择时-回撤小.txt` | 每个标的独立RSRS参数，钝化公式 |

#### V5 动量+RSRS+卡尔曼滤波
| 文件 | 特点 |
|------|------|
| `48 动量ETF轮动-RSRS择时-卡尔曼滤波.txt` | 卡尔曼滤波降噪动量 |
| `18 动量ETF轮动-RSRS择时-卡尔曼滤波.txt` | 同上(重复) |
| `16 动量ETF轮动RSRS择时-升级.txt` | 乖离动量+卡尔曼+盘中止损 |

#### V6 动量+RSRS+低通滤波
| 文件 | 特点 |
|------|------|
| `38 ETF动量轮动RSRS择时-魔改4-低通滤波.txt` | FFT低通滤波降噪动量 |

#### V7 动量+RSRS+北向资金
| 文件 | 特点 |
|------|------|
| `38 ETF动量轮动RSRS择时-魔改3-北向资金择时-再优化.txt` | 北向资金+短期动量趋势过滤 |
| `58 ETF动量轮动RSRS与北上择时-股债平衡-盘中止损.txt` | 北向+股债平衡+波动率加权 |

#### V8 乖离动量
| 文件 | 特点 |
|------|------|
| `66 ETF动量轮动MA乖离择时.txt` | MA乖离动量+MA乖离择时 |
| `10 多因子宽基ETF择时轮动改进版.txt` | 乖离动量+一阶导数+WR摆动+多时间交易 |

#### V9 动量一阶导数风控
| 文件 | 特点 |
|------|------|
| `10 多因子宽基ETF择时轮动改进版.txt` | 动量变化速度过快则空仓 |
| `50 ETF动量轮动RSRS择时-V2.1.txt` | RSRS分数斜率风控 |

#### V10 BBI多空指标轮动
| 文件 | 特点 |
|------|------|
| `57 韶华研究之五-ETF轮动躺赚夏普2.txt` | BBI+涨幅排序，多ETF池可选 |
| `21 行业ETF轮动+择时.txt` | 17只行业ETF+BBI+大盘择时 |

#### V11 涨幅+均线差值轮动
| 文件 | 特点 |
|------|------|
| `82 无需先验知识动态选择etf轮动.txt` | 成交量筛选+涨幅+均线差值 |
| `25 基本不耍六毛的ETF轮动策略.txt` | 成交量筛选+货币基金增强 |
| `30 ETF宽基轮动修改版-1.0.txt` | 涨幅+均线差值+权重分配 |

#### V12 成交量筛选轮动
| 文件 | 特点 |
|------|------|
| `82 无需先验知识动态选择etf轮动.txt` | 按成交量动态选Top ETF |
| `25 基本不耍六毛的ETF轮动策略.txt` | 月度动态筛选 |

#### V13 股债平衡+回撤控制
| 文件 | 特点 |
|------|------|
| `76 ETF-控制回撤性能拉满（国债ETF增强）.txt` | 回撤分级+MA空头排列清仓 |
| `58 ETF动量轮动RSRS与北上择时-股债平衡.txt` | 波动率倒数加权+股债配置 |

#### V14 EPO优化权重
| 文件 | 特点 |
|------|------|
| `17 多品种ETF动量轮动+EPO优化.txt` | 13只ETF+EPO优化权重 |

#### V15 核心资产+反转因子
| 文件 | 特点 |
|------|------|
| `38 回顾3 ETF策略之核心资产轮动-增强版.txt` | 短期动量 - 长期动量/6 |

#### V16 MA乖离择时
| 文件 | 特点 |
|------|------|
| `66 ETF动量轮动MA乖离择时.txt` | 60日MA乖离率做择时 |

#### V17 T+0日内动量
| 文件 | 特点 |
|------|------|
| `91 ETF-T0动量策略.txt` | 德国30ETF高开买入收盘卖出 |

#### V18 多类别轮动
| 文件 | 特点 |
|------|------|
| `64 ETF轮动策略升级-增加盘中止损.txt` | A股/海外/商品/期货分类轮动 |
| `16 ETF轮动策略升级-多类别-低回撤.txt` | 多类别版本 |

#### V19 MACD条件轮动
| 文件 | 特点 |
|------|------|
| `85 稳健型ETF策略.txt` | MACD月度正负+红利年度涨幅 |

#### 研究/辅助文件
| 文件 | 类型 |
|------|------|
| `43 研究 ETF资源收集整合.ipynb` | ETF池研究 |
| `43 轮动ETF策略中的动量因子分析.ipynb` | 动量因子分析 |
| `51 行业有效量价因子与行业轮动策略ETF.ipynb` | 行业因子研究 |
| `86 手把手教你构建ETF策略候选池.ipynb` | 候选池构建教程 |
| `86 手把手教你构建ETF策略候选池优化版.ipynb` | 候选池构建教程优化版 |
| `68 说说对ETF轮动策略的看法.txt` | 策略讨论 |
| `22 开弓ETF轮动模型——改.txt` | 开弓模型 |
| `21 以网红ETF轮动为例.txt` | 网红策略解析 |
| `81 无杠杆稳定盈利的etf轮动.txt` | 无杠杆版本 |
| `73 优化宽基etf追涨策略.txt` | 追涨优化 |
| `74 趋势筛选后相关性最小etf轮动.txt` | 趋势+相关性 |
| `97 趋势筛选后相关性最小etf轮动-加速10倍版.txt` | 加速版 |
| `26 波动率过滤后相关性最小etf轮动.txt` | 波动率+相关性 |
| `32 EPO优化低相关etf组合.txt` | EPO+低相关 |
| `28 从相关系数角度探讨etf轮动高评分.txt` | 相关系数研究 |
| `91 ETF-T0动量策略.txt` | T+0策略 |
| `61 简单ETF策略年化97%.txt` | 简单策略 |
| `61 BiLSTM for ETF.txt` | 深度学习 |
| `58 Debug-输出信息-多标的版ETF策略.txt` | Debug版本 |
| `71 股票加钱粮ETF组合.txt` | 股票+ETF组合 |
| `76 ETF基金溢价高收益低回测策略改进版.txt` | 溢价策略 |
| `93 北向Boll带_ETF组合宝付费策略.txt` | 北向+Boll带 |
| `32 北向Boll带_ETF组合宝付费策略.txt` | 同上 |
| `84 ETF网格交易策略.txt` | 网格交易 |

#### 场景适配文档
| 文件 | 内容 |
|------|------|
| `场景适配文档/02_ETF动量轮动RSRS择时策略.md` | RSRS策略适配文档 |
| `场景适配文档/04_ETF核心资产轮动策略.md` | 核心资产策略适配文档 |

### 文件统计
- **核心策略文件**: 60+ 个
- **研究/辅助文件**: 15+ 个
- **场景适配文档**: 2 个
- **总计**: 75+ 个ETF轮动相关文件
