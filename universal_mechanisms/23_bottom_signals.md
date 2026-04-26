# 市场底部特征综合判断 (9项信号)

## 概述

通过9个维度的底部信号综合打分，识别极端市场底部。单一指标容易误判，多信号共振才是真底部。

来源：聚宽策略 `36 研究 市场底部特征研究.ipynb`，结合 `97 大周期顶底判断` 整合而成。

## 9个底部信号详解

| 编号 | 信号 | 底部阈值 | 逻辑说明 |
|------|------|---------|---------|
| 1 | 市场宽度 | <15% | 极少股票站上均线，市场极度悲观 |
| 2 | FED值 | >2% | 股票盈利收益率远超国债，极度低估 |
| 3 | 格雷厄姆指数 | >2.0 | 股票相对债券极度便宜 |
| 4 | C-VIX恐慌指数 | >30 | 市场恐慌情绪极端 |
| 5 | NH-NL净新高占比 | <-30% | 创新低股票远多于创新高 |
| 6 | 拥挤率 | <15% | 资金极度分散，无热点 |
| 7 | 两市成交额 | <5000亿 | 市场极度萎缩，无人交易 |
| 8 | 破净占比 | >15% | 大量股票跌破净资产 |
| 9 | 涨停家数 | <20家 | 情绪极度低迷 |

## 历史底部验证

| 时间 | 满足项数 | 底部类型 | 后续表现 |
|------|---------|---------|---------|
| 2018-10 | 7/9 | 极端底部 | 6个月+50% |
| 2022-10 | 6/9 | 强底部 | 3个月+20% |
| 2024-02 | 5/9 | 中等底部 | 1个月+15% |

## 置信度划分

| 满足项数 | 底部置信度 | 仓位建议 | 操作建议 |
|----------|------------|----------|----------|
| **≥7项** | 极高置信 | 100% | 满仓，可考虑杠杆 |
| **5-6项** | 高置信 | 80% | 积极加仓 |
| **3-4项** | 中等置信 | 50% | 试探性建仓 |
| **1-2项** | 低置信 | 30% | 观望为主 |
| **0项** | 无信号 | 20% | 防御 |

## 适用时机

- 大盘连续下跌后的底部确认（不适合用于日常交易）
- 与FED估值结合，形成"估值底+情绪底"双重确认
- 月度/季度级别的战略仓位决策
- 不适合用于短线择时

## 代码样例

```python
# bottom_signals.py
import numpy as np
import pandas as pd
from jqdata import *

class BottomSignalsChecker:
    """市场底部9项信号综合检查器"""
    
    def __init__(self, index='000300.XSHG'):
        self.index = index
    
    # ---- 信号1：市场宽度 ----
    def check_breadth(self, context, threshold=0.15):
        """市场宽度：站上MA20的股票占比"""
        try:
            stocks = get_index_stocks('000300.XSHG')[:300]
            current_data = get_current_data()
            stocks = [s for s in stocks if not current_data[s].is_st and not current_data[s].paused]
            
            prices = get_price(stocks, end_date=context.previous_date,
                             fields='close', count=21, panel=False)
            price_df = prices.pivot(index='time', columns='code', values='close')
            ma20 = price_df.iloc[-20:].mean()
            current = price_df.iloc[-1]
            breadth = (current > ma20).mean()
            return breadth, breadth < threshold
        except:
            return 0.5, False
    
    # ---- 信号2+3：FED + 格雷厄姆 ----
    def check_fed_graham(self, context, fed_threshold=2.0, graham_threshold=2.0):
        """FED值和格雷厄姆指数"""
        try:
            df = get_fundamentals(
                query(valuation.pe_ratio).filter(valuation.code == '000300.XSHG'),
                date=context.previous_date
            )
            pe = float(df['pe_ratio'].iloc[0]) if len(df) > 0 else 15.0
            bond_yield = 2.5  # 简化处理，实际应从宏观数据获取
            
            fed = (100.0 / pe) - bond_yield
            graham = (1.0 / pe) / (bond_yield / 100.0)
            return fed, graham, (fed > fed_threshold), (graham > graham_threshold)
        except:
            return 0, 1.0, False, False
    
    # ---- 信号4：C-VIX恐慌指数 ----
    def check_cvix(self, context, threshold=30):
        """C-VIX：全市场波动率代理指标"""
        try:
            stocks = get_index_stocks('000300.XSHG')[:100]
            prices = get_price(stocks, end_date=context.previous_date,
                             fields='close', count=20, panel=False)
            price_df = prices.pivot(index='time', columns='code', values='close')
            returns = price_df.pct_change().dropna()
            # 用收益率标准差×100作为VIX代理
            cvix = returns.std().mean() * 100 * np.sqrt(252)
            return cvix, cvix > threshold
        except:
            return 20, False
    
    # ---- 信号5：NH-NL净新高占比 ----
    def check_nhnl(self, context, threshold=-0.30):
        """NH-NL：52周新高-新低净占比"""
        try:
            stocks = get_all_securities('stock').index.tolist()[:1000]
            current_data = get_current_data()
            stocks = [s for s in stocks if not current_data[s].is_st and not current_data[s].paused
                     and s[:2] not in ['68'] and s[0] not in ['4', '8']][:500]
            
            prices = get_price(stocks, end_date=context.previous_date,
                             fields='close', count=252, panel=False)
            price_df = prices.pivot(index='time', columns='code', values='close')
            
            current = price_df.iloc[-1]
            high_52w = price_df.max()
            low_52w = price_df.min()
            
            new_high = (current >= high_52w * 0.98).sum()
            new_low = (current <= low_52w * 1.02).sum()
            total = len(stocks)
            
            nhnl_pct = (new_high - new_low) / total
            return nhnl_pct, nhnl_pct < threshold
        except:
            return 0, False
    
    # ---- 信号6：拥挤率 ----
    def check_crowding(self, context, threshold=0.15):
        """拥挤率：成交额前5%占比"""
        try:
            stocks = get_all_securities('stock').index.tolist()[:2000]
            amounts = get_price(stocks, end_date=context.previous_date,
                              fields='money', count=1, panel=False)
            amount_series = amounts.groupby('code')['money'].last()
            top5_pct = amount_series.nlargest(int(len(amount_series) * 0.05)).sum()
            total = amount_series.sum()
            crowding = top5_pct / total if total > 0 else 0.3
            return crowding, crowding < threshold
        except:
            return 0.3, False
    
    # ---- 信号7：两市成交额 ----
    def check_volume(self, context, threshold=5000e8):
        """两市成交额是否低于阈值（5000亿）"""
        try:
            df = get_price('000001.XSHG', end_date=context.previous_date,
                          fields='money', count=1, panel=False)
            sh_vol = float(df['money'].iloc[-1]) if len(df) > 0 else 1e12
            # 深市约为沪市的0.8倍
            total_vol = sh_vol * 1.8
            return total_vol, total_vol < threshold
        except:
            return 1e12, False
    
    # ---- 信号8：破净占比 ----
    def check_pb_below_1(self, context, threshold=0.15):
        """破净占比：PB<1的股票占比"""
        try:
            df = get_fundamentals(
                query(valuation.code, valuation.pb_ratio)
                .filter(valuation.pb_ratio > 0)
                .limit(2000),
                date=context.previous_date
            )
            below_1 = (df['pb_ratio'] < 1).mean()
            return below_1, below_1 > threshold
        except:
            return 0.05, False
    
    # ---- 信号9：涨停家数 ----
    def check_limit_up_count(self, context, threshold=20):
        """涨停家数是否极少"""
        try:
            stocks = get_all_securities('stock').index.tolist()
            stocks = [s for s in stocks if s[:2] not in ['68'] and s[0] not in ['4', '8']][:3000]
            current_data = get_current_data()
            
            prices = get_price(stocks, end_date=context.previous_date,
                             fields=['close', 'high_limit'], count=1, panel=False)
            zt_count = len(prices[prices['close'] >= prices['high_limit'] * 0.99])
            return zt_count, zt_count < threshold
        except:
            return 50, False
    
    def check_all(self, context):
        """检查所有9项信号，返回满足数量和详情"""
        breadth, s1 = self.check_breadth(context)
        fed, graham, s2, s3 = self.check_fed_graham(context)
        cvix, s4 = self.check_cvix(context)
        nhnl, s5 = self.check_nhnl(context)
        crowding, s6 = self.check_crowding(context)
        volume, s7 = self.check_volume(context)
        pb_below, s8 = self.check_pb_below_1(context)
        zt_count, s9 = self.check_limit_up_count(context)
        
        signals = [s1, s2, s3, s4, s5, s6, s7, s8, s9]
        satisfied = sum(signals)
        
        details = {
            '市场宽度': f'{breadth:.1%} (底部<15%): {"✅" if s1 else "❌"}',
            'FED值': f'{fed:.2f}% (底部>2%): {"✅" if s2 else "❌"}',
            '格雷厄姆': f'{graham:.2f} (底部>2.0): {"✅" if s3 else "❌"}',
            'C-VIX': f'{cvix:.1f} (底部>30): {"✅" if s4 else "❌"}',
            'NH-NL': f'{nhnl:.1%} (底部<-30%): {"✅" if s5 else "❌"}',
            '拥挤率': f'{crowding:.1%} (底部<15%): {"✅" if s6 else "❌"}',
            '成交额': f'{volume/1e8:.0f}亿 (底部<5000亿): {"✅" if s7 else "❌"}',
            '破净占比': f'{pb_below:.1%} (底部>15%): {"✅" if s8 else "❌"}',
            '涨停家数': f'{zt_count}家 (底部<20家): {"✅" if s9 else "❌"}',
        }
        
        return satisfied, details
    
    def get_signal(self, context):
        """获取底部信号和建议仓位"""
        satisfied, details = self.check_all(context)
        
        if satisfied >= 7:
            signal, ratio, desc = 'EXTREME_BOTTOM', 1.0, '极高置信底部，满仓'
        elif satisfied >= 5:
            signal, ratio, desc = 'HIGH_BOTTOM', 0.8, '高置信底部，积极加仓'
        elif satisfied >= 3:
            signal, ratio, desc = 'MEDIUM_BOTTOM', 0.5, '中等置信，试探建仓'
        elif satisfied >= 1:
            signal, ratio, desc = 'WEAK_BOTTOM', 0.3, '弱信号，观望为主'
        else:
            signal, ratio, desc = 'NOT_BOTTOM', 0.2, '无底部信号，防御'
        
        return signal, ratio, satisfied, details


# 使用示例（月度运行）
def initialize(context):
    context.bottom_checker = BottomSignalsChecker()
    run_monthly(monthly_bottom_check, 1, '09:30')

def monthly_bottom_check(context):
    signal, ratio, satisfied, details = context.bottom_checker.get_signal(context)
    
    log.info(f"底部信号: {satisfied}/9项满足 → {signal}")
    for k, v in details.items():
        log.info(f"  {k}: {v}")
    
    # 调整基础仓位
    g.macro_position_ratio = ratio
    log.info(f"宏观仓位设定: {ratio*100:.0f}%")
```

## 与其他机制组合

```
底部确认流程：
月度检查底部信号（9项）
    ↓ 满足≥5项
FED估值确认（PE/国债）
    ↓ FED>2%
RSRS择时确认（日线）
    ↓ RSRS>0.7
执行建仓
```

## 适用策略

- ✅ 极端底部识别（2018年底、2022年底类型）
- ✅ 战略仓位决策（月度/季度级别）
- ✅ 与FED估值、RSRS择时组合使用
- ⚠️ 不适合日常交易，信号出现频率极低（每2-3年一次）

## 注意事项

1. 9项信号不需要全部满足，5项以上即可认为是较强底部
2. 历史上真正的大底（2018年底、2022年底）通常满足6-8项
3. 部分信号（C-VIX、NH-NL）计算较复杂，可简化为3-5项核心信号
4. 底部信号出现后，市场可能还会继续下跌，需要分批建仓
