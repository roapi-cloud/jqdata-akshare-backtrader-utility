# universal_risk_manager.py
# 通用风控管理器 - 整合所有风控机制

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, Any

# ==================== 情绪开关 ====================

class EmotionSwitch:
    """情绪开关"""
    
    def __init__(self, threshold=30):
        self.threshold = threshold
    
    def check(self, context) -> Tuple[bool, int]:
        """检查情绪，返回(是否可交易, 涨停家数)"""
        try:
            all_stocks = get_all_securities("stock").index.tolist()
            all_stocks = [s for s in all_stocks if s[:2] != "68" and s[0] not in ["4", "8"]]
            
            df = get_price(all_stocks[:500], end_date=context.previous_date, 
                          fields=["close", "high_limit"], count=1, panel=False)
            zt_count = len(df[df["close"] >= df["high_limit"] * 0.99])
            
            return zt_count >= self.threshold, zt_count
        except:
            return True, 999


# ==================== 停手机制 ====================

class PauseManager:
    """停手机制管理器"""
    
    def __init__(self, loss_trigger=3, pause_days=3):
        self.loss_trigger = loss_trigger
        self.pause_days = pause_days
        self.consecutive_loss = 0
        self.remaining_pause = 0
    
    def record_trade(self, pnl: float) -> bool:
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
    
    def can_trade(self) -> bool:
        """是否可交易"""
        return self.remaining_pause == 0


# ==================== 状态路由器 ====================

class StateRouter:
    """状态路由器"""
    
    def __init__(self, index='000300.XSHG', ma_period=20):
        self.index = index
        self.ma_period = ma_period
    
    def calculate_breadth(self, context) -> float:
        """计算市场广度"""
        try:
            hs300 = get_index_stocks(self.index)[:300]
            stocks = [s for s in hs300 if s in get_current_data()]
            
            prices = get_price(stocks, end_date=context.previous_date, 
                              fields='close', count=self.ma_period+1, panel=False)
            
            if prices is None:
                return 0.5
            
            price_df = prices.pivot(index='time', columns='code', values='close')
            ma = price_df.iloc[-self.ma_period:].mean()
            current = price_df.iloc[-1]
            
            return (current > ma).mean()
        except:
            return 0.5
    
    def calculate_sentiment(self, context) -> int:
        """计算情绪（涨停家数）"""
        try:
            all_stocks = get_all_securities("stock").index.tolist()
            all_stocks = [s for s in all_stocks if s[:2] != "68" and s[0] not in ["4", "8"]]
            
            df = get_price(all_stocks[:500], end_date=context.previous_date, 
                          fields=["close", "high_limit"], count=1, panel=False)
            return len(df[df["close"] >= df["high_limit"] * 0.99])
        except:
            return 50
    
    def route(self, context) -> Tuple[float, str]:
        """路由市场状态，返回(仓位比例, 状态名称)"""
        breadth = self.calculate_breadth(context)
        zt_count = self.calculate_sentiment(context)
        
        if breadth < 0.15 or zt_count < 30:
            return 0, "极弱停手"
        elif breadth < 0.25:
            return 0.3, "底部防守"
        elif breadth < 0.35:
            return 0.5, "震荡平衡"
        elif breadth >= 0.40 and zt_count >= 80:
            return 1.0, "强趋势"
        else:
            return 0.7, "趋势正常"


# ==================== 通用风控管理器 ====================

class UniversalRiskManager:
    """通用风控管理器 - 整合所有风控机制"""
    
    def __init__(self, 
                 emotion_threshold=30,
                 loss_trigger=3, 
                 pause_days=3,
                 enable_consistency=True,
                 enable_crowding=True,
                 enable_macro=True):
        """
        参数:
        emotion_threshold: 情绪开关阈值
        loss_trigger: 停机亏损触发次数
        pause_days: 停机天数
        enable_consistency: 是否启用一致性风控
        enable_crowding: 是否启用拥挤度检测
        enable_macro: 是否启用宏观事件过滤
        """
        self.emotion = EmotionSwitch(threshold=emotion_threshold)
        self.pause = PauseManager(loss_trigger=loss_trigger, pause_days=pause_days)
        self.state_router = StateRouter()
        
        # 一致性风控（可选）
        self.enable_consistency = enable_consistency
        if enable_consistency:
            from consistency_control import ConsistencyChecker
            self.consistency = ConsistencyChecker()
        
        # 拥挤度检测（可选）
        self.enable_crowding = enable_crowding
        if enable_crowding:
            from crowding_detection import CrowdingDetector
            self.crowding = CrowdingDetector()
        
        # 宏观事件过滤（可选）
        self.enable_macro = enable_macro
        if enable_macro:
            from macro_event_filter import MacroEventFilter
            self.macro = MacroEventFilter()
    
    def pre_trade_check(self, context) -> Tuple[bool, Any]:
        """
        交易前检查
        返回: (是否可交易, 详细信息)
        """
        info = {}
        
        # 1. 情绪检查
        emotion_ok, zt_count = self.emotion.check(context)
        info['zt_count'] = zt_count
        if not emotion_ok:
            return False, f"情绪过低({zt_count}家涨停)"
        
        # 2. 停机检查
        if not self.pause.can_trade():
            return False, "停机中"
        
        # 3. 状态路由
        position_ratio, state = self.state_router.route(context)
        info['state'] = state
        info['position_ratio'] = position_ratio
        
        if position_ratio == 0:
            return False, f"市场状态:{state}"
        
        # 4. 一致性检查
        if self.enable_consistency:
            try:
                consistency_state = self.consistency.check(context)
                info['consistency'] = consistency_state
                if consistency_state == 'OVER_CONSISTENT':
                    position_ratio *= 0.5
                    info['position_ratio'] = position_ratio
            except:
                pass
        
        # 5. 拥挤度检查
        if self.enable_crowding:
            try:
                if self.crowding.is_crowded(context):
                    position_ratio *= 0.5
                    info['position_ratio'] = position_ratio
                    info['crowded'] = True
            except:
                pass
        
        # 6. 宏观事件过滤
        if self.enable_macro:
            try:
                position_ratio *= self.macro.get_multiplier(context)
                info['position_ratio'] = position_ratio
            except:
                pass
        
        return True, info
    
    def record_trade(self, pnl: float):
        """记录交易结果"""
        self.pause.record_trade(pnl)
    
    def get_target_position(self, context, base_count=10) -> int:
        """获取目标持仓数量"""
        can_trade, info = self.pre_trade_check(context)
        
        if not can_trade:
            return 0
        
        position_ratio = info.get('position_ratio', 0.7)
        return max(int(base_count * position_ratio), 0)


# ==================== 基础股票池过滤 ====================

def get_base_universe(date) -> list:
    """获取基础股票池（所有策略通用）"""
    stocks = get_all_securities("stock", date).index.tolist()
    
    # 1. 排除科创板/北交所
    stocks = [s for s in stocks if s[:2] != "68" and s[0] not in ["4", "8"]]
    
    # 2. 排除ST
    try:
        is_st = get_extras("is_st", stocks, end_date=date, count=1).iloc[-1]
        stocks = is_st[is_st == False].index.tolist()
    except:
        pass
    
    # 3. 排除停牌
    try:
        paused = get_price(stocks, end_date=date, fields="paused", count=1, panel=False)
        paused = paused.pivot(index="time", columns="code", values="paused").iloc[-1]
        stocks = paused[paused == 0].index.tolist()
    except:
        pass
    
    # 4. 排除次新股（180天）
    try:
        from datetime import timedelta
        all_stocks = get_all_securities("stock", date)
        stocks = [s for s in stocks 
                  if date - all_stocks.loc[s, "start_date"] > timedelta(days=180)]
    except:
        pass
    
    return stocks


def filter_buyable(context, stocks: list) -> list:
    """过滤可买入股票"""
    current_data = get_current_data()
    buyable = []
    
    for stock in stocks:
        if stock not in current_data:
            continue
        
        cd = current_data[stock]
        if cd.paused or cd.is_st:
            continue
        
        if "ST" in (cd.name or "") or "*" in (cd.name or ""):
            continue
        
        # 不追涨停
        try:
            if cd.last_price >= cd.high_limit * 0.995:
                continue
        except:
            pass
        
        buyable.append(stock)
    
    return buyable


# ==================== 仓位管理 ====================

def equal_weight_position(context, stocks: list):
    """等权分配仓位"""
    if len(stocks) == 0:
        return
    
    target_value = context.portfolio.total_value / len(stocks)
    for stock in stocks:
        order_target_value(stock, target_value)


def dynamic_position(context, base_hold_num=10) -> int:
    """动态调整持仓数量"""
    risk_mgr = UniversalRiskManager()
    return risk_mgr.get_target_position(context, base_hold_num)
