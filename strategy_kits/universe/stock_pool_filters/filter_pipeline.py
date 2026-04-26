"""
组合过滤器管道
串联执行多个过滤器，返回最终结果
"""
from typing import List, Dict, Any, Optional
from datetime import date

from ...core import get_logger, log_kv
from .contract import FilterInput, FilterOutput
from .filter_st import filter_st
from .filter_paused import filter_paused
from .filter_new_stock import filter_new_stock
from .filter_limitup import filter_limitup
from .filter_limitdown import filter_limitdown
from .filter_kcbj import filter_kcbj
from .default_config import DEFAULT_FILTER_CONFIG


_logger = get_logger("stock_pool_filters.pipeline")


def apply_filters(
    base_universe: List[str],
    date: date,
    filter_config: Optional[Dict[str, Dict[str, Any]]] = None,
    positions: Optional[List[str]] = None
) -> FilterOutput:
    """
    应用多个过滤器，返回最终结果

    Args:
        base_universe: 基础股票池
        date: 过滤日期
        filter_config: 过滤器配置字典（默认使用DEFAULT_FILTER_CONFIG）
        positions: 当前持仓股票列表

    Returns:
        FilterOutput: 包含最终股票池、统计数据、移除原因

    示例:
        >>> result = apply_filters(
        >>>     base_universe=['600001.XSHG', '600002.XSHG'],
        >>>     date=date(2024, 1, 1),
        >>>     filter_config={'st': {'enabled': True}, 'paused': {'enabled': True}},
        >>>     positions=['600001.XSHG']
        >>> )
        >>> print(result.filtered_universe)
        >>> print(result.filter_stats)
    """
    # 使用默认配置如果未提供
    config = filter_config or DEFAULT_FILTER_CONFIG

    # 初始化输入
    current_universe = base_universe.copy()
    final_stats: Dict[str, int] = {}
    final_removed_reasons: Dict[str, List[str]] = {}

    # 定义过滤器映射
    filter_map = {
        'st': filter_st,
        'paused': filter_paused,
        'new_stock': filter_new_stock,
        'limitup': filter_limitup,
        'limitdown': filter_limitdown,
        'kcbj': filter_kcbj,
    }

    # 串联执行过滤器
    for filter_name, filter_func in filter_map.items():
        # 检查是否启用
        if not config.get(filter_name, {}).get('enabled', False):
            continue

        before_count = len(current_universe)
        # 构造输入
        input_data = FilterInput(
            base_universe=current_universe,
            date=date,
            config=config.get(filter_name, {}),
            positions=positions
        )

        # 执行过滤
        output_data = filter_func(input_data)

        # 更新股票池
        current_universe = output_data.filtered_universe
        after_count = len(current_universe)

        # 合并统计和移除原因
        final_stats.update(output_data.filter_stats)
        for reason, stocks in output_data.removed_reasons.items():
            if reason in final_removed_reasons:
                final_removed_reasons[reason].extend(stocks)
            else:
                final_removed_reasons[reason] = stocks

        log_kv(
            _logger,
            20,  # logging.INFO
            "filter_stage_done",
            filter_name=filter_name,
            before_count=before_count,
            after_count=after_count,
            removed=before_count - after_count,
        )

    # 构造最终输出
    final_output = FilterOutput(
        filtered_universe=current_universe,
        filter_stats=final_stats,
        removed_reasons=final_removed_reasons
    )

    log_kv(
        _logger,
        20,  # logging.INFO
        "filter_pipeline_done",
        input_count=len(base_universe),
        output_count=len(current_universe),
        active_filters=sum(1 for k, v in config.items() if v.get("enabled", False)),
    )

    return final_output


if __name__ == "__main__":
    # 测试示例
    from datetime import date as d
    from .default_config import get_minimal_config

    # 模拟基础股票池
    base_universe = [
        '600001.XSHG', '600002.XSHG', '000001.XSHE',
        '688001.XSHG', '430001.XSHE', '830001.XSHE'
    ]

    # 应用最小配置过滤器
    result = apply_filters(
        base_universe=base_universe,
        date=d(2024, 1, 1),
        filter_config=get_minimal_config(),
        positions=['600001.XSHG']
    )

    print(f"基础股票池数量: {len(base_universe)}")
    print(f"过滤后股票池数量: {len(result.filtered_universe)}")
    print(f"过滤后股票池: {result.filtered_universe}")
    print(f"移除统计: {result.filter_stats}")
    print(f"移除原因: {result.removed_reasons}")
