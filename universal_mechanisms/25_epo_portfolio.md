# EPO增强型投资组合优化 (Enhanced Portfolio Optimization)

## 概述

EPO（Enhanced Portfolio Optimization）是对传统均值-方差优化的改进，通过收缩相关性矩阵解决过拟合问题。相比等权分配，EPO能在保持分散化的同时，更好地利用动量信号。

来源：聚宽策略 `52 增强型投资组合优化（EPO）方法研究.txt`，`32 EPO优化低相关etf组合.txt`

## 核心思想

传统MVO（均值-方差优化）的问题：
- 对预期收益率估计误差极度敏感
- 容易产生极端权重（全押一只）
- 历史协方差矩阵不稳定

EPO的改进：
- 对相关性矩阵进行收缩（shrinkage）：`Σ_shrunk = (1-w)×Σ + w×I`
- w=0：完全使用历史相关性（传统MVO）
- w=1：完全使用单位矩阵（等权分配）
- 0<w<1：在两者之间平衡，减少过拟合

## 两种模式

### Simple模式
```
w_EPO = (1/λ) × Σ_shrunk⁻¹ × signal
```
- signal：动量信号（预期收益率）
- λ：风险厌恶系数

### Anchored模式（推荐）
```
w_EPO = Σ_shrunk⁻¹ × [(1-w)×γ×signal + w×V×anchor]
```
- anchor：基准权重（如风险平价权重）
- 在信号和基准之间平衡

## 效果验证

| 策略 | 年化收益 | 最大回撤 | 夏普比率 |
|------|---------|---------|---------|
| 等权ETF轮动 | 30-40% | 15-20% | 1.5 |
| EPO优化ETF轮动 | 35-50% | 12-18% | 1.8-2.2 |
| EPO+低相关组合 | 25-35% | 10-15% | 2.0+ |

## 适用时机

- ETF轮动策略的权重优化（替代等权分配）
- 多资产组合（股票+债券+商品+海外）的配置
- 持仓数量较多（5只以上）时效果更明显
- 不适合单只持仓或持仓数量<3只的策略

## 代码样例

```python
# epo_portfolio.py
import numpy as np
import pandas as pd
from scipy.linalg import solve
from jqdata import *

class EPOOptimizer:
    """EPO增强型投资组合优化器"""
    
    def __init__(self, lookback=120, shrinkage=0.5, lambda_=10, method='anchored'):
        """
        参数:
        lookback: 历史数据窗口（天）
        shrinkage: 收缩系数w（0=纯MVO, 1=等权）
        lambda_: 风险厌恶系数
        method: 'simple' 或 'anchored'
        """
        self.lookback = lookback
        self.w = shrinkage
        self.lambda_ = lambda_
        self.method = method
    
    def epo(self, returns, signal, anchor=None):
        """
        计算EPO权重
        
        参数:
        returns: DataFrame，资产收益率历史
        signal: array，预期收益率信号（如动量）
        anchor: array，基准权重（anchored模式使用）
        
        返回:
        weights: array，优化后的权重
        """
        n = returns.shape[1]
        vcov = returns.cov().values
        corr = returns.corr().values
        
        # 对角方差矩阵
        V = np.diag(np.diag(vcov))
        std = np.sqrt(V)
        
        # 收缩相关性矩阵
        I = np.eye(n)
        shrunk_cor = (1 - self.w) * corr + self.w * I
        
        # 收缩协方差矩阵
        cov_tilde = std @ shrunk_cor @ std
        inv_cov = solve(cov_tilde, np.eye(n))
        
        s = np.array(signal)
        
        if self.method == 'simple':
            weights = (1.0 / self.lambda_) * inv_cov @ s
        elif self.method == 'anchored':
            if anchor is None:
                # 默认使用风险平价作为锚点
                d = np.diag(vcov)
                anchor = (1.0 / d) / (1.0 / d).sum()
            
            a = np.array(anchor)
            gamma = np.sqrt(a.T @ cov_tilde @ a) / \
                    np.sqrt(s.T @ inv_cov @ cov_tilde @ inv_cov @ s)
            weights = inv_cov @ ((1 - self.w) * gamma * s + self.w * V @ a)
        else:
            raise ValueError(f"Unknown method: {self.method}")
        
        # 归一化（去除负权重，归一化到1）
        weights = np.array([max(0, w) for w in weights])
        total = weights.sum()
        if total > 0:
            weights = weights / total
        else:
            weights = np.ones(n) / n  # 退化为等权
        
        return weights
    
    def get_weights(self, etf_pool, end_date, signal_type='momentum'):
        """
        获取ETF组合权重
        
        参数:
        etf_pool: ETF代码列表
        end_date: 截止日期
        signal_type: 信号类型 'momentum' 或 'equal'
        """
        # 获取历史价格
        prices = get_price(
            etf_pool, count=self.lookback + 1,
            end_date=end_date, frequency='daily',
            fields=['close']
        )['close']
        
        returns = prices.pct_change().dropna()
        
        if len(returns) < 30:
            return np.ones(len(etf_pool)) / len(etf_pool)
        
        # 计算信号
        if signal_type == 'momentum':
            # 动量信号：近期平均收益率
            signal = returns.mean().values
        else:
            signal = np.ones(len(etf_pool)) / len(etf_pool)
        
        # 风险平价锚点
        d = np.diag(returns.cov().values)
        anchor = (1.0 / d) / (1.0 / d).sum()
        
        try:
            weights = self.epo(returns, signal, anchor)
        except Exception as e:
            log.warning(f"EPO优化失败，使用等权: {e}")
            weights = np.ones(len(etf_pool)) / len(etf_pool)
        
        return weights
    
    def rebalance(self, context, etf_pool):
        """执行再平衡"""
        weights = self.get_weights(etf_pool, context.previous_date)
        total_value = context.portfolio.total_value
        
        log.info(f"EPO权重: {dict(zip(etf_pool, [f'{w:.1%}' for w in weights]))}")
        
        for i, etf in enumerate(etf_pool):
            target_value = total_value * weights[i]
            order_target_value(etf, target_value)


# 使用示例
def initialize(context):
    context.epo = EPOOptimizer(
        lookback=120,
        shrinkage=0.5,   # 0.5 = 在MVO和等权之间平衡
        lambda_=10,
        method='anchored'
    )
    
    g.etf_pool = [
        '518880.XSHG',  # 黄金ETF
        '513100.XSHG',  # 纳指100
        '159915.XSHE',  # 创业板ETF
        '510880.XSHG',  # 红利ETF
        '511010.XSHG',  # 国债ETF
    ]
    
    run_monthly(trade, 1, '10:00')

def trade(context):
    context.epo.rebalance(context, g.etf_pool)
```

## 参数调优指南

| 参数 | 保守 | 平衡 | 激进 |
|------|------|------|------|
| shrinkage(w) | 0.8 | 0.5 | 0.2 |
| lookback | 240 | 120 | 60 |
| lambda_ | 20 | 10 | 5 |

- w越大：越接近等权，越保守
- w越小：越依赖历史数据，越激进
- lookback越长：越稳定，但对近期变化反应慢

## 与其他机制组合

```
ETF轮动 + EPO权重优化：
1. 动量选出候选ETF（前3-5只）
2. EPO计算最优权重（替代等权）
3. RSRS择时决定是否持仓
```

## 适用策略

- ✅ ETF多资产组合（宽基+行业+商品+债券）
- ✅ 全天候策略（股债商品配置）
- ✅ 低相关性ETF组合
- ⚠️ 单一资产类别效果有限
- ⚠️ 持仓数量<3只时退化为等权

## 待调研方向

1. **Ledoit-Wolf收缩**：更严格的协方差矩阵收缩方法
2. **Black-Litterman模型**：结合主观观点的组合优化
3. **动态收缩系数**：根据市场波动率动态调整w
4. **因子中性化**：在行业/风格因子中性化后再优化
