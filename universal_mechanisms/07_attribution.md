# 归因分析框架 (Attribution)

## 概述

对策略收益进行归因分析，理解收益来源。市值、行业、风格等因子贡献。

## 代码样例

```python
# attribution.py
import pandas as pd
import numpy as np

class AttributionAnalyzer:
    """收益归因分析器"""
    
    def __init__(self):
        self.returns_history = []
        self.factor_values = {}
    
    def record_position(self, stock, weight, date):
        """记录持仓权重"""
        if date not in self.factor_values:
            self.factor_values[date] = {}
        self.factor_values[date][stock] = weight
    
    def calculate_returns(self, prices, start_date, end_date):
        """计算收益率"""
        p = prices[(prices.index >= start_date) & (prices.index <= end_date)]
        return (p.iloc[-1] / p.iloc[0]) - 1 if len(p) > 1 else 0
    
    def calculate_attribution(self, returns, factor_values):
        """
        收益归因分析
        
        参数:
        returns: 股票收益率Series
        factor_values: 因子值字典
        
        返回:
        归因结果字典
        """
        attribution = {}
        
        # 市值归因
        if 'market_cap' in factor_values:
            cap_returns = returns * factor_values['market_cap']
            attribution['market_cap'] = cap_returns.sum()
        
        # 行业归因
        if 'industry' in factor_values:
            industry_returns = {}
            for industry, stocks in factor_values['industry'].items():
                industry_ret = returns[stocks].mean()
                industry_returns[industry] = industry_ret * len(stocks) / len(returns)
            attribution['industry'] = industry_returns
        
        # 风格归因（动量、价值等）
        style_factors = ['momentum', 'value', 'quality', 'size']
        for factor in style_factors:
            if factor in factor_values:
                factor_ret = returns * factor_values[factor]
                attribution[factor] = factor_ret.sum()
        
        # 特异收益
        attribution['specific'] = returns.sum() - sum(attribution.values())
        
        return attribution
    
    def generate_report(self, context):
        """生成归因报告"""
        report = {
            'total_return': context.portfolio.total_value / context.portfolio.starting_cash - 1,
            'positions': {},
            'factor_contribution': {}
        }
        
        # 持仓信息
        for stock, pos in context.portfolio.positions.items():
            report['positions'][stock] = {
                'weight': pos.value / context.portfolio.total_value,
                'return': pos.price / pos.avg_cost - 1,
                'contribution': (pos.price / pos.avg_cost - 1) * (pos.value / context.portfolio.total_value)
            }
        
        return report


def simple_attribution_check(context):
    """简单的归因检查"""
    report = []
    
    for stock, pos in context.portfolio.positions.items():
        ret = pos.price / pos.avg_cost - 1
        weight = pos.value / context.portfolio.total_value
        contribution = ret * weight
        
        report.append({
            'stock': stock,
            'return': f"{ret*100:.2f}%",
            'weight': f"{weight*100:.2f}%",
            'contribution': f"{contribution*100:.2f}%"
        })
    
    report_df = pd.DataFrame(report)
    log.info(f"归因报告:\n{report_df}")


# 使用示例
def initialize(context):
    context.attribution = AttributionAnalyzer()

def after_trading_end(context):
    # 生成归因报告
    simple_attribution_check(context)
```

## 归因维度

1. **市值因子**：小市值vs大市值
2. **行业因子**：各行业贡献
3. **风格因子**：动量、价值、质量、规模
4. **特异收益**：无法解释的收益

## 适用策略

- ✅ 研究通用
- ✅ 策略评估
- ✅ 组合优化
