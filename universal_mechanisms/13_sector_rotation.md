# 行业/主题动量轮动 (Sector Rotation)

## 概述

基于行业/主题指数动量，在强势行业间轮动切换。

## 机制说明

1. **计算各行业/主题指数动量**
2. **排序选择动量最强的N个行业**
3. **动量超过阈值时切换**
4. **结合择时信号判断是否轮动**

## 效果验证

| 策略 | 效果 | 说明 |
|------|------|------|
| 行业ETF轮动+择时 | 年化35%，回撤16% | 经典轮动策略 |
| 核心资产轮动增强版 | 年化40%+ | 增强版本 |

## 代码样例

```python
# sector_rotation.py
import numpy as np
import pandas as pd

class SectorRotation:
    """行业轮动"""
    
    def __init__(self, sectors=None, momentum_period=20, top_n=3):
        """
        参数:
        sectors: 行业ETF列表
        momentum_period: 动量计算周期
        top_n: 保留前N个行业
        """
        self.momentum_period = momentum_period
        self.top_n = top_n
        
        # 默认行业ETF
        if sectors is None:
            self.sectors = {
                '510310.XSHG': '沪深300ETF',
                '159915.XSHE': '创业板ETF',
                '512880.XSHG': '证券ETF',
                '512660.XSHG': '军工ETF',
                '512800.XSHG': '银行ETF',
                '512010.XSHG': '医药ETF',
                '515050.XSHG': '5GETF',
                '512760.XSHG': '芯片ETF',
            }
        else:
            self.sectors = sectors
    
    def calculate_momentum(self, end_date):
        """计算各行业动量"""
        momentum = {}
        
        for sector_code, sector_name in self.sectors.items():
            try:
                prices = get_price(sector_code, 
                                 end_date=end_date, 
                                 fields='close', 
                                 count=self.momentum_period + 1, 
                                 panel=False)
                
                if prices is None or len(prices) < self.momentum_period:
                    continue
                
                pchg = (prices['close'].iloc[-1] / prices['close'].iloc[0]) - 1
                momentum[sector_code] = {
                    'momentum': pchg,
                    'name': sector_name
                }
            except:
                continue
        
        return momentum
    
    def get_top_sectors(self, end_date):
        """获取动量最强的行业"""
        momentum = self.calculate_momentum(end_date)
        
        if len(momentum) == 0:
            return []
        
        # 排序
        sorted_sectors = sorted(momentum.items(), 
                               key=lambda x: x[1]['momentum'], 
                               reverse=True)
        
        return sorted_sectors[:self.top_n]
    
    def should_rotate(self, context, threshold=0.05):
        """
        判断是否应该轮动
        当前最强行业动量超过阈值时轮动
        """
        top_sectors = self.get_top_sectors(context.previous_date)
        
        if len(top_sectors) == 0:
            return False, []
        
        # 当前最强
        strongest = top_sectors[0]
        strongest_momentum = strongest[1]['momentum']
        
        # 检查是否持仓了非最强行业
        if context.portfolio.positions:
            held_sectors = list(context.portfolio.positions.keys())
            
            # 如果持仓的不是最强，且最强动量超过阈值
            if held_sectors and strongest[0] not in held_sectors:
                if strongest_momentum > threshold:
                    return True, top_sectors
        
        return False, top_sectors
    
    def get_rotation_signal(self, context):
        """获取轮动信号"""
        top_sectors = self.get_top_sectors(context.previous_date)
        
        if len(top_sectors) == 0:
            return 'HOLD', None
        
        strongest = top_sectors[0]
        
        # 动量大于0认为是多头信号
        if strongest[1]['momentum'] > 0:
            return 'BUY', strongest[0]
        
        return 'HOLD', None


# 使用示例
def initialize(context):
    context.sector_rot = SectorRotation(momentum_period=20, top_n=3)

def handle_data(context):
    # 检查轮动信号
    should_rotate, top_sectors = context.sector_rot.should_rotate(
        context, threshold=0.05
    )
    
    if should_rotate:
        # 清仓
        for stock in context.portfolio.positions:
            order_target_value(stock, 0)
        
        # 买入最强行业
        if top_sectors:
            cash = context.portfolio.available_cash
            order_target_value(top_sectors[0][0], cash)
            log.info(f"轮动到: {top_sectors[0][1]['name']}")
    
    # 或者使用简单的动量信号
    signal, sector = context.sector_rot.get_rotation_signal(context)
    
    if signal == 'BUY':
        log.info(f"买入信号: {sector}")
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| sectors | 见代码 | 行业ETF字典 |
| momentum_period | 20 | 动量计算周期 |
| top_n | 3 | 保留前N个行业 |
| threshold | 0.05 | 轮动阈值 |

## 适用策略

- ✅ ETF轮动策略
- ✅ 行业增强策略
- ✅ 主题投机

## 注意事项

1. 动量周期需要根据策略调整
2. 轮动阈值避免频繁切换
3. 建议结合择时信号使用
