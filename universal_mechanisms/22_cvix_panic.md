# C-VIX恐慌指数 (波动率指标)

## 概述

C-VIX是中国版VIX，用于衡量市场恐慌程度。恐慌程度高时往往是市场底部信号。

## 机制说明

C-VIX = 前两月期权隐含波动率加权平均

## 阈值划分

| C-VIX值 | 状态 | 市场情绪 |
|---------|------|----------|
| **<15** | 低波动 | 市场平静 |
| **15-25** | 正常 | 情绪稳定 |
| **25-35** | 高波动 | 恐慌加剧 |
| **>35** | 极端恐慌 | 底部特征 |

## 代码样例

```python
# cvix_panic.py
import numpy as np

class CVIXIndicator:
    """C-VIX恐慌指数"""
    
    def __init__(self):
        self.data_source_needed = True  # 需要期权数据源
    
    def get_cvix(self, options_data):
        """
        计算C-VIX
        options_data: 期权隐含波动率数据
        """
        # 前两月期权隐含波动率加权平均
        cvix = options_data['iv'].mean() * 100
        return cvix
    
    def get_signal(self, cvix):
        """获取信号"""
        if cvix < 15:
            return 'CALM', '低波动,市场平静'
        elif cvix < 25:
            return 'NORMAL', '正常,情绪稳定'
        elif cvix < 35:
            return 'PANIC', '高波动,恐慌加剧'
        else:
            return 'EXTREME_PANIC', '极端恐慌,底部特征'


# 使用示例（需要期权数据源）
def initialize(context):
    context.cvix = CVIXIndicator()

def get_monthly_cvix(context):
    # 注意: C-VIX需要期权数据源
    # 以下为示例逻辑
    try:
        # 获取期权数据
        options_iv = get_option_implied_volatility()
        cvix = context.cvix.get_cvix(options_iv)
        
        signal, desc = context.cvix.get_signal(cvix)
        log.info(f"C-VIX: {cvix:.1f}, 信号: {desc}")
        
        return cvix, signal
    except:
        log.info("C-VIX数据不可用")
        return None, None
```

## 适用策略

- ✅ 仓位调整辅助
- ✅ 极端市场识别
- ⚠️ 需要期权数据源
