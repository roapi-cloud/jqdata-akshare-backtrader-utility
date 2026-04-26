"""
科创板/北交所过滤器
过滤科创板（68开头）和北交所（4/8开头）股票
"""
from typing import List

from .contract import FilterInput, FilterOutput


def filter_kcbj(input_data: FilterInput) -> FilterOutput:
    """
    过滤科创板和北交所股票

    实现要点：
    - 北交所：股票代码以 '4' 或 '8' 开头
    - 科创板：股票代码以 '68' 开头

    Args:
        input_data: 包含 base_universe、date、config

    Returns:
        FilterOutput: 过滤后的股票池和移除统计
    """
    removed_stocks: List[str] = []
    filtered_universe = []

    for stock in input_data.base_universe:
        # 获取股票代码前缀（去除交易所后缀）
        # 如 '688001.XSHG' -> '688001'
        code_prefix = stock.split('.')[0]

        # 北交所：4开头或8开头
        if code_prefix.startswith('4') or code_prefix.startswith('8'):
            removed_stocks.append(stock)
            continue

        # 科创板：68开头
        if code_prefix.startswith('68'):
            removed_stocks.append(stock)
            continue

        # 保留其他股票
        filtered_universe.append(stock)

    # 构造输出
    output = FilterOutput(
        filtered_universe=filtered_universe,
        filter_stats={'kcbj': len(removed_stocks)},
        removed_reasons={'kcbj': removed_stocks}
    )

    return output


# 聚宽原始实现参考（来源：聚宽有价值策略558/37 微盘股扩散指数双均线择时.txt:244-248）
"""
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list
"""


if __name__ == "__main__":
    # 测试示例
    from datetime import date as d

    test_input = FilterInput(
        base_universe=[
            '600001.XSHG',    # 主板，保留
            '688001.XSHG',    # 科创板，移除
            '430001.XSHE',    # 北交所，移除
            '830001.XSHE',    # 北交所，移除
            '000001.XSHE'     # 深市，保留
        ],
        date=d(2024, 1, 1),
        config={}
    )

    test_output = filter_kcbj(test_input)
    print(f"过滤后股票池: {test_output.filtered_universe}")
    print(f"移除数量: {test_output.filter_stats}")
    print(f"移除原因: {test_output.removed_reasons}")
    print(f"预期保留: ['600001.XSHG', '000001.XSHE']")