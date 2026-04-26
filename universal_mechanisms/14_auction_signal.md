# 集合竞价信号机制 (Auction Signal)

## 概述

利用集合竞价阶段的成交量/价格变化作为短线买入信号，是首板、二板等短线策略的核心机制。

## 机制说明

1. **获取集合竞价数据**：09:15-09:25的报价和成交
2. **计算竞价涨幅**：竞价价格/昨收盘 - 1
3. **过滤条件**：非涨停、非跌停、温和低开
4. **排序选择**：低开幅度适中的优先

## 效果验证

| 策略 | 效果 | 说明 |
|------|------|------|
| 集合竞价三合一 | 今年收益1067%，年化198% | 短线综合策略 |
| 一进二集合竞价策略 | 今年收益翻倍 | 二板接力 |
| 集合竞价摸奖策略 | 5个月收益239% | 高频策略 |

## 代码样例

```python
# auction_signal.py
import numpy as np
import pandas as pd

class AuctionSignal:
    """集合竞价信号"""
    
    def __init__(self, min_ratio=-0.03, max_ratio=0.095, 
                 target_ratio=-0.02, volume_min=0):
        """
        参数:
        min_ratio: 最低竞价涨幅（如-0.03表示跌停）
        max_ratio: 最高竞价涨幅（如0.095表示涨停）
        target_ratio: 目标竞价涨幅（如-0.02表示低开2%）
        volume_min: 最小竞价成交量
        """
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio
        self.target_ratio = target_ratio
        self.volume_min = volume_min
    
    def get_auction_data(self, stock, date):
        """获取集合竞价数据"""
        try:
            # 获取当日竞价数据
            auction_data = get_ticks(stock, date, count=1, 
                                    fields=['time', 'current', 'volume', 'money', 'a1_p'],
                                    skip=True, df=True)
            return auction_data
        except Exception as e:
            log.error(f"获取竞价数据失败 {stock}: {e}")
            return None
    
    def get_auction_signal(self, stock, date):
        """获取单只股票竞价信号"""
        try:
            # 获取昨日收盘价
            yesterday = (pd.Timestamp(date) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            prev_close = get_price(stock, end_date=yesterday, 
                                   fields='close', count=1)['close'].iloc[-1]
            
            # 获取当日竞价数据
            auction_data = get_ticks(stock, date, count=1, 
                                    fields=['time', 'current', 'volume'], 
                                    skip=True, df=True)
            
            if auction_data is None or len(auction_data) == 0:
                return None
            
            # 竞价价格
            auction_price = auction_data['current'].iloc[-1]
            auction_volume = auction_data['volume'].iloc[-1]
            
            # 计算竞价涨幅
            ratio = auction_price / prev_close - 1
            
            # 获取当前数据（判断是否涨停/停牌）
            current_data = get_current_data()
            if stock not in current_data:
                return None
            
            cd = current_data[stock]
            if cd.paused or cd.is_st:
                return None
            
            # 涨停判断
            if ratio >= cd.high_limit / prev_close - 1 - 0.001:
                return None  # 不追涨停
            
            return {
                'stock': stock,
                'auction_price': auction_price,
                'prev_close': prev_close,
                'ratio': ratio,
                'volume': auction_volume,
                'qualified': self.min_ratio <= ratio <= self.max_ratio
            }
        except Exception as e:
            return None
    
    def filter_auction_stocks(self, context, stocks):
        """过滤集合竞价符合条件的股票"""
        today = context.current_dt.strftime('%Y-%m-%d')
        qualified = []
        
        for stock in stocks:
            signal = self.get_auction_signal(stock, today)
            
            if signal is None or not signal['qualified']:
                continue
            
            # 竞价涨幅在目标区间
            if signal['ratio'] <= self.target_ratio:
                qualified.append(signal)
        
        # 按竞价涨幅排序（低开优先）
        qualified.sort(key=lambda x: x['ratio'])
        
        return qualified


# 弱转强信号
class WeakToStrongSignal:
    """弱转强信号（昨日涨停今日竞价强势）"""
    
    def __init__(self, yesterday_limit_up=True, today_min_ratio=0.02):
        """
        参数:
        yesterday_limit_up: 昨日是否涨停
        today_min_ratio: 今日竞价最小涨幅
        """
        self.yesterday_limit_up = yesterday_limit_up
        self.today_min_ratio = today_min_ratio
    
    def check_weak_to_strong(self, context, stock):
        """检查弱转强信号"""
        try:
            yesterday = context.previous_date.strftime('%Y-%m-%d')
            
            # 昨日涨停
            prev_data = get_price(stock, end_date=yesterday, 
                                 fields=['close', 'high_limit'], count=2, panel=False)
            
            if prev_data is None or len(prev_data) < 2:
                return False
            
            prev_close = prev_data['close'].iloc[-2]
            high_limit = prev_data['high_limit'].iloc[-2]
            
            # 昨日涨停（收盘价接近涨停价）
            if prev_close < high_limit * 0.99:
                return False
            
            # 今日竞价强势
            today = context.current_dt.strftime('%Y-%m-%d')
            auction_signal = get_ticks(stock, today, count=1, 
                                      fields=['current'], skip=True, df=True)
            
            if auction_signal is None or len(auction_signal) == 0:
                return False
            
            auction_price = auction_signal['current'].iloc[-1]
            ratio = auction_price / prev_close - 1
            
            # 竞价涨幅超过阈值，且未涨停
            if ratio >= self.today_min_ratio and ratio < 0.095:
                return True
            
            return False
        except:
            return False


# 使用示例
def initialize(context):
    context.auction = AuctionSignal(
        min_ratio=-0.03,
        max_ratio=0.095,
        target_ratio=-0.02
    )
    context.w2s = WeakToStrongSignal()

def handle_data(context):
    today = context.current_dt.strftime('%Y-%m-%d')
    
    # 竞价选股（首板低开）
    stocks = get_all_securities('stock')
    stocks = [s for s in stocks.index if s[:2] not in ['68', '4', '8']]
    
    auctionqualified = context.auction.filter_auction_stocks(context, stocks)
    
    log.info(f"集合竞价合格股票: {len(auctionqualified)}")
    
    # 选择前N只
    target_count = 3
    target_stocks = [s['stock'] for s in auctionqualified[:target_count]]
    
    # 买入
    cash = context.portfolio.available_cash
    for stock in target_stocks:
        order_target_value(stock, cash / len(target_stocks))
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| min_ratio | -0.03 | 最低竞价涨幅（跌停-3%） |
| max_ratio | 0.095 | 最高竞价涨幅（涨停9.5%） |
| target_ratio | -0.02 | 目标竞价涨幅（低开-2%） |
| volume_min | 0 | 最小竞价成交量 |

## 适用策略

- ✅ 首板低开（核心机制）
- ✅ 二板接力
- ✅ 弱转强
- ✅ 集合竞价摸奖

## 注意事项

1. 集合竞价数据获取可能失败，需要容错
2. 短线策略需要快速执行
3. 建议结合情绪指标使用
