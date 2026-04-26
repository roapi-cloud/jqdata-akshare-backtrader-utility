"""
次新股过滤器
过滤上市不足指定天数的股票
"""
from typing import List

from ...core import get_logger, log_kv
from .contract import FilterInput, FilterOutput
from ._data_utils import build_listing_date_map


_logger = get_logger("stock_pool_filters.filter_new_stock")


def filter_new_stock(input_data: FilterInput) -> FilterOutput:
    """
    过滤次新股（上市不足指定天数）

    实现要点：
    - 计算上市日期与当前日期差值
    - 移除上市天数小于 min_days 的股票

    数据依赖（需适配聚宽风格API）：
    - get_security_info(stock).start_date

    Args:
        input_data: 包含 base_universe、date、config
            config参数：
            - min_days: 最小上市天数（默认250）

    Returns:
        FilterOutput: 过滤后的股票池和移除统计
    """
    removed_stocks: List[str] = []
    filtered_universe: List[str] = []

    min_days = input_data.config.get('min_days', 250)
    drop_if_missing = bool(input_data.config.get("drop_if_missing_listing_date", False))
    listing_dates = build_listing_date_map(input_data.base_universe, input_data.config)

    for stock in input_data.base_universe:
        start_date = listing_dates.get(stock)
        if start_date is None:
            if drop_if_missing:
                removed_stocks.append(stock)
            else:
                filtered_universe.append(stock)
            continue

        days_since_listing = (input_data.date - start_date).days
        if days_since_listing < int(min_days):
            removed_stocks.append(stock)
            continue
        filtered_universe.append(stock)

    # 构造输出
    output = FilterOutput(
        filtered_universe=filtered_universe,
        filter_stats={'new_stock': len(removed_stocks)},
        removed_reasons={'new_stock': removed_stocks}
    )

    log_kv(
        _logger,
        20,  # logging.INFO
        "filter_new_stock_applied",
        input_count=len(input_data.base_universe),
        removed=len(removed_stocks),
        output_count=len(filtered_universe),
        min_days=min_days,
        drop_if_missing=drop_if_missing,
    )

    return output


# 聚宽原始实现参考（来源：聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:265-267）
"""
def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list
            if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)]
"""


if __name__ == "__main__":
    # 测试示例
    from datetime import date as d

    test_input = FilterInput(
        base_universe=['600001.XSHG', '600002.XSHG', '000001.XSHE'],
        date=d(2024, 1, 1),
        config={'min_days': 250}
    )

    test_output = filter_new_stock(test_input)
    print(f"过滤后股票池: {test_output.filtered_universe}")
    print(f"移除数量: {test_output.filter_stats}")
    print(f"移除原因: {test_output.removed_reasons}")
