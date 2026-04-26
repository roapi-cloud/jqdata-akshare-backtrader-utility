"""
停牌股票过滤器
过滤停牌股票，支持停牌天数阈值
"""
from typing import List

from ...core import get_logger, log_kv
from .contract import FilterInput, FilterOutput
from ._data_utils import build_paused_history_map, build_paused_map


_logger = get_logger("stock_pool_filters.filter_paused")


def filter_paused(input_data: FilterInput) -> FilterOutput:
    """
    过滤停牌股票

    实现要点：
    - 检查 paused 字段（True表示停牌）
    - 支持停牌天数阈值：过去N天内停牌天数少于threshold

    数据依赖（需适配聚宽风格API）：
    - get_price(stock_list, end_date=date, count=paused_N, fields='paused', panel=False)

    Args:
        input_data: 包含 base_universe、date、config
            config可选参数：
            - paused_N: 查询天数（默认1）
            - threshold: 停牌天数阈值（可选）

    Returns:
        FilterOutput: 过滤后的股票池和移除统计
    """
    removed_stocks: List[str] = []
    filtered_universe: List[str] = []

    paused_n = int(input_data.config.get("paused_N", 1))
    threshold = input_data.config.get("threshold")
    paused_map = build_paused_map(input_data.base_universe, input_data.config)
    paused_history_map = build_paused_history_map(input_data.config)

    for stock in input_data.base_universe:
        if threshold is None:
            is_paused = int(paused_map.get(stock, 0)) == 1
            if is_paused:
                removed_stocks.append(stock)
                continue
            filtered_universe.append(stock)
            continue

        history = paused_history_map.get(stock, [])
        if not history:
            latest = int(paused_map.get(stock, 0))
            history = [latest]
        paused_days = sum(int(v) for v in history[:paused_n])
        if paused_days >= int(threshold):
            removed_stocks.append(stock)
            continue
        filtered_universe.append(stock)

    # 构造输出
    output = FilterOutput(
        filtered_universe=filtered_universe,
        filter_stats={'paused': len(removed_stocks)},
        removed_reasons={'paused': removed_stocks}
    )

    log_kv(
        _logger,
        20,  # logging.INFO
        "filter_paused_applied",
        input_count=len(input_data.base_universe),
        removed=len(removed_stocks),
        output_count=len(filtered_universe),
        paused_n=paused_n,
        threshold=threshold if threshold is not None else "none",
    )

    return output


# QuantsPlaybook原始实现参考（来源：QuantsPlaybook/B-因子构建类/高频价量相关性/Hugos_tools/BuildStockPool.py:52-78）
"""
def filter_paused(self, paused_N:int=1, threshold:int=None)->list:
    '''过滤停牌股
    输入:
        paused_N:默认为1即查询当日不停牌
        threshold:在过paused_N日内停牌数量小于threshold
    '''
    paused = get_price(self.securities, end_date=self.watch_date,
                      count=paused_N, fields='paused', panel=False)
    paused = paused.pivot(index='time', columns='code')['paused']

    if threshold:
        sum_paused_day = paused.sum()
        self.securities = sum_paused_day[sum_paused_day < threshold].index.tolist()
    else:
        paused_ser = paused.iloc[-1]
        self.securities = paused_ser[paused_ser == 0].index.tolist()
"""


if __name__ == "__main__":
    # 测试示例
    from datetime import date as d

    test_input = FilterInput(
        base_universe=['600001.XSHG', '600002.XSHG', '000001.XSHE'],
        date=d(2024, 1, 1),
        config={'paused_N': 1}
    )

    test_output = filter_paused(test_input)
    print(f"过滤后股票池: {test_output.filtered_universe}")
    print(f"移除数量: {test_output.filter_stats}")
    print(f"移除原因: {test_output.removed_reasons}")
