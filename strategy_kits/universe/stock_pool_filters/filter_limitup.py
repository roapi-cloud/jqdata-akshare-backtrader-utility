"""
涨停股票过滤器
过滤当日涨停不可买入的股票，保留已持仓股票
"""
from typing import List

from ...core import get_logger, log_kv
from .contract import FilterInput, FilterOutput
from ._data_utils import build_limit_map, build_price_map


_logger = get_logger("stock_pool_filters.filter_limitup")


def filter_limitup(input_data: FilterInput) -> FilterOutput:
    """
    过滤涨停不可买股票

    实现要点：
    - 对比最新价与涨停价
    - 已持仓股票允许保留（观察后续走势）
    - 未持仓且已涨停的股票移除（无法买入）

    数据依赖（需适配聚宽风格API）：
    - get_price(stock, end_date=date, frequency='1m', fields='close', count=1)
    - get_current_data()[stock].high_limit

    Args:
        input_data: 包含 base_universe、date、config、positions
            config参数：
            - keep_positions: 是否保留持仓（默认True）

    Returns:
        FilterOutput: 过滤后的股票池和移除统计
    """
    removed_stocks: List[str] = []
    filtered_universe: List[str] = []

    positions = input_data.positions or []
    keep_positions = input_data.config.get('keep_positions', True)
    position_set = set(str(s) for s in positions)
    price_map = build_price_map(input_data.config)
    high_limit_map = build_limit_map(input_data.config, side="high")

    for stock in input_data.base_universe:
        if keep_positions and stock in position_set:
            filtered_universe.append(stock)
            continue

        latest_price = price_map.get(stock)
        high_limit = high_limit_map.get(stock)
        if latest_price is None or high_limit is None:
            filtered_universe.append(stock)
            continue

        if latest_price >= high_limit:
            removed_stocks.append(stock)
            continue
        filtered_universe.append(stock)

    # 构造输出
    output = FilterOutput(
        filtered_universe=filtered_universe,
        filter_stats={'limitup': len(removed_stocks)},
        removed_reasons={'limitup': removed_stocks}
    )

    log_kv(
        _logger,
        20,  # logging.INFO
        "filter_limitup_applied",
        input_count=len(input_data.base_universe),
        removed=len(removed_stocks),
        output_count=len(filtered_universe),
        keep_positions=bool(keep_positions),
    )

    return output


# 聚宽原始实现参考（来源：聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:251-255）
"""
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]
"""


if __name__ == "__main__":
    # 测试示例
    from datetime import date as d

    test_input = FilterInput(
        base_universe=['600001.XSHG', '600002.XSHG', '000001.XSHE'],
        date=d(2024, 1, 1),
        config={'keep_positions': True},
        positions=['600001.XSHG']  # 假设已持仓
    )

    test_output = filter_limitup(test_input)
    print(f"过滤后股票池: {test_output.filtered_universe}")
    print(f"移除数量: {test_output.filter_stats}")
    print(f"移除原因: {test_output.removed_reasons}")
