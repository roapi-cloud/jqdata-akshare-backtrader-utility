# FED估值指标 + 格雷厄姆指数

## 概述

FED模型（美联储模型）和格雷厄姆指数是判断A股大周期估值顶底的核心宏观指标。两者结合可以识别市场是否处于系统性低估或高估区间，是长线策略仓位管理的重要依据。

来源：聚宽策略 `97 大周期顶底判断：FED指标+格雷厄姆指数一次搞定.ipynb`

## 机制说明

### FED模型
- 公式：`FED = 沪深300盈利收益率(1/PE) - 10年期国债收益率`
- 逻辑：当股票盈利收益率高于无风险利率时，股票相对债券更有吸引力
- FED > 0：股票低估，值越大越低估
- FED < 0：股票高估，值越小越高估

### 格雷厄姆指数
- 公式：`Graham = (1/PE_300) / 国债收益率`
- 逻辑：沪深300盈利收益率与无风险利率的比值
- Graham > 1.5：股票明显低估
- Graham < 1.0：股票高估

### 实测数据（2024-12-20）
| 指标 | 数值 | 判断 |
|------|------|------|
| 沪深300 PE | 19.02 | - |
| 10年国债收益率 | 1.73% | 历史低位 |
| FED值 | 3.26% | 极度低估 |
| 格雷厄姆指数 | 2.63 | 极度低估 |

## 阈值划分

| FED值 | 格雷厄姆值 | 市场状态 | 仓位建议 | 操作建议 |
|-------|-----------|----------|----------|----------|
| **>3%** | >2.5 | 极度低估 | 120% | 满仓+杠杆 |
| **>2%** | >2.0 | 极低估 | 100% | 积极建仓 |
| **1-2%** | 1.5-2.0 | 低估 | 80% | 正常配置 |
| **0-1%** | 1.0-1.5 | 合理 | 60% | 维持仓位 |
| **-1~0%** | 0.8-1.0 | 轻微高估 | 40% | 减仓防御 |
| **<-1%** | <0.8 | 高估 | 20% | 大幅减仓 |

## 适用时机

- 大盘系统性底部识别（2018年底、2022年底、2024年初）
- 长线策略仓位基准设定
- 与短线择时（RSRS）结合，形成"宏观底仓+技术择时"双层框架
- 不适合用于短线交易（信号变化极慢，月度/季度级别）

## 代码样例

```python
# fed_valuation.py
import numpy as np
import pandas as pd
from jqdata import *

class FEDValuation:
    """FED估值指标 + 格雷厄姆指数"""
    
    def __init__(self, index='000300.XSHG'):
        self.index = index
    
    def get_bond_yield(self, date=None):
        """
        获取10年期国债收益率
        聚宽数据：macro.MAC_BOND_YIELD
        返回百分比形式（如 2.5 表示 2.5%）
        """
        try:
            df = macro.run_query(
                query(macro.MAC_BOND_YIELD)
                .filter(macro.MAC_BOND_YIELD.stat_year == str(date)[:4])
                .order_by(macro.MAC_BOND_YIELD.stat_date.desc())
                .limit(1)
            )
            if len(df) > 0:
                return float(df['yield_10'].iloc[0])
        except:
            pass
        return 2.5  # 默认值
    
    def get_index_pe(self, date=None):
        """获取沪深300 PE"""
        try:
            df = get_fundamentals(
                query(valuation.pe_ratio)
                .filter(valuation.code == self.index),
                date=date
            )
            if len(df) > 0:
                return float(df['pe_ratio'].iloc[0])
        except:
            pass
        return 15.0  # 默认值
    
    def calculate_fed(self, pe, bond_yield):
        """
        计算FED值
        FED = 盈利收益率 - 国债收益率
        盈利收益率 = 100/PE (百分比形式)
        """
        if pe <= 0:
            return 0
        earnings_yield = 100.0 / pe  # 转为百分比
        return earnings_yield - bond_yield
    
    def calculate_graham(self, pe, bond_yield):
        """
        计算格雷厄姆指数
        Graham = (1/PE) / (bond_yield/100)
        即盈利收益率 / 国债收益率（均为小数形式）
        """
        if pe <= 0 or bond_yield <= 0:
            return 1.0
        earnings_yield = 1.0 / pe
        bond_rate = bond_yield / 100.0
        return earnings_yield / bond_rate
    
    def get_valuation_state(self, context):
        """获取估值状态"""
        date = context.previous_date
        pe = self.get_index_pe(date)
        bond_yield = self.get_bond_yield(date)
        
        fed = self.calculate_fed(pe, bond_yield)
        graham = self.calculate_graham(pe, bond_yield)
        
        # 判断状态
        if fed > 3 and graham > 2.5:
            state, ratio = '极度低估', 1.0
        elif fed > 2 and graham > 2.0:
            state, ratio = '极低估', 1.0
        elif fed > 1 and graham > 1.5:
            state, ratio = '低估', 0.8
        elif fed > 0 and graham > 1.0:
            state, ratio = '合理', 0.6
        elif fed > -1 and graham > 0.8:
            state, ratio = '轻微高估', 0.4
        else:
            state, ratio = '高估', 0.2
        
        return {
            'pe': pe,
            'bond_yield': bond_yield,
            'fed': fed,
            'graham': graham,
            'state': state,
            'position_ratio': ratio
        }
    
    def get_position_ratio(self, context):
        """获取建议仓位比例"""
        result = self.get_valuation_state(context)
        return result['position_ratio']


# 使用示例（月度/季度运行）
def initialize(context):
    context.fed_val = FEDValuation(index='000300.XSHG')
    run_monthly(check_valuation, 1, '09:30')

def check_valuation(context):
    result = context.fed_val.get_valuation_state(context)
    log.info(f"FED估值: PE={result['pe']:.1f}, 国债={result['bond_yield']:.2f}%, "
             f"FED={result['fed']:.2f}%, Graham={result['graham']:.2f}, "
             f"状态={result['state']}, 建议仓位={result['position_ratio']*100:.0f}%")
    
    # 根据估值调整基础仓位
    g.base_position_ratio = result['position_ratio']
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| index | 000300.XSHG | 参考指数（沪深300） |
| FED极低估阈值 | >2% | 积极建仓信号 |
| Graham低估阈值 | >1.5 | 低估信号 |

## 与其他机制组合

```
宏观底仓框架：
FED估值（月度）→ 确定基础仓位比例（20%-100%）
    ↓
RSRS择时（日度）→ 在基础仓位上做±20%调整
    ↓
情绪开关（日度）→ 极端情绪时强制减仓
```

## 适用策略

- ✅ RFScore长线策略（基础仓位参考）
- ✅ ETF轮动（空仓/满仓决策）
- ✅ 价值投资策略（建仓时机）
- ✅ 股债平衡策略（股债比例调整）
- ⚠️ 短线策略（不适用，信号太慢）

## 注意事项

1. 国债收益率数据需要从宏观数据库获取，聚宽提供 `macro.MAC_BOND_YIELD`
2. 2024年国债收益率历史低位（约1.7%），导致FED和Graham指数偏高，需结合绝对估值判断
3. 该指标是大周期指标，不适合频繁交易，建议月度或季度检查一次
4. 与市场宽度、RSRS等短期指标结合使用效果更佳
