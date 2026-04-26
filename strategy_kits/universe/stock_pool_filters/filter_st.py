"""
ST股票过滤器
过滤ST、*ST、退市股票
"""
from typing import List

from ...core import get_logger, log_kv
from .contract import FilterInput, FilterOutput
from ._data_utils import build_name_map, build_st_map


_logger = get_logger("stock_pool_filters.filter_st")


def filter_st(input_data: FilterInput) -> FilterOutput:
    """
    过滤ST、*ST、退市股票

    实现要点：
    - 检查 is_st 字段（True表示ST状态）
    - 检查股票名称包含 'ST'、'*'、'退' 等标签

    数据依赖（需适配聚宽风格API）：
    - get_extras('is_st', stock_list, date=date)
    - get_security_info(stock).display_name

    Args:
        input_data: 包含 base_universe、date、config

    Returns:
        FilterOutput: 过滤后的股票池和移除统计
    """
    removed_stocks: List[str] = []
    filtered_universe: List[str] = []

    check_name = bool(input_data.config.get("check_name", True))
    st_map = build_st_map(input_data.base_universe, input_data.config)
    name_map = build_name_map(input_data.base_universe, input_data.config) if check_name else {}

    for stock in input_data.base_universe:
        is_st_flag = bool(st_map.get(stock, False))
        if is_st_flag:
            removed_stocks.append(stock)
            continue

        if check_name:
            name = str(name_map.get(stock, ""))
            if any(token in name for token in ("ST", "*", "退")):
                removed_stocks.append(stock)
                continue

        filtered_universe.append(stock)

    # 构造输出
    output = FilterOutput(
        filtered_universe=filtered_universe,
        filter_stats={'st': len(removed_stocks)},
        removed_reasons={'st': removed_stocks}
    )

    log_kv(
        _logger,
        20,  # logging.INFO
        "filter_st_applied",
        input_count=len(input_data.base_universe),
        removed=len(removed_stocks),
        output_count=len(filtered_universe),
    )

    return output


# 聚宽原始实现参考（来源：聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:236-241）
"""
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]
"""


if __name__ == "__main__":
    # 测试示例
    from datetime import date as d

    test_input = FilterInput(
        base_universe=['600001.XSHG', '600002.XSHG', '000001.XSHE'],
        date=d(2024, 1, 1),
        config={'check_name': True}
    )

    test_output = filter_st(test_input)
    print(f"过滤后股票池: {test_output.filtered_universe}")
    print(f"移除数量: {test_output.filter_stats}")
    print(f"移除原因: {test_output.removed_reasons}")
