# 综合策略通用框架设计 (CTA/可转债/基金FOF)

## 第一部分: CTA/期货策略框架

### 一、策略类型概述

CTA(Commodity Trading Advisor)期货策略主要利用期货市场的趋势性、波动性和跨期/跨品种价差进行交易。从分析的15+个策略文件中，可归纳出以下核心特征：

- **交易标的**: 股指期货(IF/IC/IH)、商品期货(RB/FG/AP/BU/LH等)、期权PCR指标
- **持仓周期**: 日内交易、波段持仓(数天至数周)、跨期套利
- **核心逻辑**: 趋势跟踪(均线突破)、波动率突破(ATR/R-breaker)、价差回归(跨期套利)、期权情绪指标(PCR)

### 二、子策略变体分类

| 子策略类型 | 代表策略 | 核心信号 | 持仓周期 |
|-----------|---------|---------|---------|
| 趋势跟踪CTA | 中证500指增+CTA, 生猪期货CTA | EMA交叉, MACD, 海龟突破 | 日线级别 |
| 日内交易CTA | 期货三价均线ATR, R-breaker, 周内日内结合CTA | 分钟均线, R-breaker价位, 量价imbalance | 日内不隔夜 |
| 波动率突破 | 低风险高收益期货策略 | ATR通道, 20日高低点突破 | 日内/波段 |
| 跨期套利 | 股指期货套利(58), 收盘折溢价(72/88) | 近远月价差, 分位数回归 | 分钟/日内 |
| 期权套利 | PCR与波动率价差套利(73) | PCR指标, 波动率相关性 | 日线级别 |
| 股票+期货对冲 | 价值投资+期货对冲V4.0(45) | 基本面选股+EMA趋势对冲 | 月度调仓 |

### 三、通用代码框架

#### 核心模块定义

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

class SignalType(Enum):
    TREND = "trend"              # 趋势跟踪(均线/MACD)
    BREAKOUT = "breakout"        # 波动率突破(ATR/海龟)
    R_BREAKER = "r_breaker"      # R-breaker日内突破
    SPREAD = "spread"            # 跨期价差套利
    PCR = "pcr"                  # 期权PCR情绪指标
    VOLUME = "volume"            # 量价信号

class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"

@dataclass
class FuturesConfig:
    """期货品种配置"""
    underlying: str = "IF"                    # 品种代码(IF/IC/IH/RB/LH等)
    benchmark: str = "000300.XSHG"            # 对标指数
    multiplier: int = 300                     # 合约乘数
    margin_rate: float = 0.15                 # 保证金比例

@dataclass
class SignalConfig:
    """信号参数配置"""
    signal_type: SignalType = SignalType.TREND
    
    # 趋势跟踪参数
    ma_short: int = 5
    ma_long: int = 20
    ema_period: int = 14
    
    # MACD参数
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # ATR突破参数
    atr_period: int = 14
    atr_multiplier_entry: float = 2.0
    atr_multiplier_stop: float = 1.5
    
    # 海龟突破参数
    donchian_short: int = 20
    donchian_long: int = 55
    
    # R-breaker参数
    r_breaker_theta: float = 0.35
    r_breaker_lambda: float = 0.07
    
    # 跨期套利参数
    spread_lookback: int = 300
    spread_entry_quantile: float = 0.9
    spread_exit_quantile: float = 0.3
    
    # PCR参数
    pcr_period: int = 20
    pcorr_threshold: float = -0.75
    pcr_buy_threshold: int = 18
    pcr_sell_threshold: int = 1

@dataclass
class RiskConfig:
    """风控参数配置"""
    stop_loss_atr: float = 2.0                # ATR止损倍数
    stop_loss_pct: float = 0.03               # 百分比止损
    take_profit_pct: float = 0.03             # 百分比止盈
    max_position_pct: float = 0.30            # 最大仓位比例
    max_contracts: int = 50                   # 最大持仓手数
    holiday_deleverage: bool = True           # 长假前空仓
    delivery_close: bool = True               # 交割日前平仓

@dataclass
class CTAStrategyConfig:
    """CTA策略总配置"""
    futures: List[FuturesConfig] = field(default_factory=list)
    signal: SignalConfig = field(default_factory=SignalConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    
    # 仓位管理
    position_method: str = "fixed_fraction"   # fixed_fraction/volatility_target/kelly
    target_volatility: float = 0.15           # 目标年化波动率
    volatility_lookback: int = 20             # 波动率计算窗口
    
    # 资金管理
    stock_share: float = 0.70                 # 股票子账户比例(对冲策略)
    future_share: float = 0.30                # 期货子账户比例
    future_margin_pct: float = 0.35           # 期货保证金占用比例
    
    # 调仓
    rebalance_frequency: str = "daily"        # daily/weekly/monthly
    trading_time: str = "11:15"               # 交易执行时间
```

#### 框架主类

```python
class CTAStrategy:
    """CTA期货策略通用框架"""
    
    def __init__(self, config: CTAStrategyConfig):
        self.config = config
        self.positions = {}           # 当前持仓
        self.signals_history = []     # 信号历史
        self.pnl_history = []         # 盈亏历史
        
    def initialize(self, context):
        """初始化: 设置账户、手续费、定时任务"""
        # 1. 设置子账户(对冲策略需要)
        if self.config.stock_share + self.config.future_share > 0:
            set_subportfolios([
                SubPortfolioConfig(cash=context.portfolio.starting_cash * self.config.stock_share, type='stock'),
                SubPortfolioConfig(cash=context.portfolio.starting_cash * self.config.future_share, type='futures')
            ])
        
        # 2. 设置期货手续费和保证金
        for fc in self.config.futures:
            set_order_cost(OrderCost(
                open_commission=0.000023, 
                close_commission=0.000023,
                close_today_commission=0.0023
            ), type='index_futures')
            set_option('futures_margin_rate', fc.margin_rate)
        
        # 3. 设置定时任务
        run_daily(self.before_market_open, time='09:00', reference_security='IF8888.CCFX')
        run_daily(self.market_trade, time=self.config.trading_time, reference_security='IF8888.CCFX')
        run_daily(self.after_market_close, time='15:30', reference_security='IF8888.CCFX')
    
    def before_market_open(self, context):
        """盘前准备: 获取主力合约、计算指标"""
        for fc in self.config.futures:
            # 获取主力合约
            main_contract = get_dominant_future(fc.underlying)
            fc.main_contract = main_contract
            
            # 检查是否交割日
            if self.config.risk.delivery_close:
                end_date = get_security_info(main_contract).end_date
                fc.is_delivery = (context.current_dt.date() == end_date)
            
            # 计算技术指标
            self._calculate_indicators(context, fc)
    
    def _calculate_indicators(self, context, fc: FuturesConfig):
        """计算技术指标"""
        sig = self.config.signal
        contract = fc.main_contract
        
        if sig.signal_type == SignalType.TREND:
            # EMA交叉信号
            close = attribute_history(contract, sig.ma_long + 5, '1d', 'close')['close']
            fc.ema_short = self._ema(close, sig.ma_short)
            fc.ema_long = self._ema(close, sig.ma_long)
            fc.current_price = close[-1]
            
        elif sig.signal_type == SignalType.BREAKOUT:
            # ATR + 海龟突破
            data = attribute_history(contract, max(sig.donchian_long, sig.atr_period) + 5, '1d', ['high', 'low', 'close'])
            fc.atr = self._atr(data['high'], data['low'], data['close'], sig.atr_period)
            fc.high_20 = data['high'][-sig.donchian_short:-1].max()
            fc.low_20 = data['low'][-sig.donchian_short:-1].min()
            fc.current_price = data['close'][-1]
            
        elif sig.signal_type == SignalType.R_BREAKER:
            # R-breaker价位计算
            prev = attribute_history(contract, 1, '1d', ['high', 'low', 'close'])
            fc.r3 = prev['high'][-1] + sig.r_breaker_theta * (prev['close'][-1] - prev['low'][-1])
            fc.r2 = prev['high'][-1] + sig.r_breaker_theta * (prev['close'][-1] - prev['low'][-1])
            fc.r1 = (1 + sig.r_breaker_lambda) / 2 * (prev['high'][-1] + prev['low'][-1]) - sig.r_breaker_lambda * prev['low'][-1]
            fc.s1 = (1 + sig.r_breaker_lambda) / 2 * (prev['high'][-1] + prev['low'][-1]) - sig.r_breaker_lambda * prev['high'][-1]
            fc.s2 = prev['low'][-1] - sig.r_breaker_theta * (prev['high'][-1] - prev['close'][-1])
            fc.s3 = prev['low'][-1] - sig.r_breaker_theta * (prev['high'][-1] - prev['close'][-1])
            
        elif sig.signal_type == SignalType.SPREAD:
            # 跨期价差
            data1 = attribute_history(contract, sig.spread_lookback, '1m', 'close')['close']
            # 获取远月合约...
            fc.spread = data1  # 价差序列
            fc.spread_mean = data1.mean()
            fc.spread_std = data1.std()
    
    def generate_signal(self, context, fc: FuturesConfig) -> PositionSide:
        """生成交易信号"""
        sig = self.config.signal
        
        if sig.signal_type == SignalType.TREND:
            # EMA交叉: 价格上穿短EMA且短EMA>长EMA -> 多
            if fc.current_price > fc.ema_short[-1] and fc.ema_short[-1] > fc.ema_long[-1]:
                return PositionSide.LONG
            elif fc.current_price < fc.ema_short[-1] and fc.ema_short[-1] < fc.ema_long[-1]:
                return PositionSide.SHORT
            return PositionSide.FLAT
            
        elif sig.signal_type == SignalType.BREAKOUT:
            # 海龟突破 + ATR过滤
            if fc.current_price >= fc.high_20:
                return PositionSide.LONG
            elif fc.current_price <= fc.low_20:
                return PositionSide.SHORT
            return PositionSide.FLAT
            
        elif sig.signal_type == SignalType.R_BREAKER:
            # R-breaker突破逻辑(需tick级别)
            pass
            
        elif sig.signal_type == SignalType.SPREAD:
            # 价差回归
            current_spread = fc.spread[-1]
            upper = fc.spread_mean + sig.spread_entry_quantile * fc.spread_std
            lower = fc.spread_mean - sig.spread_entry_quantile * fc.spread_std
            if current_spread > upper:
                return PositionSide.SHORT  # 价差过高, 卖近买远
            elif current_spread < lower:
                return PositionSide.LONG   # 价差过低, 买近卖远
            return PositionSide.FLAT
        
        return PositionSide.FLAT
    
    def calculate_position(self, context, fc: FuturesConfig) -> int:
        """计算开仓手数"""
        method = self.config.position_method
        total_value = context.portfolio.total_value
        
        if method == "fixed_fraction":
            # 固定比例: 总资金的固定比例 / (合约价值 * 保证金率)
            contract_value = fc.current_price * fc.multiplier
            max_contracts = int(total_value * self.config.risk.max_position_pct / contract_value)
            return min(max_contracts, self.config.risk.max_contracts)
            
        elif method == "volatility_target":
            # 波动率目标: 根据ATR调整仓位
            atr_value = fc.atr[-1] if hasattr(fc, 'atr') else fc.current_price * 0.02
            risk_per_contract = atr_value * fc.multiplier * self.config.signal.atr_multiplier_stop
            target_risk = total_value * self.config.target_volatility / 252 ** 0.5
            contracts = int(target_risk / risk_per_contract)
            return min(contracts, self.config.risk.max_contracts)
        
        return 1
    
    def check_stop_loss(self, context, fc: FuturesConfig) -> bool:
        """检查止损条件"""
        risk = self.config.risk
        contract = fc.main_contract
        
        if contract not in context.portfolio.positions:
            return False
        
        pos = context.portfolio.positions[contract]
        cost = pos.avg_cost
        current = fc.current_price
        
        # ATR止损
        if hasattr(fc, 'atr'):
            atr_stop = fc.atr[-1] * risk.stop_loss_atr
            if pos.side == 'long' and current < cost - atr_stop:
                return True
            elif pos.side == 'short' and current > cost + atr_stop:
                return True
        
        # 百分比止损
        if pos.side == 'long' and (current - cost) / cost < -risk.stop_loss_pct:
            return True
        elif pos.side == 'short' and (cost - current) / cost < -risk.stop_loss_pct:
            return True
        
        return False
    
    def market_trade(self, context):
        """盘中交易执行"""
        for fc in self.config.futures:
            contract = fc.main_contract
            
            # 1. 检查交割日平仓
            if getattr(fc, 'is_delivery', False):
                self._close_all_positions(context, contract)
                continue
            
            # 2. 检查长假前空仓
            if self.config.risk.holiday_deleverage and self._is_holiday_eve(context):
                self._close_all_positions(context, contract)
                continue
            
            # 3. 检查止损
            if self.check_stop_loss(context, fc):
                self._close_all_positions(context, contract)
                continue
            
            # 4. 生成信号
            signal = self.generate_signal(context, fc)
            
            # 5. 执行交易
            current_pos = len(context.portfolio.positions.get(contract, []))
            
            if signal == PositionSide.LONG and current_pos == 0:
                contracts = self.calculate_position(context, fc)
                order(contract, contracts, side='long')
            elif signal == PositionSide.SHORT and current_pos == 0:
                contracts = self.calculate_position(context, fc)
                order(contract, contracts, side='short')
            elif signal == PositionSide.FLAT and current_pos > 0:
                self._close_all_positions(context, contract)
    
    def _close_all_positions(self, context, contract):
        """平仓"""
        if contract in context.portfolio.positions:
            order_target(contract, 0)
        if contract in context.portfolio.short_positions:
            order_target(contract, 0, side='short')
    
    def _is_holiday_eve(self, context):
        """判断是否长假前夕"""
        today = context.current_dt.date()
        # 简化实现: 检查未来3个交易日是否有超过3天的间隔
        trade_days = list(get_all_trade_days())
        idx = trade_days.index(today)
        if idx + 1 < len(trade_days):
            next_day = trade_days[idx + 1]
            return (next_day - today).days > 3
        return False
    
    def after_market_close(self, context):
        """盘后处理"""
        # 记录持仓和盈亏
        for fc in self.config.futures:
            contract = fc.main_contract
            if contract in context.portfolio.positions:
                pos = context.portfolio.positions[contract]
                self.pnl_history.append({
                    'date': context.current_dt.date(),
                    'contract': contract,
                    'side': 'long',
                    'pnl': (pos.price - pos.avg_cost) * pos.total_amount * fc.multiplier
                })
    
    @staticmethod
    def _ema(series, period):
        """计算EMA"""
        import numpy as np
        ema = np.zeros_like(series, dtype=float)
        multiplier = 2 / (period + 1)
        ema[0] = series[0]
        for i in range(1, len(series)):
            ema[i] = (series[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    @staticmethod
    def _atr(high, low, close, period):
        """计算ATR"""
        import numpy as np
        tr = np.maximum(high[1:] - low[1:], 
                       np.maximum(np.abs(high[1:] - close[:-1]), 
                                 np.abs(low[1:] - close[:-1])))
        atr = np.zeros_like(tr)
        atr[0] = np.mean(tr[:period])
        for i in range(1, len(tr)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        return atr
```

### 四、典型策略映射示例

#### 1. 中证500指增+CTA (27)

```python
# 映射配置
config = CTAStrategyConfig(
    futures=[FuturesConfig(underlying="IC", multiplier=200, margin_rate=0.15)],
    signal=SignalConfig(
        signal_type=SignalType.TREND,
        ma_short=2, ma_long=6,
    ),
    risk=RiskConfig(
        stop_loss_atr=5,
        max_position_pct=0.30,
    ),
    stock_share=0.70, future_share=0.30, future_margin_pct=0.35,
    position_method="volatility_target",
    volatility_lookback=20,
)
# 波动率调整: 短ATR(20)-长ATR(50) < 0 -> 1.5倍仓位; > 0 -> 1.0倍
# ATR止损: 5日最高/最低 ± 5*ATR
```

#### 2. 生猪期货CTA (63)

```python
config = CTAStrategyConfig(
    futures=[FuturesConfig(underlying="LH", benchmark="LH8888.XDCE", margin_rate=0.14)],
    signal=SignalConfig(
        signal_type=SignalType.TREND,
        macd_fast=12, macd_slow=26, macd_signal=9,
    ),
    risk=RiskConfig(
        stop_loss_pct=0.03,
        take_profit_pct=0.03,
        max_contracts=100,
    ),
    position_method="fixed_fraction",
    trading_time="every_bar",  # tick级别
)
# MACD>0 + 价格突破开仓阈值 + 相关品种(牧原股份)趋势一致 -> 开多
# 基于5日振幅计算开仓阈值
```

#### 3. 期货三价均线+ATR (71)

```python
config = CTAStrategyConfig(
    futures=[FuturesConfig(underlying="IF", margin_rate=0.15)],
    signal=SignalConfig(
        signal_type=SignalType.BREAKOUT,
        ma_short=5, ma_long=20,
        atr_period=14, atr_multiplier_entry=3.0,
    ),
    risk=RiskConfig(
        max_position_pct=1.0,  # 全仓
    ),
    position_method="fixed_fraction",
    trading_time="every_bar",  # 分钟级别
)
# 三价均线(高+低+收)/3, 短MA上穿长MA + 趋势确认 -> 开仓
# 不隔夜, 14:59平仓
```

#### 4. R-breaker日内交易 (76)

```python
config = CTAStrategyConfig(
    futures=[FuturesConfig(underlying="IF")],
    signal=SignalConfig(
        signal_type=SignalType.R_BREAKER,
        r_breaker_theta=0.35,
        r_breaker_lambda=0.07,
    ),
    risk=RiskConfig(
        max_position_pct=0.10,
    ),
    position_method="fixed_fraction",
    trading_time="tick",  # 必须tick级别
)
# R3/R2/R1/S1/S2/S3六档价位, 突破R3做多, 跌破S3做空
# R2回落至R1平仓, S2反弹至S1平仓
```

#### 5. 期权PCR股指期货套利 (73)

```python
config = CTAStrategyConfig(
    futures=[FuturesConfig(underlying="IH", multiplier=300, margin_rate=0.15)],
    signal=SignalConfig(
        signal_type=SignalType.PCR,
        pcr_period=20,
        pcorr_threshold=-0.75,
        pcr_buy_threshold=18,
        pcr_sell_threshold=1,
    ),
    risk=RiskConfig(
        stop_loss_pct=0.05,  # 20000元止损
        take_profit_pct=0.25,  # 100000元止盈
        max_contracts=50,
    ),
    position_method="fixed_fraction",
)
# PCR(成交额/成交量)与ETF收益率相关性 < -0.75 时有效
# PCR排名>18 -> 多头, <1 -> 空头
```

#### 6. 股指期货跨期套利 (58)

```python
config = CTAStrategyConfig(
    futures=[
        FuturesConfig(underlying="IF", margin_rate=0.10),
    ],
    signal=SignalConfig(
        signal_type=SignalType.SPREAD,
        spread_lookback=300,
        spread_entry_quantile=0.9,
        spread_exit_quantile=0.3,
    ),
    risk=RiskConfig(
        max_position_pct=0.80,  # 预留20%现金
    ),
    position_method="fixed_fraction",
    trading_time="every_bar",  # 分钟级别
)
# 近月-远月价差, 价差>90%分位数*1.1 -> 卖近买远
# 价差<30%分位数 -> 平仓
```

---

## 第二部分: 可转债策略框架

### 一、策略类型概述

可转债策略利用可转债"下有保底(债底), 上不封顶(转股)"的特性进行投资。核心策略为**双低轮动**, 即选择转债价格低+转股溢价率低的可转债进行等权轮动。

### 二、子策略变体分类

| 子策略类型 | 代表策略 | 核心逻辑 | 调仓频率 |
|-----------|---------|---------|---------|
| 双低轮动 | 可转债双低策略(86), 双低轮动2.0(95) | 转债价格+溢价率排序, 取前N只 | 日/周 |
| 价格筛选 | 白马可转债 | 低价转债+正股基本面 | 周/月 |
| 条款博弈 | - | 下修条款、强赎条款博弈 | 事件驱动 |

### 三、通用代码框架

#### 核心模块定义

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class BondScreenConfig:
    """可转债筛选配置"""
    max_bond_price: float = 130.0           # 最高转债价格
    max_premium_ratio: float = 0.30         # 最高转股溢价率(30%)
    min_bond_price: float = 10.0            # 最低转债价格(排除异常)
    min_remaining_size: float = 0.5         # 最小剩余规模(亿元)
    exclude_delisted: bool = True           # 排除已退市
    exclude_matured: bool = True            # 排除已到期
    
    # 双低计算
    double_low_formula: str = "price + premium_rate * 100"  # price + premium*100

@dataclass
class BondPositionConfig:
    """仓位配置"""
    bond_num: int = 10                      # 持仓转债数量
    position_method: str = "equal"          # equal/double_low_weight
    max_single_pct: float = 0.15            # 单只最大仓位
    cash_reserve: float = 0.0               # 现金保留比例

@dataclass
class BondRebalanceConfig:
    """调仓配置"""
    frequency: str = "daily"                # daily/weekly/monthly
    trading_time: str = "open"              # open/10:00/14:00
    sell_not_in_buy: bool = True            # 卖出不在新名单的
    min_holding_days: int = 0               # 最小持有天数

@dataclass
class ConvertibleBondConfig:
    """可转债策略总配置"""
    screen: BondScreenConfig = field(default_factory=BondScreenConfig)
    position: BondPositionConfig = field(default_factory=BondPositionConfig)
    rebalance: BondRebalanceConfig = field(default_factory=BondRebalanceConfig)
    
    # 资金
    initial_capital: float = 100000
    commission_rate: float = 0.0003         # 佣金(万3)
```

#### 框架主类

```python
class ConvertibleBondStrategy:
    """可转债策略通用框架"""
    
    def __init__(self, config: ConvertibleBondConfig):
        self.config = config
        self.holdings = {}                  # 持仓 {code: {qty, cost_price}}
        self.trade_log = []                 # 交易记录
    
    def initialize(self, context):
        """初始化"""
        set_benchmark('000300.XSHG')
        set_option('use_real_price', True)
        set_order_cost(OrderCost(
            open_tax=0, close_tax=0,
            open_commission=self.config.commission_rate,
            close_commission=self.config.commission_rate,
            min_commission=5
        ), type='stock')
        
        # 定时调仓
        freq = self.config.rebalance.frequency
        if freq == 'daily':
            run_daily(self.rebalance, time=self.config.rebalance.trading_time)
        elif freq == 'weekly':
            run_weekly(self.rebalance, weekday=1, time=self.config.rebalance.trading_time)
        elif freq == 'monthly':
            run_monthly(self.rebalance, monthday=1, time=self.config.rebalance.trading_time)
    
    def screen_bonds(self, context) -> List[Dict]:
        """筛选可转债"""
        sc = self.config.screen
        
        # 1. 获取所有可转债
        bond_df = bond.run_query(query(
            bond.BOND_BASIC_INFO
        ).filter(
            bond.BOND_BASIC_INFO.bond_type_id == '703013'
        ))
        
        # 2. 过滤已到期/退市
        if sc.exclude_matured:
            bond_df = bond_df[bond_df.maturity_date > context.current_dt.date()]
        
        # 3. 获取每只转债的详细信息
        bond_list = []
        for _, row in bond_df.iterrows():
            code = row.code
            info = self._get_bond_detail(code, context)
            if info is None:
                continue
            
            # 4. 价格筛选
            if info['bond_price'] > sc.max_bond_price:
                continue
            if info['bond_price'] < sc.min_bond_price:
                continue
            
            # 5. 溢价率筛选
            if info['premium_ratio'] > sc.max_premium_ratio:
                continue
            
            bond_list.append(info)
        
        # 6. 计算双低值并排序
        for bond in bond_list:
            bond['double_low'] = bond['bond_price'] + bond['premium_ratio'] * 100
        
        bond_list.sort(key=lambda x: x['double_low'])
        
        return bond_list
    
    def _get_bond_detail(self, code, context) -> Optional[Dict]:
        """获取单只转债详细信息"""
        try:
            # 获取转债基本信息
            conv_df = bond.run_query(query(
                bond.CONBOND_BASIC_INFO
            ).filter(
                bond.CONBOND_BASIC_INFO.code == code
            ))
            
            if len(conv_df) == 0:
                return None
            
            # 获取转债价格
            price_df = bond.run_query(query(
                bond.CONBOND_DAILY_PRICE
            ).filter(
                bond.CONBOND_DAILY_PRICE.code == code,
                bond.CONBOND_DAILY_PRICE.date <= context.previous_date
            ).limit(1))
            
            if len(price_df) == 0:
                return None
            
            bond_price = price_df.iloc[0]['close']
            
            # 获取转股价格和正股价格
            conv_price_df = bond.run_query(query(
                bond.CONBOND_DAILY_CONVERT
            ).filter(
                bond.CONBOND_DAILY_CONVERT.code == code
            ).limit(1))
            
            strike_price = conv_price_df.iloc[0]['convert_price']
            stock_code = self._get_underlying_stock(code)
            stock_price = get_price(stock_code, count=1, end_date=context.previous_date)['close'][0]
            
            # 计算转股价值和溢价率
            inner_value = 100 / strike_price * stock_price
            premium_ratio = (bond_price - inner_value) / inner_value
            
            return {
                'code': code,
                'bond_price': bond_price,
                'stock_price': stock_price,
                'strike_price': strike_price,
                'inner_value': inner_value,
                'premium_ratio': premium_ratio,
            }
        except:
            return None
    
    def _get_underlying_stock(self, bond_code) -> str:
        """获取转债对应正股代码"""
        df = bond.run_query(query(
            bond.BOND_BASIC_INFO
        ).filter(
            bond.BOND_BASIC_INFO.code == bond_code
        ))
        return df.iloc[0]['company_code']
    
    def calculate_weights(self, bond_list: List[Dict]) -> Dict[str, float]:
        """计算配置权重"""
        method = self.config.position.position_method
        n = self.config.position.bond_num
        
        target_bonds = bond_list[:n]
        
        if method == "equal":
            # 等权配置
            weight = 1.0 / len(target_bonds) if target_bonds else 0
            return {b['code']: weight for b in target_bonds}
        
        elif method == "double_low_weight":
            # 双低值越低权重越高(反比)
            total_inv = sum(1.0 / b['double_low'] for b in target_bonds)
            return {b['code']: (1.0 / b['double_low']) / total_inv for b in target_bonds}
        
        return {}
    
    def rebalance(self, context):
        """调仓执行"""
        # 1. 筛选转债
        bond_list = self.screen_bonds(context)
        
        # 2. 计算目标权重
        target_weights = self.calculate_weights(bond_list)
        target_codes = set(target_weights.keys())
        current_codes = set(context.portfolio.positions.keys())
        
        # 3. 卖出不在目标列表的
        if self.config.rebalance.sell_not_in_buy:
            for code in current_codes - target_codes:
                order_target(code, 0)
        
        # 4. 买入/调整目标
        total_value = context.portfolio.total_value
        for code, weight in target_weights.items():
            target_value = total_value * weight
            current_value = context.portfolio.positions.get(code, None)
            current_value = current_value.value if current_value else 0
            
            if abs(target_value - current_value) > 1000:  # 最小调仓金额
                order_target_value(code, target_value)
    
    def backtest(self, start_date, end_date, capital=100000):
        """回测引擎(离线模式)"""
        import pandas as pd
        
        dates = pd.date_range(start_date, end_date, freq='B')
        portfolio_value = [capital]
        holdings = {}
        cash = capital
        
        for date in dates:
            # 筛选
            bond_list = self._screen_bonds_offline(date)
            target_codes = set(b['code'] for b in bond_list[:self.config.position.bond_num])
            
            # 卖出
            for code in list(holdings.keys()):
                if code not in target_codes:
                    price = self._get_price(code, date)
                    if price:
                        cash += holdings[code]['qty'] * price
                    del holdings[code]
            
            # 买入
            buy_num = self.config.position.bond_num - len(holdings)
            if buy_num > 0:
                per_bond_cash = cash / buy_num
                for bond in bond_list[:self.config.position.bond_num]:
                    if bond['code'] not in holdings:
                        price = bond['bond_price']
                        qty = int(per_bond_cash / price / 10) * 10
                        if qty > 0:
                            holdings[bond['code']] = {'qty': qty, 'cost': price}
                            cash -= qty * price
            
            # 更新市值
            total = cash
            for code, pos in holdings.items():
                price = self._get_price(code, date)
                if price:
                    total += pos['qty'] * price
            
            portfolio_value.append(total)
        
        return pd.Series(portfolio_value, index=dates)
```

### 四、典型策略映射示例

#### 1. 可转债双低策略 (86)

```python
config = ConvertibleBondConfig(
    screen=BondScreenConfig(
        max_bond_price=150,
        max_premium_ratio=0.50,
        min_bond_price=10,
    ),
    position=BondPositionConfig(
        bond_num=10,
        position_method="equal",
    ),
    rebalance=BondRebalanceConfig(
        frequency="weekly",
        trading_time="open",
    ),
)
# 双低 = 转债价格 + (转债价格-转股价值)/转股价值*100
# 按双低值升序排序, 取前10只等权买入
# 每周调仓, 卖出不在新名单的, 买入新入选的
```

#### 2. 可转债双低轮动回测2.0 (95)

```python
config = ConvertibleBondConfig(
    screen=BondScreenConfig(
        max_bond_price=200,
        max_premium_ratio=1.0,
        min_bond_price=10,
    ),
    position=BondPositionConfig(
        bond_num=10,
        position_method="equal",
    ),
    rebalance=BondRebalanceConfig(
        frequency="daily",
        trading_time="open",
    ),
    initial_capital=100000,
)
# double_order = close + 100 * convert_premium_rate
# 每日按前一日双低排序取前10, 按开盘价买卖
# 回测2018-09-12至2021-07-31, 年化101%
```

#### 3. 白马可转债策略 (概念)

```python
config = ConvertibleBondConfig(
    screen=BondScreenConfig(
        max_bond_price=120,
        max_premium_ratio=0.20,
        min_remaining_size=3.0,  # 剩余规模>3亿
    ),
    position=BondPositionConfig(
        bond_num=15,
        position_method="equal",
    ),
    rebalance=BondRebalanceConfig(
        frequency="weekly",
        trading_time="10:00",
    ),
)
# 选择价格低+溢价率低+剩余规模大的"白马"转债
# 正股需满足一定基本面条件(ROE>0, 营收增长>0)
```

---

## 第三部分: 基金/FOF策略框架

### 一、策略类型概述

基金/FOF策略通过配置不同类型的ETF/LOF/场外基金实现资产配置。核心逻辑包括**动量轮动**、**风险平价**、**相关性最小化**和**基金跟随**。

### 二、子策略变体分类

| 子策略类型 | 代表策略 | 核心逻辑 | 调仓频率 |
|-----------|---------|---------|---------|
| 动量轮动 | 波动率过滤相关性最小(26), 趋势筛选相关性最小(74) | 动量评分+相关性过滤 | 日/周 |
| 风险平价 | FoF all in(94), FOF养老成长(14) | 波动率倒数加权 | 月 |
| 固定配置 | iAlpha基金投资(06/09) | 固定比例再平衡 | 月 |
| 定投增强 | 场内基金定投价值平均(69) | 价值平均策略+止盈 | 月 |
| 溢价套利 | 基金溢价(62), 折价基金套利(68) | 折溢价率交易 | 日 |
| 基金跟随 | 基金跟随策略(17) | 跟随基金重仓股 | 季 |
| 情绪监控 | 无杠杆ETF轮动(81), 动态选择ETF(82) | 成交量监控+动量 | 日 |

### 三、通用代码框架

#### 核心模块定义

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

class AllocationMethod(Enum):
    EQUAL = "equal"                     # 等权配置
    MOMENTUM = "momentum"               # 动量轮动
    VOLATILITY_PARITY = "volatility_parity"  # 波动率平价
    RISK_PARITY = "risk_parity"         # 风险平价
    MIN_CORRELATION = "min_correlation" # 最小相关性
    FIXED = "fixed"                     # 固定权重

@dataclass
class FundPoolConfig:
    """基金池配置"""
    funds: List[str] = field(default_factory=list)       # 指定基金列表
    categories: List[str] = field(default_factory=list)  # 基金类别(etf/lof/fund)
    
    # 筛选条件
    min_list_days: int = 365              # 最小上市天数
    min_avg_money: float = 1e7            # 最小日均成交额(1000万)
    min_aum: float = 1e8                  # 最小规模(1亿)
    max_volatility: float = 0.35          # 最大年化波动率
    min_volatility: float = 0.05          # 最小年化波动率

@dataclass
class AllocationConfig:
    """配置方法参数"""
    method: AllocationMethod = AllocationMethod.MOMENTUM
    
    # 动量参数
    momentum_period: int = 25             # 动量计算周期
    momentum_score_min: float = -0.5      # 最低动量得分
    momentum_score_max: float = 4.5       # 最高动量得分
    
    # 波动率参数
    volatility_period: int = 243          # 波动率计算周期(1年)
    
    # 相关性参数
    correlation_period: int = 729         # 相关性计算周期(3年)
    min_corr_select_num: int = 4          # 最小相关性筛选数量
    
    # 风险平价参数
    risk_free_rate: float = 0.03          # 无风险利率
    confidence_level: float = 0.02        # 置信水平(VaR/ES)
    reference_cycle: int = 250            # 参考周期
    
    # 固定权重
    fixed_weights: Dict[str, float] = field(default_factory=dict)

@dataclass
class RebalanceConfig:
    """调仓配置"""
    frequency: str = "weekly"             # daily/weekly/monthly
    threshold: float = 0.05               # 偏离阈值(超过则调仓)
    max_turnover: float = 0.30            # 最大换手率
    trading_time: str = "10:00"
    
    # 风控
    empty_keep_stock: str = "511880.XSHG" # 空仓时持有的货币基金
    volume_monitor: bool = False          # 是否监控成交量
    volume_lag: int = 6                   # 连续跌破均线天数
    volume_ma_period: int = 7             # 成交量均线周期

@dataclass
class FundFOFConfig:
    """基金FOF策略总配置"""
    pool: FundPoolConfig = field(default_factory=FundPoolConfig)
    allocation: AllocationConfig = field(default_factory=AllocationConfig)
    rebalance: RebalanceConfig = field(default_factory=RebalanceConfig)
    
    # 资金
    initial_capital: float = 100000
    target_num: int = 1                   # 目标持仓数量(动量轮动)
    commission_rate: float = 0.0003       # 佣金
```

#### 框架主类

```python
class FundFOFStrategy:
    """基金FOF策略通用框架"""
    
    def __init__(self, config: FundFOFConfig):
        self.config = config
        self.holdings = {}
        self.nav_history = {}
    
    def initialize(self, context):
        """初始化"""
        set_benchmark('000300.XSHG')
        set_option('use_real_price', True)
        set_order_cost(OrderCost(
            open_tax=0, close_tax=0,
            open_commission=self.config.commission_rate,
            close_commission=self.config.commission_rate,
            min_commission=5
        ), type='fund')
        
        # 定时调仓
        freq = self.config.rebalance.frequency
        if freq == 'daily':
            run_daily(self.rebalance, time=self.config.rebalance.trading_time)
        elif freq == 'weekly':
            run_weekly(self.rebalance, weekday=1, time=self.config.rebalance.trading_time)
        elif freq == 'monthly':
            run_monthly(self.rebalance, monthday=1, time=self.config.rebalance.trading_time)
    
    def get_fund_pool(self, context) -> List[str]:
        """获取基金池"""
        pc = self.config.pool
        
        if pc.funds:
            # 使用指定列表
            return pc.funds
        
        # 动态获取
        if pc.categories:
            all_funds = get_all_securities(pc.categories, context.previous_date)
        else:
            all_funds = get_all_securities(['etf'], context.previous_date)
        
        fund_list = all_funds.index.tolist()
        
        # 过滤上市时间
        if pc.min_list_days > 0:
            cutoff = context.current_dt.date() - timedelta(days=pc.min_list_days)
            fund_list = [f for f in fund_list 
                        if get_security_info(f).start_date < cutoff]
        
        # 过滤成交额
        if pc.min_avg_money > 0:
            money = history(pc.min_list_days, '1d', 'money', fund_list)
            avg_money = money.mean()
            fund_list = [f for f in fund_list 
                        if avg_money.get(f, 0) > pc.min_avg_money]
        
        # 过滤波动率
        if pc.max_volatility > 0 or pc.min_volatility > 0:
            closes = history(pc.volatility_period, '1d', 'close', fund_list)
            returns = np.log(closes).diff().dropna()
            vol = returns.std() * np.sqrt(243)
            
            if pc.max_volatility > 0:
                fund_list = [f for f in fund_list 
                            if vol.get(f, 999) < pc.max_volatility]
            if pc.min_volatility > 0:
                fund_list = [f for f in fund_list 
                            if vol.get(f, 0) > pc.min_volatility]
        
        return fund_list
    
    def calculate_allocation(self, context, fund_list: List[str]) -> Dict[str, float]:
        """计算配置权重"""
        method = self.config.allocation.method
        
        if method == AllocationMethod.EQUAL:
            return self._equal_weight(fund_list)
        
        elif method == AllocationMethod.MOMENTUM:
            return self._momentum_weight(context, fund_list)
        
        elif method == AllocationMethod.VOLATILITY_PARITY:
            return self._volatility_parity(context, fund_list)
        
        elif method == AllocationMethod.MIN_CORRELATION:
            return self._min_correlation(context, fund_list)
        
        elif method == AllocationMethod.FIXED:
            return self.config.allocation.fixed_weights
        
        return {}
    
    def _equal_weight(self, fund_list: List[str]) -> Dict[str, float]:
        """等权配置"""
        if not fund_list:
            return {}
        w = 1.0 / len(fund_list)
        return {f: w for f in fund_list}
    
    def _momentum_weight(self, context, fund_list: List[str]) -> Dict[str, float]:
        """动量评分配置"""
        ac = self.config.allocation
        scores = {}
        
        for fund in fund_list:
            closes = attribute_history(fund, ac.momentum_period, '1d', ['close'])
            if len(closes) < ac.momentum_period:
                continue
            
            # 线性回归斜率
            y = np.log(closes['close'].values)
            x = np.arange(len(y))
            slope, intercept = np.polyfit(x, y, 1)
            
            # 年化收益率
            annualized_return = np.exp(slope * 250) - 1
            
            # R平方
            y_pred = slope * x + intercept
            r_squared = 1 - np.sum((y - y_pred)**2) / ((len(y) - 1) * np.var(y, ddof=1))
            
            # 得分 = 年化收益 * R平方
            score = annualized_return * r_squared
            
            # 过滤得分范围
            if ac.momentum_score_min < score < ac.momentum_score_max:
                scores[fund] = score
        
        if not scores:
            return {}
        
        # 按得分降序
        sorted_funds = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        target_num = self.config.target_num
        target_funds = [f[0] for f in sorted_funds[:target_num]]
        
        return {f: 1.0/len(target_funds) for f in target_funds}
    
    def _volatility_parity(self, context, fund_list: List[str]) -> Dict[str, float]:
        """波动率平价配置"""
        ac = self.config.allocation
        closes = history(ac.volatility_period, '1d', 'close', fund_list)
        returns = np.log(closes).diff().dropna()
        vol = returns.std() * np.sqrt(243)
        
        # 权重与波动率成反比
        inv_vol = {f: 1.0 / vol[f] for f in fund_list if vol[f] > 0}
        total = sum(inv_vol.values())
        
        return {f: w / total for f, w in inv_vol.items()}
    
    def _min_correlation(self, context, fund_list: List[str]) -> Dict[str, float]:
        """最小相关性配置"""
        ac = self.config.allocation
        
        # 计算相关性矩阵
        closes = history(ac.correlation_period, '1d', 'close', fund_list).dropna(axis=1)
        returns = np.log(closes).diff().dropna()
        corr_matrix = returns.corr()
        
        # 计算每只基金的平均绝对相关性
        avg_corr = {}
        for fund in corr_matrix.columns:
            avg_corr[fund] = corr_matrix[fund].abs().mean()
        
        # 选择相关性最小的N只
        select_num = ac.min_corr_select_num
        selected = sorted(avg_corr.items(), key=lambda x: x[1])[:select_num]
        selected_funds = [f[0] for f in selected]
        
        # 对选中的基金再进行动量排序
        return self._momentum_weight(context, selected_funds)
    
    def check_rebalance_needed(self, context, target_weights: Dict[str, float]) -> bool:
        """检查是否需要调仓"""
        threshold = self.config.rebalance.threshold
        
        for fund, target_w in target_weights.items():
            if fund in context.portfolio.positions:
                current_w = context.portfolio.positions[fund].value / context.portfolio.total_value
                if abs(current_w - target_w) > threshold:
                    return True
            elif target_w > 0:
                return True
        
        return False
    
    def rebalance(self, context):
        """调仓执行"""
        # 1. 获取基金池
        fund_list = self.get_fund_pool(context)
        
        if not fund_list:
            return
        
        # 2. 成交量风控(动态选择策略)
        if self.config.rebalance.volume_monitor:
            if self._volume_check(context):
                # 成交量过低, 全部转入货币基金
                target_weights = {self.config.rebalance.empty_keep_stock: 1.0}
            else:
                target_weights = self.calculate_allocation(context, fund_list)
        else:
            target_weights = self.calculate_allocation(context, fund_list)
        
        # 3. 检查是否需要调仓
        if not self.check_rebalance_needed(context, target_weights):
            return
        
        # 4. 执行调仓
        target_codes = set(target_weights.keys())
        current_codes = set(context.portfolio.positions.keys())
        
        # 卖出
        for code in current_codes - target_codes:
            if code != self.config.rebalance.empty_keep_stock:
                order_target_value(code, 0)
        
        # 买入/调整
        total_value = context.portfolio.total_value
        for code, weight in target_weights.items():
            target_value = total_value * weight
            order_target_value(code, target_value)
    
    def _volume_check(self, context) -> bool:
        """成交量监控: 连续N天低于均线 -> 空仓"""
        rb = self.config.rebalance
        target_market = '000300.XSHG'  # 可配置
        
        volume = attribute_history(target_market, 100, '1d', 'volume')['volume'].values
        vol_ma = np.convolve(volume, np.ones(rb.volume_ma_period)/rb.volume_ma_period, mode='valid')
        
        if len(vol_ma) < rb.volume_lag:
            return False
        
        vol_ratio = volume[-rb.volume_lag:] / vol_ma[-rb.volume_lag:] - 1
        
        return all(v < 0 for v in vol_ratio)
```

### 四、典型策略映射示例

#### 1. iAlpha 基金投资策略 (06/09)

```python
config = FundFOFConfig(
    pool=FundPoolConfig(
        funds=[
            '511260.XSHG',  # 十年国债ETF
            '518880.XSHG',  # 黄金ETF
            '513500.XSHG',  # 标普500ETF
            '513100.XSHG',  # 纳指100ETF
            '159928.XSHE',  # 消费ETF
            '512010.XSHG',  # 医药ETF
            '513050.XSHG',  # 中概互联ETF
        ],
    ),
    allocation=AllocationConfig(
        method=AllocationMethod.FIXED,
    ),
    rebalance=RebalanceConfig(
        frequency="monthly",
        threshold=0.10,  # 偏离10%才调仓
        trading_time="9:35",
    ),
    target_num=9,
)
# 固定配置, 每月11号调仓
# 每只基金目标仓位 = 初始资金 / 9
# 偏离超过10%或100*最新价时调仓
```

#### 2. FOF养老成长基金-v2.0 (14)

```python
config = FundFOFConfig(
    pool=FundPoolConfig(
        funds=[
            '515520.XSHG', '161907.XSHE', '512890.XSHG',  # 红利类
            '510050.XSHG', '510310.XSHG', '512910.XSHG',  # 宽基类
            '513050.XSHG', '510900.XSHG',                  # 海外类
            '518880.XSHG',                                  # 黄金
        ],
    ),
    allocation=AllocationConfig(
        method=AllocationMethod.RISK_PARITY,
        confidence_level=0.02,
        reference_cycle=250,
    ),
    rebalance=RebalanceConfig(
        frequency="monthly",
        threshold=0.05,
    ),
)
# 基于VaR/ES风险价值计算仓位
# 仓位 = (max_ES/ES) * (max_VaR/VaR) * 1.02^增长率 * 权重
# 选前5名, 其余配置债券基金
# RSI+ATR辅助买卖判断
```

#### 3. 波动率过滤后相关性最小etf轮动 (26)

```python
config = FundFOFConfig(
    pool=FundPoolConfig(
        funds=['512660.XSHG', '511010.XSHG', '510880.XSHG', ...],  # 30只ETF
        min_volatility=0.05,
        max_volatility=0.33,
    ),
    allocation=AllocationConfig(
        method=AllocationMethod.MIN_CORRELATION,
        correlation_period=729,
        min_corr_select_num=4,
        momentum_period=25,
    ),
    rebalance=RebalanceConfig(
        frequency="daily",
        trading_time="10:00",
    ),
    target_num=1,
)
# 先过滤波动率(5%-33%), 再计算3年相关性
# 选相关性最小的4只, 再做25日动量排序
# score = annualized_return * r_squared, 取第1名
```

#### 4. 趋势筛选后相关性最小etf轮动 (74)

```python
config = FundFOFConfig(
    pool=FundPoolConfig(
        funds=['512660.XSHG', '510880.XSHG', ...],  # 30只ETF
    ),
    allocation=AllocationConfig(
        method=AllocationMethod.MIN_CORRELATION,
        correlation_period=243,
        min_corr_select_num=4,
        momentum_period=25,
    ),
    rebalance=RebalanceConfig(
        frequency="daily",
        trading_time="10:00",
    ),
    target_num=1,
)
# 先用MA10/MA30趋势过滤: 短期均线在长期均线上方天数占比>3
# 再计算1年相关性, 选最小相关性的4只
# 最后25日动量排序取第1名
```

#### 5. FoF all in (94)

```python
config = FundFOFConfig(
    pool=FundPoolConfig(
        categories=['fund'],
        min_list_days=365,
        min_aum=1e8,
        min_avg_money=1e6,  # 流动性过滤
        max_volatility=0.19,  # 波动率小于指数
        min_volatility=1.0,
    ),
    allocation=AllocationConfig(
        method=AllocationMethod.VOLATILITY_PARITY,
        volatility_period=241,
    ),
    rebalance=RebalanceConfig(
        frequency="monthly",
    ),
)
# 全市场基金筛选: 规模>1亿, 流动性达标, 波动率1%-19%
# 权重 = 1/波动率, 归一化后95%配置
# 预期年化收益0.7%, 年化波动4.6%
```

#### 6. 场内基金定投价值平均增强策略 (69)

```python
config = FundFOFConfig(
    pool=FundPoolConfig(
        funds=['510300.XSHG', '159915.XSHE', '159905.XSHE'],
    ),
    allocation=AllocationConfig(
        method=AllocationMethod.FIXED,
    ),
    rebalance=RebalanceConfig(
        frequency="monthly",
        trading_time="open+30m",
    ),
)
# 价值平均策略: 每月目标市值 = 上月市值 * 1.005
# 本月应投入 = 目标市值 - 当前持仓市值
# 止盈: 收益>40%且回撤>9% -> 全仓止盈
#       收益>100%或1年涨幅>75% -> 全仓止盈
# 建仓: 从高点回撤至0.318黄金分割位以下开始建仓
```

#### 7. 基金跟随策略 (17)

```python
config = FundFOFConfig(
    pool=FundPoolConfig(
        categories=['stock'],
    ),
    allocation=AllocationConfig(
        method=AllocationMethod.MOMENTUM,
        momentum_period=20,
    ),
    rebalance=RebalanceConfig(
        frequency="monthly",
        trading_time="open",
    ),
    target_num=5,
)
# 选股逻辑: 获取基金持仓最多的股票(finance.FUND_PORTFOLIO_STOCK)
# 比较近1季度 vs 前1季度基金持仓市值变化
# 按基金增持幅度排序, 取前5名
# 仅在2/5/8/11月(季报后)执行
```

---

## 第四部分: 完整文件索引

### CTA/期货策略文件

| 序号 | 文件名 | 策略类型 | 核心信号 | 关键参数 |
|-----|--------|---------|---------|---------|
| 1 | 27 中证500指增+CTA.txt | 股票+期货对冲 | EMA(2/6)+ATR止损 | ATRdays=20, stop=5 |
| 2 | 63 生猪期货CTA策略.txt | 趋势跟踪 | MACD+均线趋势 | loss_ratio=0.03 |
| 3 | 71 【股指策略】周内与日内结合CTA.txt | 日内+周线 | 分钟量价imbalance+周信号 | leverage=3 |
| 4 | 71 期货日内策略三价均线结合ATR指标.txt | 日内突破 | 三价MA(5/20)+ATR | atr_length=14 |
| 5 | 76 日内交易策略R-breaker.txt | R-breaker | R3/R2/R1/S1/S2/S3 | theta=0.35 |
| 6 | 73 基于期权PCR与标的波动率价差的股指期货套利.txt | 期权套利 | PCR+波动率相关性 | pcr_period=20 |
| 7 | 40 低风险高收益的期货策略.txt | 海龟突破 | 20日高低点+涨跌天数 | duo/kong评分 |
| 8 | 45 价值投资+期货对冲V4.0.txt | 股票+期货对冲 | EMA(2/5)+ATR止损 | stock_share=0.7 |
| 9 | 58 严格资金管理，股指期货套利.txt | 跨期套利 | 近远月价差分位数 | quantile=0.9/0.3 |
| 10 | 72/88 【股指期货】收盘折溢价策略.txt | 跨期套利 | 收盘价折溢价 | - |
| 11 | 57 股指期货套利.txt | 跨期套利 | 价差回归 | - |
| 12 | 36 致敬市场(6)，指数期货贴水.txt | 贴水套利 | 期货贴水率 | - |
| 13 | 88 【股指期货】收盘折溢价策略.txt | 跨期套利 | 折溢价统计 | - |

### 可转债策略文件

| 序号 | 文件名 | 策略类型 | 核心逻辑 | 关键参数 |
|-----|--------|---------|---------|---------|
| 1 | 86 可转债双低策略.ipynb | 双低轮动 | 双低值排序 | bond_num=10 |
| 2 | 95 可转债双低轮动回测2.0.ipynb | 双低轮动 | double_order=close+100*溢价率 | kzz_num=10, 年化101% |

### 基金/FOF策略文件

| 序号 | 文件名 | 策略类型 | 核心逻辑 | 关键参数 |
|-----|--------|---------|---------|---------|
| 1 | 06/09 iAlpha 基金投资策略.txt | 固定配置 | 固定比例再平衡 | position_n=9, 月调仓 |
| 2 | 14 FOF养老成长基金-v2.0.txt | 风险平价 | VaR/ES风险预算 | stockCount=5, 月调仓 |
| 3 | 17 基金跟随策略.txt | 基金跟随 | 基金重仓股跟随 | max_hold=5, 季调仓 |
| 4 | 26 波动率过滤后相关性最小etf轮动.txt | 最小相关性 | 波动率过滤+相关性+动量 | target_num=1 |
| 5 | 74 趋势筛选后相关性最小etf轮动.txt | 最小相关性 | 趋势过滤+相关性+动量 | target_num=1 |
| 6 | 81 无杠杆，稳定盈利的etf轮动.txt | 动量轮动 | 涨幅排序+成交量风控 | 持仓3只 |
| 7 | 82 无需先验知识，动态选择的etf轮动.txt | 动量轮动 | 成交量动态选基+动量 | top7+情绪监控 |
| 8 | 62 基金溢价（模拟效果好！）.txt | 折溢价套利 | 折价买入溢价卖出 | least_premium=2.5% |
| 9 | 69 场内基金定投价值平均增强策略.txt | 定投增强 | 价值平均+止盈 | month_growth=1.005 |
| 10 | 94 FoF, all in.ipynb | 波动率平价 | 全市场筛选+1/波动率加权 | 78只基金 |
| 11 | 68 折价基金统计套利.txt | 折溢价套利 | 折价率排序 | - |
| 12 | 53 基于大盘PE标准差偏离度的聪明基金定投策略.txt | 定投增强 | PE偏离度定投 | - |
| 13 | 78 【基金增强思考2.0】.txt | 动量轮动 | 基金持续性+周期 | - |
| 14 | 80 公募基金抱团.txt | 基金跟随 | 基金持仓集中度 | - |
| 15 | 84 多大规模的基金收益最好？.txt | 规模因子 | 基金规模研究 | - |
