"""
股票池过滤器默认配置
"""
from typing import Dict, Any


DEFAULT_FILTER_CONFIG: Dict[str, Dict[str, Any]] = {
    'st': {
        'enabled': True,
        'check_name': True,  # 是否额外检查名称中ST/*/退
    },
    'paused': {
        'enabled': True,
        'paused_N': 1,      # 查询当天
        'threshold': None,  # 不使用停牌天数阈值
    },
    'new_stock': {
        'enabled': True,
        'min_days': 250,    # 默认上市250天以上
    },
    'limitup': {
        'enabled': True,    # 买入时默认过滤涨停
        'keep_positions': True,  # 保留持仓
    },
    'limitdown': {
        'enabled': False,   # 默认不启用（边界复杂）
        'keep_positions': True,
    },
    'kcbj': {
        'enabled': True,    # 默认过滤科创/北交所
    },
}


def get_minimal_config() -> Dict[str, Dict[str, Any]]:
    """获取最小配置（仅启用ST、停牌、次新、科创北交所）"""
    return {
        'st': {'enabled': True, 'check_name': True},
        'paused': {'enabled': True},
        'new_stock': {'enabled': True, 'min_days': 250},
        'kcbj': {'enabled': True},
    }


if __name__ == "__main__":
    print("默认配置:")
    for k, v in DEFAULT_FILTER_CONFIG.items():
        print(f"  {k}: {v}")