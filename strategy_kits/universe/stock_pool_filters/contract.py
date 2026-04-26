"""
股票池过滤器数据契约
定义统一输入输出接口，确保所有过滤器可组合使用
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import date


@dataclass
class FilterInput:
    """过滤器统一输入"""
    base_universe: List[str]  # 基础股票池（股票代码列表）
    date: date                # 过滤日期
    config: Dict[str, Any] = field(default_factory=dict)  # 过滤配置参数
    positions: Optional[List[str]] = None  # 当前持仓股票列表（涨停/跌停过滤用）


@dataclass
class FilterOutput:
    """过滤器统一输出"""
    filtered_universe: List[str] = field(default_factory=list)  # 过滤后的股票池
    filter_stats: Dict[str, int] = field(default_factory=dict)  # 统计信息：各过滤器移除数量
    removed_reasons: Dict[str, List[str]] = field(default_factory=dict)  # 移除原因：{原因: [股票列表]}


# 示例用法
if __name__ == "__main__":
    # 构造输入
    input_data = FilterInput(
        base_universe=['600001.XSHG', '600002.XSHG', '000001.XSHE'],
        date=date(2024, 1, 1),
        config={'min_days': 250},
        positions=['600001.XSHG']
    )

    # 构造输出
    output_data = FilterOutput(
        filtered_universe=['600001.XSHG'],
        filter_stats={'new_stock': 1, 'paused': 1},
        removed_reasons={'new_stock': ['600002.XSHG'], 'paused': ['000001.XSHE']}
    )

    print(f"输入: {input_data}")
    print(f"输出: {output_data}")