# 任务 06：SignalMaker 指标工厂抽取结果

## 1. 概述

本文档抽取自 QuantsPlaybook/SignalMaker 及聚宽侧信号实现，目标是构建一个可拼装、可扩展的指标工厂，让新策略可以像拼积木一样组合单指标/单信号模块。

**核心原则**：
- 指标工厂只负责计算原始信号值（-1/0/1 或连续值）
- 策略组合层负责投票规则、阈值判断、最终仓位
- 清晰分离：指标 ≠ 策略

---

## 2. 第一版最值得抽取的信号列表

### 2.1 趋势跟踪类 (Trend Following)

| 信号名称 | 来源 | 输入 | 输出 | 说明 |
|---------|------|------|------|------|
| `AlligatorSignal` | 鳄鱼线择时 | close_df | signal_df(-1/0/1) | 三条均线多头排列/空头排列 |
| `AOMomentumSignal` | AO动量震荡 | high_df, low_df | signal_df(-1/0/1) | 连续N日上行/下行 |
| `MACDSignal` | MACD零轴信号 | close_df | signal_df(-1/0/1) | DIF上穿DEA且能量柱转红 |
| `ICUMASignal` | ICU均线 | close_df | signal_df(-1/0/1) | 稳健回归均线方向 |

### 2.2 分形/形态类 (Fractal/Pattern)

| 信号名称 | 来源 | 输入 | 输出 | 说明 |
|---------|------|------|------|------|
| `FractalSignal` | 鳄鱼线择时 | high_df, low_df, close_df | signal_df(-1/0/1) | 顶分型/底分型+突破确认 |
| `AlignmentSignal` | 通用工具 | arr(n,3) | signal_arr | 多头排列/空头排列检测 |

### 2.3 波动率/区间类 (Volatility/Range)

| 信号名称 | 来源 | 输入 | 输出 | 说明 |
|---------|------|------|------|------|
| `NoiseAreaSignal` | ETF日内动量 | ohlcv_df | signal_df | 噪声区域上下边界+vwap |
| `QRSSignal` | QRS择时 | low_df, high_df | signal_df(连续值) | Beta*zscore*corr_regulation |

### 2.4 成交量类 (Volume)

| 信号名称 | 来源 | 输入 | 输出 | 说明 |
|---------|------|------|------|------|
| `VMACDMTMSignal` | 成交量择时 | volume_df | signal_df(连续值) | VMACD动量累积 |

### 2.5 希尔伯特变换类 (HHT)

| 信号名称 | 来源 | 输入 | 输出 | 说明 |
|---------|------|------|------|------|
| `HTSignal` | HHT择时 | close_series | signal_series(0/1) | 瞬时相位判断 |
| `HHTSignal` | HHT择时 | close_series | signal_series(0/1) | EMD/VMD分解后相位判断 |

### 2.6 资金流向类 (Flow)

| 信号名称 | 来源 | 输入 | 输出 | 说明 |
|---------|------|------|------|------|
| `NorthMoneySignal` | 北向资金 | north_money_df | signal_series(-1/0/1) | 分位数突破 |

---

## 3. 统一 Signal Interface

### 3.1 基础接口定义

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Union, Optional
import pandas as pd
import numpy as np


class BaseSignal(ABC):
    """信号计算器基类
    
    所有具体信号计算器必须继承此基类，实现 compute 方法。
    输入输出格式统一，便于策略层拼装。
    """
    
    # 信号元信息
    name: str = "base"
    category: str = "unknown"  # trend, mean_reversion, volatility, pattern, flow
    output_type: str = "discrete"  # discrete(-1/0/1), continuous, binary(0/1)
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化信号计算器
        
        Args:
            config: 信号计算参数配置
        """
        self.config = config or {}
        self._validate_config()
    
    @abstractmethod
    def compute(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """计算信号
        
        Args:
            price_df: 价格数据，必须包含 OHLCV 列
            feature_df: 特征数据，用于非价格类信号
            **kwargs: 额外参数
            
        Returns:
            {
                "signal_series": pd.Series,  # 单资产信号 (可选)
                "signal_df": pd.DataFrame,   # 多资产信号 (可选)
                "meta": {
                    "name": str,
                    "category": str,
                    "output_type": str,
                    "params": Dict,
                    "timestamp": datetime,
                }
            }
        """
        pass
    
    def _validate_config(self) -> None:
        """验证配置参数"""
        pass
    
    def get_meta(self) -> Dict[str, Any]:
        """获取信号元信息"""
        return {
            "name": self.name,
            "category": self.category,
            "output_type": self.output_type,
            "params": self.config,
        }


class DiscreteSignal(BaseSignal):
    """离散信号基类 (-1/0/1)"""
    output_type = "discrete"
    
    def compute(self, **kwargs) -> Dict[str, Any]:
        result = self._compute_impl(**kwargs)
        # 标准化输出为 -1, 0, 1
        if "signal_df" in result:
            result["signal_df"] = result["signal_df"].clip(-1, 1).fillna(0)
        if "signal_series" in result:
            result["signal_series"] = result["signal_series"].clip(-1, 1).fillna(0)
        return result
    
    @abstractmethod
    def _compute_impl(self, **kwargs) -> Dict[str, Any]:
        pass


class ContinuousSignal(BaseSignal):
    """连续信号基类"""
    output_type = "continuous"
    
    def compute(self, **kwargs) -> Dict[str, Any]:
        result = self._compute_impl(**kwargs)
        return result
    
    @abstractmethod
    def _compute_impl(self, **kwargs) -> Dict[str, Any]:
        pass


class BinarySignal(BaseSignal):
    """二进制信号基类 (0/1)"""
    output_type = "binary"
    
    def compute(self, **kwargs) -> Dict[str, Any]:
        result = self._compute_impl(**kwargs)
        # 标准化输出为 0, 1
        if "signal_df" in result:
            result["signal_df"] = (result["signal_df"] > 0).astype(int)
        if "signal_series" in result:
            result["signal_series"] = (result["signal_series"] > 0).astype(int)
        return result
    
    @abstractmethod
    def _compute_impl(self, **kwargs) -> Dict[str, Any]:
        pass
```

### 3.2 信号注册与工厂

```python
from typing import Type, Dict


class SignalRegistry:
    """信号注册中心"""
    
    _signals: Dict[str, Type[BaseSignal]] = {}
    
    @classmethod
    def register(cls, name: str, signal_class: Type[BaseSignal]):
        """注册信号计算器"""
        cls._signals[name] = signal_class
        
    @classmethod
    def get(cls, name: str) -> Type[BaseSignal]:
        """获取信号计算器类"""
        if name not in cls._signals:
            raise ValueError(f"Unknown signal: {name}")
        return cls._signals[name]
    
    @classmethod
    def list_signals(cls, category: Optional[str] = None) -> Dict[str, Type[BaseSignal]]:
        """列出所有已注册信号"""
        if category is None:
            return cls._signals.copy()
        return {
            name: sig for name, sig in cls._signals.items()
            if sig.category == category
        }
    
    @classmethod
    def create(cls, name: str, config: Optional[Dict] = None) -> BaseSignal:
        """创建信号计算器实例"""
        signal_class = cls.get(name)
        return signal_class(config)


# 装饰器注册方式
def register_signal(name: str):
    """信号注册装饰器"""
    def decorator(cls: Type[BaseSignal]):
        SignalRegistry.register(name, cls)
        return cls
    return decorator
```

---

## 4. 每个信号的输入输出格式

### 4.1 AlligatorSignal (鳄鱼线)

```python
@register_signal("alligator")
class AlligatorSignal(DiscreteSignal):
    """鳄鱼线信号
    
    输入:
        price_df: pd.DataFrame
            index: datetime
            columns: asset codes
            values: close prices
        config: {
            "periods": (13, 8, 5),      # 下颚线、牙齿线、上唇线周期
            "lag": (8, 5, 3),            # 滞后周期
            "keep_pre_status": True,     # 是否保持前一状态
        }
    
    输出:
        {
            "signal_df": pd.DataFrame,   # -1(空头排列), 0(无信号), 1(多头排列)
            "meta": {
                "raw_lines": pd.DataFrame,  # 原始鳄鱼线三条均线值
            }
        }
    """
    name = "alligator"
    category = "trend"
```

### 4.2 AOMomentumSignal (AO动量)

```python
@register_signal("ao_momentum")
class AOMomentumSignal(DiscreteSignal):
    """AO动量震荡信号
    
    输入:
        price_df: pd.DataFrame
            columns: ["high", "low"] or separate high_df/low_df
        config: {
            "periods": (5, 34),
            "window": 3,                 # 连续判断窗口
            "keep_pre_status": True,
        }
    
    输出:
        {
            "signal_df": pd.DataFrame,   # -1(连续下行), 0, 1(连续上行)
            "meta": {
                "ao_values": pd.DataFrame,  # 原始AO值
            }
        }
    """
    name = "ao_momentum"
    category = "trend"
```

### 4.3 MACDSignal

```python
@register_signal("macd")
class MACDSignal(DiscreteSignal):
    """MACD零轴信号
    
    输入:
        price_df: pd.DataFrame
            values: close prices
        config: {
            "fastperiod": 12,
            "slowperiod": 26,
            "signalperiod": 9,
            "keep_pre_status": True,
        }
    
    输出:
        {
            "signal_df": pd.DataFrame,   # -1(看空), 0, 1(看多)
            "meta": {
                "dif": pd.DataFrame,
                "dea": pd.DataFrame,
                "hist": pd.DataFrame,
            }
        }
    """
    name = "macd"
    category = "trend"
```

### 4.4 FractalSignal (分形)

```python
@register_signal("fractal")
class FractalSignal(DiscreteSignal):
    """分型信号
    
    输入:
        price_df: pd.DataFrame
            columns: ["high", "low", "close"]
        config: {
            "window": 3,
            "keep_pre_status": True,
        }
    
    输出:
        {
            "signal_df": pd.DataFrame,   # -1(底分型突破), 0, 1(顶分型突破)
            "meta": {
                "fractal_type": pd.DataFrame,  # 1(顶分型), -1(底分型)
            }
        }
    """
    name = "fractal"
    category = "pattern"
```

### 4.5 NoiseAreaSignal (噪声区域)

```python
@register_signal("noise_area")
class NoiseAreaSignal(ContinuousSignal):
    """噪声区域信号
    
    输入:
        price_df: pd.DataFrame (分钟级)
            columns: ["code", "trade_time", "open", "high", "low", "close", "volume"]
        config: {
            "window": 14,                # 波动率计算窗口
        }
    
    输出:
        {
            "signal_df": pd.DataFrame,   # 包含 upperbound, lowerbound, vwap
            "meta": {
                "sigma": pd.DataFrame,   # 波动率
            }
        }
    """
    name = "noise_area"
    category = "volatility"
```

### 4.6 QRSSignal

```python
@register_signal("qrs")
class QRSSignal(ContinuousSignal):
    """QRS择时信号
    
    输入:
        feature_df: pd.DataFrame
            columns: low values
        aux_df: pd.DataFrame
            columns: high values
        config: {
            "regression_window": 18,
            "zscore_window": 600,
            "n": 2,                      # corr幂次
            "adjust_regulation": False,
            "use_simple_beta": False,
        }
    
    输出:
        {
            "signal_df": pd.DataFrame,   # 连续信号值
            "meta": {
                "beta": pd.DataFrame,
                "regulation": pd.DataFrame,
                "zscore_beta": pd.DataFrame,
            }
        }
    """
    name = "qrs"
    category = "volatility"
```

### 4.7 VMACDMTMSignal

```python
@register_signal("vmacd_mtm")
class VMACDMTMSignal(ContinuousSignal):
    """VMACD动量信号
    
    输入:
        feature_df: pd.DataFrame
            values: volume
        config: {
            "fastperiod": 12,
            "slowperiod": 26,
            "signalperiod": 9,
            "period": 60,                # zscore和动量窗口
        }
    
    输出:
        {
            "signal_df": pd.DataFrame,   # 连续动量值
            "meta": {
                "vmacd": pd.DataFrame,
                "zscore_vmacd": pd.DataFrame,
            }
        }
    """
    name = "vmacd_mtm"
    category = "volume"
```

### 4.8 HTSignal / HHTSignal

```python
@register_signal("ht")
class HTSignal(BinarySignal):
    """希尔伯特变换信号
    
    输入:
        price_df: pd.DataFrame
            values: close prices
        config: {
            "ma_period": 60,             # 平滑周期
            "ht_period": 30,             # 变换周期
        }
    
    输出:
        {
            "signal_series": pd.Series,  # 0 or 1
            "meta": {
                "phase": pd.Series,      # 瞬时相位
            }
        }
    """
    name = "ht"
    category = "trend"


@register_signal("hht")
class HHTSignal(BinarySignal):
    """HHT信号(EMD/VMD分解)
    
    输入:
        price_df: pd.DataFrame
            values: close prices
        config: {
            "hht_period": 60,
            "imf_index": 2,              # 使用第几个IMF
            "max_imf": 9,
            "method": "EMD",             # or "VMD"
        }
    
    输出:
        {
            "signal_series": pd.Series,  # 0 or 1
        }
    """
    name = "hht"
    category = "trend"
```

### 4.9 NorthMoneySignal

```python
@register_signal("north_money")
class NorthMoneySignal(DiscreteSignal):
    """北向资金信号
    
    输入:
        feature_df: pd.DataFrame
            columns: ["north_money"]
        config: {
            "window": 60,
            "upper_quantile": 0.8,
            "lower_quantile": 0.2,
        }
    
    输出:
        {
            "signal_series": pd.Series,  # -1, 0, 1
            "meta": {
                "upper": pd.Series,
                "lower": pd.Series,
            }
        }
    """
    name = "north_money"
    category = "flow"
```

---

## 5. 推荐目录与文件拆分

```
strategy_kits/signals/indicator_factory/
├── __init__.py                    # 导出主要类和函数
├── base.py                        # BaseSignal, DiscreteSignal, ContinuousSignal, BinarySignal
├── registry.py                    # SignalRegistry, register_signal
├── factory.py                     # SignalFactory, 批量信号计算
├── utils.py                       # 通用工具函数 (sliding_window等)
│
├── trend/                         # 趋势跟踪类信号
│   ├── __init__.py
│   ├── alligator.py              # 鳄鱼线信号
│   ├── ao.py                     # AO动量
│   ├── macd.py                   # MACD信号
│   └── icu_ma.py                 # ICU均线
│
├── pattern/                       # 形态/分形类信号
│   ├── __init__.py
│   ├── fractal.py                # 分型信号
│   └── alignment.py              # 排列检测
│
├── volatility/                    # 波动率类信号
│   ├── __init__.py
│   ├── noise_area.py             # 噪声区域
│   └── qrs.py                    # QRS信号
│
├── volume/                        # 成交量类信号
│   ├── __init__.py
│   └── vmacd_mtm.py              # VMACD动量
│
├── transform/                     # 变换类信号
│   ├── __init__.py
│   ├── ht.py                     # 希尔伯特变换
│   └── hht.py                    # HHT (EMD/VMD)
│
└── flow/                          # 资金流向类信号
    ├── __init__.py
    └── north_money.py            # 北向资金
```

---

## 6. 信号组合使用示例

```python
from strategy_kits.signals.indicator_factory import (
    SignalRegistry, SignalFactory
)

# 单信号使用
config = {"periods": (13, 8, 5), "lag": (8, 5, 3)}
signal = SignalRegistry.create("alligator", config)
result = signal.compute(price_df=close_df)
signal_df = result["signal_df"]

# 多信号组合
factory = SignalFactory()
factory.add_signal("alligator", config)
factory.add_signal("macd", {"keep_pre_status": True})
factory.add_signal("fractal", {"window": 3})

# 批量计算
results = factory.compute_all(price_df=data)

# 投票组合 (策略层)
def vote_signals(results, weights=None):
    """信号投票
    
    weights: 各信号权重，None则等权
    """
    combined = pd.DataFrame()
    for name, result in results.items():
        sig = result.get("signal_df") or result.get("signal_series")
        combined[name] = sig
    
    if weights:
        vote = combined.mul(pd.Series(weights)).sum(axis=1)
    else:
        vote = combined.mean(axis=1)
    
    # 阈值判断生成最终仓位
    position = pd.cut(vote, bins=[-1, -0.3, 0.3, 1], labels=[-1, 0, 1])
    return position
```

---

## 7. 不该抽的内容清单

| 内容 | 理由 | 应存放位置 |
|------|------|-----------|
| `evaluate_signals()` 投票规则 | 策略专属逻辑 | strategy_templates/ |
| 固定阈值 (如 QRS > 1.5) | 策略参数 | strategy_templates/ |
| 研报专属标签定义 | 场景特定 | validation/ |
| 最终仓位计算 | 策略层职责 | strategy_templates/ |
| 多信号冲突解决规则 | 策略专属 | strategy_templates/ |

---

## 8. 与现有模块的关系

```
┌─────────────────────────────────────────────────────────┐
│                   Strategy Template                      │
│         (信号组合、投票规则、仓位管理)                     │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│               indicator_factory (本模块)                 │
│         (单信号计算、统一接口、信号注册中心)               │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              factor_preprocess (已有)                    │
│              regime_filters (已有)                       │
│         (数据预处理、市场状态过滤)                        │
└─────────────────────────────────────────────────────────┘
```

---

## 9. 依赖关系

```
indicator_factory/
├── base.py           <- 无外部依赖 (除 pandas/numpy)
├── registry.py       <- 依赖 base.py
├── utils.py          <- numpy only
├── trend/*           <- talib (optional), scipy (ICU)
├── pattern/*         <- numpy/pandas
├── volatility/*      <- numpy/pandas, scipy (QRS)
├── volume/*          <- talib (optional)
├── transform/*       <- scipy, PyEMD/VMD (optional)
└── flow/*            <- pandas only
```

**核心依赖**: pandas, numpy
**可选依赖**: talib, scipy, PyEMD, vmdpy

---

## 10. 迁移检查清单

- [ ] base.py - 基础接口
- [ ] registry.py - 注册中心
- [ ] utils.py - 滑动窗口等工具
- [ ] trend/alligator.py - 鳄鱼线
- [ ] trend/ao.py - AO动量
- [ ] trend/macd.py - MACD
- [ ] trend/icu_ma.py - ICU均线
- [ ] pattern/fractal.py - 分型
- [ ] pattern/alignment.py - 排列
- [ ] volatility/noise_area.py - 噪声区域
- [ ] volatility/qrs.py - QRS
- [ ] volume/vmacd_mtm.py - VMACD
- [ ] transform/ht.py - 希尔伯特
- [ ] transform/hht.py - HHT
- [ ] flow/north_money.py - 北向资金
- [ ] tests/ - 单元测试
- [ ] examples/ - 使用示例
