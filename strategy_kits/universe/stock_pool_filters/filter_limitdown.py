"""
跌停股票过滤器
过滤当日跌停股票，保留已持仓股票
边界说明：跌停买入困难，卖出无法成交
"""
from typing import List

from ...core import get_logger, log_kv
from .contract import FilterInput, FilterOutput
from ._data_utils import build_limit_map, build_price_map


_logger = get_logger("stock_pool_filters.filter_limitdown")


def filter_limitdown(input_data: FilterInput) -> FilterOutput:
    """
    过滤跌停不可买股票

    实现要点：
    - 对比最新价与跌停价
    - 已持仓股票允许保留（但需策略层判断是否卖出）
    - 未持仓且已跌停的股票移除（买入可能困难）

    边界说明：
    - 跌停股票：买入可能成交困难，卖出确定无法成交
    - 建议策略层在卖出逻辑中额外判断跌停状态
    - 过滤器默认行为：移除未持仓的跌停股票

    数据依赖（需适配聚宽风格API）：
    - get_price(stock, end_date=date, frequency='1m', fields='close', count=1)
    - get_current_data()[stock].low_limit

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
    low_limit_map = build_limit_map(input_data.config, side="low")

    for stock in input_data.base_universe:
        if keep_positions and stock in position_set:
            filtered_universe.append(stock)
            continue

        latest_price = price_map.get(stock)
        low_limit = low_limit_map.get(stock)
        if latest_price is None or low_limit is None:
            filtered_universe.append(stock)
            continue

        if latest_price <= low_limit:
            removed_stocks.append(stock)
            continue
        filtered_universe.append(stock)

    # 构造输出
    output = FilterOutput(
        filtered_universe=filtered_universe,
        filter_stats={'limitdown': len(removed_stocks)},
        removed_reasons={'limitdown': removed_stocks}
    )

    log_kv(
        _logger,
        20,  # logging.INFO
        "filter_limitdown_applied",
        input_count=len(input_data.base_universe),
        removed=len(removed_stocks),
        output_count=len(filtered_universe),
        keep_positions=bool(keep_positions),
    )

    return output


# 聚宽原始实现参考（来源：聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:258-262）
"""
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]
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

    test_output = filter_limitdown(test_input)
    print(f"过滤后股票池: {test_output.filtered_universe}")
    print(f"移除数量: {test_output.filter_stats}")
    print(f"移除原因: {test_output.removed_reasons}")
    print("\n边界说明：跌停买入困难，卖出无法成交，建议策略层在卖出逻辑中额外判断")
