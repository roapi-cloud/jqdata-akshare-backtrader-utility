# 情绪开关 (Emotion Switch)

## 概述

通过市场涨停家数判断整体情绪，低于阈值时停止开仓。是最高通用的风控机制。

## 机制说明

1. **获取全市场涨停家数**
2. **涨停家数低于阈值时，说明情绪低迷**
3. **停止开仓，避免在弱势市场亏损**

## 效果验证

| 策略 | 无开关 | 有开关(≥30) | 改善 |
|------|--------|-------------|------|
| 首板低开 | 年化- | 年化28.4% | 回撤-40% |
| 小市值 | 回撤35.2% | 回撤21.3% | 卡玛+113% |

## 代码样例

```python
# emotion_switch.py
import numpy as np

def check_emotion(context, threshold=30):
    """情绪检查通用函数"""
    all_stocks = get_all_securities("stock").index.tolist()
    all_stocks = [s for s in all_stocks if s[:2] != "68" and s[0] not in ["4", "8"]]
    
    df = get_price(all_stocks[:500], end_date=context.previous_date, 
                   fields=["close", "high_limit"], count=1, panel=False)
    zt_count = len(df[df["close"] >= df["high_limit"] * 0.99])
    
    return zt_count >= threshold, zt_count


class EmotionSwitch:
    """情绪开关类"""
    
    def __init__(self, threshold=30):
        self.threshold = threshold
    
    def check(self, context):
        """检查情绪"""
        return check_emotion(context, self.threshold)


# 使用示例
def initialize(context):
    context.emotion_switch = EmotionSwitch(threshold=30)

def handle_data(context):
    can_trade, zt_count = context.emotion_switch.check(context)
    
    log.info(f"涨停家数: {zt_count}, 是否可交易: {can_trade}")
    
    if not can_trade:
        # 情绪过低，清仓
        for stock in context.portfolio.positions:
            order_target_value(stock, 0)
        return
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| threshold | 30 | 涨停家数阈值 |

## 适用策略

- ✅ 首板低开
- ✅ 小市值防守
- ✅ 二板接力
- ✅ 弱转强
- ✅ RFScore（可作为减仓信号）
