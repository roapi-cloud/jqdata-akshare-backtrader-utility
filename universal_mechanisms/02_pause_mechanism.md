# 停手机制 (Pause Mechanism)

## 概述

连续亏损N笔后暂停交易M天，避免情绪失控连续亏损。是高通用性的风控机制。

## 机制说明

1. **记录连续亏损笔数**
2. **达到阈值后暂停交易N天**
3. **帮助交易者冷静，避免情绪化交易**

## 最优参数

| 规则 | 回撤改善 | 卡玛提升 | 收益影响 | 适用场景 |
|------|---------|---------|---------|----------|
| 连亏3停3（推荐） | -28.4% | +68.6% | +20.7% | 通用 |
| 近10笔转负半仓 | -23% | +29% | -2% | 高频策略 |
| 连亏2停2 | -35% | +45% | -15% | 激进策略 |

## 代码样例

```python
# pause_manager.py

class PauseManager:
    """停手机制管理器"""
    
    def __init__(self, loss_trigger=3, pause_days=3):
        self.loss_trigger = loss_trigger
        self.pause_days = pause_days
        self.consecutive_loss = 0
        self.remaining_pause = 0
    
    def record_trade(self, pnl):
        """记录交易，返回是否可交易"""
        if self.remaining_pause > 0:
            self.remaining_pause -= 1
            return False
        
        if pnl < 0:
            self.consecutive_loss += 1
        else:
            self.consecutive_loss = 0
        
        if self.consecutive_loss >= self.loss_trigger:
            self.remaining_pause = self.pause_days
            self.consecutive_loss = 0
            return False
        
        return True
    
    def can_trade(self):
        """是否可交易"""
        return self.remaining_pause == 0
    
    def get_status(self):
        """获取状态信息"""
        return {
            'consecutive_loss': self.consecutive_loss,
            'remaining_pause': self.remaining_pause,
            'can_trade': self.can_trade()
        }
    
    def reset(self):
        """重置状态"""
        self.consecutive_loss = 0
        self.remaining_pause = 0


# 使用示例
def initialize(context):
    # 推荐参数：连亏3笔停3天
    context.pause_mgr = PauseManager(loss_trigger=3, pause_days=3)

def handle_data(context):
    if not context.pause_mgr.can_trade():
        log.info(f"停机中，剩余 {context.pause_mgr.remaining_pause} 天")
        return
    
    # 正常交易逻辑
    pass


def after_trading_end(context):
    # 计算今日交易盈亏
    total_pnl = 0
    # ... 根据实际交易计算盈亏
    
    context.pause_mgr.record_trade(total_pnl)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| loss_trigger | 3 | 连续亏损触发次数 |
| pause_days | 3 | 暂停交易天数 |

## 适用策略

- ✅ 所有短线策略（首板、二板、弱转强）
- ✅ 机会仓组合
- ⚠️ 长线策略（RFScore）慎用
