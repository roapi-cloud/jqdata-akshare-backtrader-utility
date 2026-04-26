# pause_manager.py
# 停手机制 - 连续亏损后暂停交易

class PauseManager:
    """停手机制管理器"""
    
    def __init__(self, loss_trigger=3, pause_days=3):
        """
        参数:
        loss_trigger: 连续亏损触发次数
        pause_days: 暂停交易天数
        """
        self.loss_trigger = loss_trigger
        self.pause_days = pause_days
        self.consecutive_loss = 0
        self.remaining_pause = 0
    
    def record_trade(self, pnl):
        """
        记录交易，返回是否可交易
        
        参数:
        pnl: 本笔交易盈亏（正数盈利，负数亏损）
        
        返回:
        bool: 是否可交易
        """
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
    
    # 或激进参数：连亏2笔停2天
    # context.pause_mgr = PauseManager(loss_trigger=2, pause_days=2)

def handle_data(context):
    # 检查是否可交易
    if not context.pause_mgr.can_trade():
        log.info(f"停机中，剩余 {context.pause_mgr.remaining_pause} 天")
        return
    
    # 正常交易逻辑
    pass


def after_trading_end(context):
    # 计算今日交易盈亏
    total_pnl = 0
    
    # 这里需要根据实际交易记录计算盈亏
    # 示例中简化处理
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        # 假设每笔交易盈亏可以从pos中获取
        # 这里需要根据实际情况计算
    
    # 记录交易结果
    context.pause_mgr.record_trade(total_pnl)
    
    # 打印状态
    status = context.pause_mgr.get_status()
    log.info(f"停机状态: {status}")
