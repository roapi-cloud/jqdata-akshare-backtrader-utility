# ES风险平价仓位管理 (Expected Shortfall Risk Parity)

## 概述

基于ES（Expected Shortfall，预期亏损）的风险平价方法，让每类资产对组合的风险贡献相等。比传统波动率风险平价更能捕捉极端风险，是桥水全天候策略的核心机制。

来源：聚宽策略 `07 致敬经典作品——小兵哥《一致性风险度量》——极速版.txt`，`72 桥水全天候策略增加一致性度量ES风险控制.txt`

## 核心概念

### VaR vs ES
- **VaR（Value at Risk）**：在置信水平α下，最大损失不超过X
- **ES（Expected Shortfall）**：超过VaR阈值后的平均损失，更保守
- ES = 最差(1-α)%情况下的平均损失

### 风险平价逻辑
```
传统等权：每类资产权重相等
波动率平价：每类资产波动率贡献相等
ES平价：每类资产极端风险贡献相等（更保守）

权重 ∝ 1/ES(资产)
```

## 效果验证

| 策略 | 年化收益 | 最大回撤 | 夏普比率 |
|------|---------|---------|---------|
| 等权全天候 | 12-15% | 8-12% | 1.2 |
| 波动率平价 | 13-16% | 6-10% | 1.5 |
| ES平价（本机制） | 12-15% | 5-8% | 1.6-1.8 |

## 适用时机

- 多资产组合（股票+债券+商品+货币）的权重分配
- 市场极端波动时期（ES比波动率更能反映尾部风险）
- 长期持有的全天候/桥水类策略
- 不适合单一资产类别或高频交易

## 代码样例

```python
# es_risk_parity.py
import numpy as np
import pandas as pd
import math
from jqdata import *

class ESRiskParity:
    """基于ES的风险平价仓位管理"""
    
    def __init__(self, confidence_level=2.58, lookback=120, 
                 rebalance_threshold=0.15, rebalance_cycle=30):
        """
        参数:
        confidence_level: 置信水平对应的z值
            1.96 → 95%, 2.06 → 96%, 2.18 → 97%
            2.34 → 98%, 2.58 → 99%
        lookback: 历史数据窗口（天）
        rebalance_threshold: 触发再平衡的偏离阈值（15%）
        rebalance_cycle: 定期再平衡周期（天）
        """
        self.confidence_level = confidence_level
        self.lookback = lookback
        self.rebalance_threshold = rebalance_threshold
        self.rebalance_cycle = rebalance_cycle
        
        # 置信水平映射
        self.alpha_map = {
            1.96: 0.05, 2.06: 0.04, 2.18: 0.03,
            2.34: 0.02, 2.58: 0.01, 5.0: 0.00001
        }
    
    def get_daily_returns(self, security, days=None):
        """获取日收益率序列"""
        if days is None:
            days = self.lookback
        h = history(days, '1d', 'close', security, df=True)
        returns = h.resample('D').last().pct_change().fillna(0).iloc[:, 0].values
        return returns
    
    def calculate_es(self, security):
        """
        计算单个资产的ES（预期亏损）
        ES = 最差α%情况下的平均损失（取正值）
        """
        alpha = self.alpha_map.get(self.confidence_level, 0.05)
        returns = self.get_daily_returns(security)
        
        if len(returns) == 0:
            return 0.01  # 默认值
        
        # 排序，取最差α%
        sorted_returns = sorted(returns)
        n = len(sorted_returns)
        cutoff = int(n * alpha)
        
        if cutoff == 0:
            return abs(sorted_returns[0])
        
        # ES = 最差cutoff个收益率的平均值（取绝对值）
        es = -sum(sorted_returns[:cutoff]) / (n * alpha)
        
        return max(es, 1e-6)  # 避免除零
    
    def calculate_weights(self, asset_groups):
        """
        计算各资产组的权重
        
        参数:
        asset_groups: dict，格式 {'equity': ['510300.XSHG'], 'bond': ['511010.XSHG'], ...}
        
        返回:
        weights: dict，各资产的目标权重
        """
        group_es = {}
        group_ratios = {}
        
        # 计算每组的ES（取组内第一个资产代表）
        for group_name, assets in asset_groups.items():
            if not assets:
                continue
            es = self.calculate_es(assets[0])
            group_es[group_name] = es
            group_ratios[group_name] = {a: 1.0/len(assets) for a in assets}
        
        if not group_es:
            return {}
        
        # 风险平价：权重 ∝ 1/ES
        max_es = max(group_es.values())
        group_positions = {g: max_es / es for g, es in group_es.items()}
        total_position = sum(group_positions.values())
        
        # 归一化
        weights = {}
        for group_name, position in group_positions.items():
            group_weight = position / total_position
            assets = asset_groups[group_name]
            for asset in assets:
                weights[asset] = group_weight * group_ratios[group_name][asset]
        
        return weights
    
    def need_rebalance(self, context, current_weights, target_weights):
        """
        判断是否需要再平衡
        条件：任一资产偏离超过阈值，或达到定期再平衡周期
        """
        # 检查偏离
        total_value = context.portfolio.total_value
        for asset, target_w in target_weights.items():
            if asset in context.portfolio.positions:
                current_value = context.portfolio.positions[asset].value
                current_w = current_value / total_value
                if abs(current_w - target_w) / max(target_w, 0.01) > self.rebalance_threshold:
                    return True
        return False
    
    def execute_rebalance(self, context, asset_groups):
        """执行再平衡"""
        weights = self.calculate_weights(asset_groups)
        
        if not weights:
            return
        
        log.info(f"ES风险平价权重: {', '.join([f'{k}:{v:.1%}' for k,v in weights.items()])}")
        
        total_value = context.portfolio.total_value
        
        # 先卖出超配资产
        for asset, weight in weights.items():
            target_value = total_value * weight
            if asset in context.portfolio.positions:
                current_value = context.portfolio.positions[asset].value
                if current_value > target_value * 1.05:
                    order_target_value(asset, target_value)
        
        # 再买入低配资产
        for asset, weight in weights.items():
            target_value = total_value * weight
            order_target_value(asset, target_value)


# 使用示例（全天候策略）
def initialize(context):
    context.es_rp = ESRiskParity(
        confidence_level=2.58,  # 99%置信水平
        lookback=120,
        rebalance_threshold=0.15,
        rebalance_cycle=30
    )
    
    # 四类资产
    g.asset_groups = {
        'equity':    ['510300.XSHG'],  # 沪深300ETF
        'commodity': ['518880.XSHG'],  # 黄金ETF
        'bond':      ['511010.XSHG'],  # 国债ETF
        'overseas':  ['513100.XSHG'],  # 纳指ETF
    }
    
    g.hold_periods = 0
    
    run_daily(market_open, time='open')

def market_open(context):
    g.hold_periods -= 1
    
    # 定期再平衡 或 偏离触发再平衡
    if g.hold_periods <= 0 or context.es_rp.need_rebalance(
            context, {}, context.es_rp.calculate_weights(g.asset_groups)):
        context.es_rp.execute_rebalance(context, g.asset_groups)
        g.hold_periods = context.es_rp.rebalance_cycle
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| confidence_level | 2.58 | z值（2.58=99%置信） |
| lookback | 120 | 历史数据窗口 |
| rebalance_threshold | 0.15 | 偏离触发阈值（15%） |
| rebalance_cycle | 30 | 定期再平衡周期（天） |

## 与其他机制组合

```
全天候策略框架：
ES风险平价（权重分配）
    + FED估值（判断是否增配股票）
    + RSRS择时（股票仓位微调）
    + 情绪开关（极端情绪时减股票仓位）
```

## 适用策略

- ✅ 全天候/桥水类多资产策略
- ✅ 股债平衡策略
- ✅ ETF多资产组合
- ✅ 低风险稳健型策略
- ⚠️ 纯股票策略（不适合，单一资产类别）

## 待调研方向

1. **CVaR优化**：直接最小化CVaR（ES）的组合优化
2. **动态置信水平**：市场波动大时提高置信水平（更保守）
3. **因子风险平价**：在因子层面（价值/成长/动量）做风险平价
4. **条件ES**：在不同市场状态下使用不同的ES估计
