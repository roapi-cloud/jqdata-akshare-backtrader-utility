# emotion_switch.py
# 情绪开关 - 涨停家数判断整体情绪

def check_emotion(context, threshold=30):
    """
    情绪检查通用函数
    
    参数:
    context: 聚宽context对象
    threshold: 涨停家数阈值，低于此值时停止开仓
    
    返回:
    (是否可交易, 涨停家数)
    """
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
    
    def get_zt_count(self, context):
        """获取涨停家数"""
        _, zt_count = self.check(context)
        return zt_count


# 使用示例
def initialize(context):
    context.emotion_switch = EmotionSwitch(threshold=30)

def handle_data(context):
    # 情绪检查
    can_trade, zt_count = context.emotion_switch.check(context)
    
    log.info(f"涨停家数: {zt_count}, 是否可交易: {can_trade}")
    
    if not can_trade:
        # 情绪过低，清仓
        for stock in context.portfolio.positions:
            order_target_value(stock, 0)
        return
    
    # 正常交易逻辑
    pass
