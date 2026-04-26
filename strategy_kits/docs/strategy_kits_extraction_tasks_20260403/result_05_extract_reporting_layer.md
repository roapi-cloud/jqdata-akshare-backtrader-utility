# 任务 05：抽统一绩效与报告层

## 抽取来源

1. **聚宽侧**：`stock-backtesting-system/src/backtest/backtrader_base_strategy.py:531` - `analyze_performance()`
2. **QuantsPlaybook**：
   - `hugos_toolkit/BackTestReport/performance.py` - `strategy_performance()`
   - `hugos_toolkit/BackTestReport/tear.py` - `get_backtest_report()`, `create_trade_report_table()`, `analysis_rets()`, `analysis_trade()`
   - `hugos_toolkit/BackTestReport/timeseries.py` - `gen_drawdown_table()`

## 统一接口设计

### 核心函数

```python
# strategy_kits/validation/reporting/performance.py

def compute_performance(returns: pd.Series, benchmark_returns: pd.Series = None, period: str = 'daily') -> pd.DataFrame:
    """
    计算策略绩效指标
    
    Parameters:
        returns: 策略日收益率序列
        benchmark_returns: 基准收益率序列（可选）
        period: 收益频率 ('daily', 'hourly', 'monthly')
    
    Returns:
        DataFrame 包含：
        - 年化收益率、累计收益率
        - 年化波动率、夏普比率、索提诺比率、Calmar比率
        - 最大回撤
        - Alpha、Beta、信息比率（如有基准）
        - 超额收益率（如有基准）
    """

def compute_trade_stats(trade_list: pd.DataFrame) -> pd.DataFrame:
    """
    计算交易统计指标
    
    Parameters:
        trade_list: 交易记录 DataFrame（datein, dateout, pricein, priceout）
    
    Returns:
        DataFrame 包含：
        - 交易总笔数、完结笔数、未完结笔数
        - 胜率、盈亏比
        - 平均持仓天数、最大持仓天数、最短持仓天数
        - 连续获利次数、连续亏损次数
        - 平均盈利、平均亏损
    """

def build_tearsheet(returns: pd.Series, benchmark_returns: pd.Series = None, 
                    trade_list: pd.DataFrame = None, price: pd.Series = None) -> dict:
    """
    构建完整报告对象
    
    Returns:
        dict 包含：
        - performance_metrics: DataFrame（绩效指标）
        - trade_stats: DataFrame（交易统计，可选）
        - drawdown_table: DataFrame（最大回撤表）
        - charts: dict（图表对象）
            - cumulative: 累计收益曲线
            - drawdowns: 回撤图
            - underwater: 水下图
            - annual_returns: 年度收益图
            - monthly_heatmap: 月度热力图
            - monthly_dist: 月度分布图
            - pnl: 盈亏图（如有交易数据）
            - orders: 订单图（如有价格和交易数据）
            - position: 持仓图（如有价格和交易数据）
    """

def export_summary(performance: pd.DataFrame, trade_stats: pd.DataFrame = None, 
                   output_path: str = None, format: str = 'markdown') -> str:
    """
    导出简版报告
    
    Parameters:
        performance: 绩效指标 DataFrame
        trade_stats: 交易统计 DataFrame（可选）
        output_path: 输出路径（可选）
        format: 输出格式 ('markdown', 'html', 'csv')
    
    Returns:
        格式化的报告字符串
    """
```

## 指标总表

| 指标类别 | 指标名称 | 计算公式 | 数据来源 |
|---------|---------|---------|---------|
| **收益指标** | 总收益率 | `(NAV_end / NAV_start - 1)` | 聚宽、QP |
| | 年化收益率 | `(NAV_end / NAV_start) ** (252/days) - 1` | 聚宽、QP |
| | 累计收益率 | `cum_returns(returns).iloc[-1]` | QP |
| | 超额收益率 | `annual_return - benchmark_annual_return` | QP |
| **风险指标** | 年化波动率 | `std(returns) * sqrt(252)` | QP |
| | 最大回撤 | `min((NAV - cummax(NAV)) / cummax(NAV))` | 聚宽、QP |
| | 下行波动率 | `sqrt(mean(neg_returns^2))` | 聚宽 |
| **风险调整收益** | 夏普比率 | `mean(returns) / std(returns) * sqrt(252)` | 聚宽、QP |
| | 索提诺比率 | `mean(returns) / downside_std * sqrt(252)` | 聚宽、QP |
| | Calmar比率 | `annual_return / abs(max_drawdown)` | QP |
| **相对指标** | Alpha | `回归常数项 * 252` | 聚宽、QP |
| | Beta | `回归斜率项` | 聚宽、QP |
| | 信息比率 | `mean(excess_returns) / std(excess_returns) * sqrt(252)` | 聚宽、QP |

## 交易统计表

| 指标名称 | 计算逻辑 | 数据来源 |
|---------|---------|---------|
| 交易总笔数 | 已完成交易数 | QP |
| 胜率 | `won_trades / total_trades` | QP、聚宽 |
| 盈亏比 | `avg_win / abs(avg_loss)` | QP、聚宽 |
| 平均持仓天数 | `avg(holding_days)` | QP |
| 最大持仓天数 | `max(holding_days)` | QP |
| 最短持仓天数 | `min(holding_days)` | QP |
| 连续获利次数 | `max_consecutive_wins` | QP |
| 连续亏损次数 | `max_consecutive_losses` | QP |

## 回撤与收益曲线图表需求

### 必要图表

1. **累计收益曲线图**
   - 策略累计净值 vs 基准累计净值
   - 双Y轴或单Y轴对比

2. **回撤图**
   - 显示回撤区间
   - 标注峰值、谷值、恢复点

3. **水下图**
   - 持续回撤程度可视化
   - 时间轴上显示回撤深度

4. **年度收益柱状图**
   - 每年收益率对比
   - 策略 vs 基准

5. **月度收益热力图**
   - 年-月矩阵
   - 颜色编码收益率

6. **月度收益分布图**
   - 按月份分组统计
   - 箱线图或柱状图

### 可选图表（依赖交易数据）

7. **盈亏图**
   - 每笔交易盈亏
   - 时间序列展示

8. **订单图**
   - 价格曲线 + 买入/卖出标记点

9. **持仓图**
   - 价格曲线 + 持仓区间阴影

## 最小报告 Contract

```python
# strategy_kits/validation/reporting/contract.py

from typing import Protocol, Optional
import pandas as pd

class PerformanceReporter(Protocol):
    """绩效报告器协议"""
    
    def compute_performance(
        returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        period: str = 'daily'
    ) -> pd.DataFrame:
        """计算绩效指标"""
        ...
    
    def compute_trade_stats(
        trade_list: pd.DataFrame
    ) -> pd.DataFrame:
        """计算交易统计"""
        ...
    
    def build_tearsheet(
        returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        trade_list: Optional[pd.DataFrame] = None,
        price: Optional[pd.Series] = None
    ) -> dict:
        """构建完整报告"""
        ...
    
    def export_summary(
        performance: pd.DataFrame,
        trade_stats: Optional[pd.DataFrame] = None,
        output_path: Optional[str] = None,
        format: str = 'markdown'
    ) -> str:
        """导出简版报告"""
        ...
```

## 骨架文件

### 文件结构

```
strategy_kits/validation/reporting/
├── __init__.py
├── contract.py          # 协议定义
├── performance.py       # 指标计算核心
├── trade_stats.py       # 交易统计计算
├── tearsheet.py         # 报告构建
├── drawdown.py          # 回撤分析
├── visualization.py     # 图表生成（可选，依赖绘图库）
└── exporters/
    ├── __init__.py
    ├── markdown_exporter.py
    ├── html_exporter.py
    └── csv_exporter.py
```

### `__init__.py`

```python
"""
统一绩效与报告层

提供标准化的策略绩效计算、交易统计、报告生成功能。
让任何新策略跑完都能输出统一指标和基础报告。
"""

from .contract import PerformanceReporter
from .performance import compute_performance
from .trade_stats import compute_trade_stats
from .tearsheet import build_tearsheet
from .exporters import export_summary

__all__ = [
    'PerformanceReporter',
    'compute_performance',
    'compute_trade_stats',
    'build_tearsheet',
    'export_summary',
]
```

### `performance.py` 骨架

```python
"""
绩效指标计算
"""

import pandas as pd
import numpy as np
from typing import Optional

try:
    import empyrical as ep
    HAS_EMPYRICAL = True
except ImportError:
    HAS_EMPYRICAL = False

def compute_performance(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    period: str = 'daily'
) -> pd.DataFrame:
    """
    计算策略绩效指标
    
    Args:
        returns: 策略收益率序列（日频）
        benchmark_returns: 基准收益率序列（可选）
        period: 数据频率 ('daily', 'hourly', 'monthly')
    
    Returns:
        DataFrame 包含标准绩效指标
    """
    if len(returns) < 2:
        return _empty_performance()
    
    metrics = {}
    
    # 收益指标
    metrics['年化收益率'] = _annual_return(returns, period)
    metrics['累计收益率'] = _cumulative_return(returns)
    
    # 风险指标
    metrics['年化波动率'] = _annual_volatility(returns, period)
    metrics['最大回撤'] = _max_drawdown(returns)
    
    # 风险调整收益
    metrics['夏普比率'] = _sharpe_ratio(returns, period)
    metrics['索提诺比率'] = _sortino_ratio(returns, period)
    metrics['Calmar比率'] = _calmar_ratio(returns, period)
    
    # 相对指标（如有基准）
    if benchmark_returns is not None:
        aligned_benchmark = benchmark_returns.reindex(returns.index).fillna(0)
        metrics['Alpha'] = _alpha(returns, aligned_benchmark, period)
        metrics['Beta'] = _beta(returns, aligned_benchmark)
        metrics['信息比率'] = _information_ratio(returns, aligned_benchmark, period)
        metrics['超额收益率'] = metrics['年化收益率'] - _annual_return(aligned_benchmark, period)
    
    return pd.DataFrame([metrics]).T

def _annual_return(returns: pd.Series, period: str) -> float:
    """年化收益率"""
    if HAS_EMPYRICAL:
        return ep.annual_return(returns, period=period)
    # 手工计算
    cumulative = (1 + returns).prod()
    n_periods = len(returns)
    annual_factor = _get_annual_factor(period)
    return cumulative ** (annual_factor / n_periods) - 1

def _cumulative_return(returns: pd.Series) -> float:
    """累计收益率"""
    return (1 + returns).prod() - 1

def _annual_volatility(returns: pd.Series, period: str) -> float:
    """年化波动率"""
    if HAS_EMPYRICAL:
        return ep.annual_volatility(returns, period=period)
    annual_factor = _get_annual_factor(period)
    return returns.std() * np.sqrt(annual_factor)

def _max_drawdown(returns: pd.Series) -> float:
    """最大回撤"""
    if HAS_EMPYRICAL:
        return ep.max_drawdown(returns)
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()

def _sharpe_ratio(returns: pd.Series, period: str) -> float:
    """夏普比率"""
    if HAS_EMPYRICAL:
        return ep.sharpe_ratio(returns, period=period)
    annual_factor = _get_annual_factor(period)
    return returns.mean() / returns.std() * np.sqrt(annual_factor)

def _sortino_ratio(returns: pd.Series, period: str) -> float:
    """索提诺比率"""
    if HAS_EMPYRICAL:
        return ep.sortino_ratio(returns, period=period)
    annual_factor = _get_annual_factor(period)
    downside_returns = returns[returns < 0]
    downside_std = np.sqrt(np.mean(downside_returns ** 2))
    if downside_std == 0:
        return np.nan
    return returns.mean() / downside_std * np.sqrt(annual_factor)

def _calmar_ratio(returns: pd.Series, period: str) -> float:
    """Calmar比率"""
    if HAS_EMPYRICAL:
        return ep.calmar_ratio(returns, period=period)
    annual_ret = _annual_return(returns, period)
    max_dd = _max_drawdown(returns)
    if max_dd == 0:
        return np.nan
    return annual_ret / abs(max_dd)

def _alpha(returns: pd.Series, benchmark: pd.Series, period: str) -> float:
    """Alpha"""
    if HAS_EMPYRICAL:
        return ep.alpha(returns, benchmark, period=period)
    # 手工回归
    import statsmodels.api as sm
    X = sm.add_constant(benchmark)
    model = sm.OLS(returns, X).fit()
    annual_factor = _get_annual_factor(period)
    return model.params['const'] * annual_factor

def _beta(returns: pd.Series, benchmark: pd.Series) -> float:
    """Beta"""
    if HAS_EMPYRICAL:
        return ep.beta(returns, benchmark)
    import statsmodels.api as sm
    X = sm.add_constant(benchmark)
    model = sm.OLS(returns, X).fit()
    return model.params.get(benchmark.name if benchmark.name else 'x1', np.nan)

def _information_ratio(returns: pd.Series, benchmark: pd.Series, period: str) -> float:
    """信息比率"""
    excess_returns = returns - benchmark
    annual_factor = _get_annual_factor(period)
    if excess_returns.std() == 0:
        return np.nan
    return excess_returns.mean() / excess_returns.std() * np.sqrt(annual_factor)

def _get_annual_factor(period: str) -> int:
    """年化因子"""
    factors = {'daily': 252, 'hourly': 252*6, 'monthly': 12}
    return factors.get(period, 252)

def _empty_performance() -> pd.DataFrame:
    """空绩效表"""
    return pd.DataFrame([{
        '年化收益率': np.nan,
        '累计收益率': np.nan,
        '年化波动率': np.nan,
        '最大回撤': np.nan,
        '夏普比率': np.nan,
        '索提诺比率': np.nan,
        'Calmar比率': np.nan,
    }]).T
```

### `trade_stats.py` 骨架

```python
"""
交易统计计算
"""

import pandas as pd
import numpy as np
from typing import Dict

def compute_trade_stats(trade_list: pd.DataFrame) -> pd.DataFrame:
    """
    计算交易统计指标
    
    Args:
        trade_list: DataFrame with columns [datein, dateout, pricein, priceout]
    
    Returns:
        DataFrame 包含交易统计指标
    """
    if trade_list.empty:
        return _empty_trade_stats()
    
    stats = {}
    
    # 基础统计
    total_trades = len(trade_list)
    completed = trade_list['dateout'].notna().sum()
    
    stats['交易总笔数'] = total_trades
    stats['完结笔数'] = completed
    stats['未完结笔数'] = total_trades - completed
    
    # 盈亏统计（仅完结交易）
    completed_trades = trade_list[trade_list['dateout'].notna()]
    if len(completed_trades) > 0:
        pnl = completed_trades['priceout'] - completed_trades['pricein']
        
        won = (pnl > 0).sum()
        lost = (pnl < 0).sum()
        
        stats['胜率'] = won / len(completed_trades) if len(completed_trades) > 0 else np.nan
        
        avg_win = pnl[pnl > 0].mean() if won > 0 else np.nan
        avg_loss = pnl[pnl < 0].mean() if lost > 0 else np.nan
        
        stats['盈亏比'] = avg_win / abs(avg_loss) if avg_loss != 0 and not np.isnan(avg_loss) else np.nan
        
        # 持仓天数
        holding_days = (completed_trades['dateout'] - completed_trades['datein']).dt.days
        stats['平均持仓天数'] = holding_days.mean()
        stats['最大持仓天数'] = holding_days.max()
        stats['最短持仓天数'] = holding_days.min()
        
        # 连续统计
        stats['连续获利次数'] = _max_consecutive(pnl > 0)
        stats['连续亏损次数'] = _max_consecutive(pnl < 0)
    else:
        stats['胜率'] = np.nan
        stats['盈亏比'] = np.nan
        stats['平均持仓天数'] = np.nan
        stats['最大持仓天数'] = np.nan
        stats['最短持仓天数'] = np.nan
        stats['连续获利次数'] = np.nan
        stats['连续亏损次数'] = np.nan
    
    return pd.DataFrame([stats]).T

def _max_consecutive(condition: pd.Series) -> int:
    """计算最大连续次数"""
    if condition.empty:
        return 0
    max_count = 0
    current_count = 0
    for val in condition:
        if val:
            current_count += 1
            max_count = max(max_count, current_count)
        else:
            current_count = 0
    return max_count

def _empty_trade_stats() -> pd.DataFrame:
    """空交易统计表"""
    return pd.DataFrame([{
        '交易总笔数': np.nan,
        '完结笔数': np.nan,
        '未完结笔数': np.nan,
        '胜率': np.nan,
        '盈亏比': np.nan,
        '平均持仓天数': np.nan,
        '最大持仓天数': np.nan,
        '最短持仓天数': np.nan,
        '连续获利次数': np.nan,
        '连续亏损次数': np.nan,
    }]).T

def create_trade_report_from_analyzer(trader_analyzer: Dict) -> pd.DataFrame:
    """
    从 Backtrader TradeAnalyzer 创建交易统计表
    （兼容 QuantsPlaybook 接口）
    
    Args:
        trader_analyzer: Backtrader 分析器结果字典
    
    Returns:
        DataFrame 包含交易统计
    """
    stats = {}
    
    def get_value(keys: list, default=np.nan):
        """嵌套获取值"""
        val = trader_analyzer
        for key in keys:
            if isinstance(val, dict) and key in val:
                val = val[key]
            else:
                return default
        return val
    
    stats['交易总笔数'] = get_value(['total', 'total'])
    stats['完结笔数'] = get_value(['total', 'closed'])
    stats['未完结笔数'] = get_value(['total', 'open'])
    
    won = get_value(['won', 'total'])
    total = stats['交易总笔数']
    stats['胜率'] = won / total if total > 0 else np.nan
    
    won_money = get_value(['won', 'pnl', 'total'])
    lost_money = get_value(['lost', 'pnl', 'total'])
    stats['盈亏比'] = won_money / abs(lost_money) if lost_money != 0 else np.nan
    
    stats['平均持仓天数'] = get_value(['len', 'average'])
    stats['最大持仓天数'] = get_value(['len', 'max'])
    stats['最短持仓天数'] = get_value(['len', 'min'])
    
    stats['连续获利次数'] = get_value(['streak', 'won', 'longest'])
    stats['连续亏损次数'] = get_value(['streak', 'lost', 'longest'])
    
    return pd.DataFrame([stats]).T
```

### `tearsheet.py` 骨架

```python
"""
完整报告构建
"""

import pandas as pd
from typing import Optional, Dict
from .performance import compute_performance
from .trade_stats import compute_trade_stats
from .drawdown import compute_drawdown_table

def build_tearsheet(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    trade_list: Optional[pd.DataFrame] = None,
    price: Optional[pd.Series] = None
) -> Dict:
    """
    构建完整报告对象
    
    Args:
        returns: 策略收益率序列
        benchmark_returns: 基准收益率（可选）
        trade_list: 交易记录 DataFrame（可选）
        price: 价格序列（可选，用于图表）
    
    Returns:
        dict 包含绩效指标、交易统计、回撤表、图表对象
    """
    report = {}
    
    # 绩效指标
    report['performance_metrics'] = compute_performance(returns, benchmark_returns)
    
    # 交易统计（如有）
    if trade_list is not None:
        report['trade_stats'] = compute_trade_stats(trade_list)
    
    # 回撤表
    report['drawdown_table'] = compute_drawdown_table(returns)
    
    # 图表对象（依赖可视化模块）
    report['charts'] = {}
    try:
        from .visualization import (
            plot_cumulative,
            plot_drawdowns,
            plot_underwater,
            plot_annual_returns,
            plot_monthly_heatmap,
            plot_monthly_dist,
        )
        
        report['charts']['cumulative'] = plot_cumulative(returns, benchmark_returns)
        report['charts']['drawdowns'] = plot_drawdowns(returns)
        report['charts']['underwater'] = plot_underwater(returns)
        report['charts']['annual_returns'] = plot_annual_returns(returns)
        report['charts']['monthly_heatmap'] = plot_monthly_heatmap(returns)
        report['charts']['monthly_dist'] = plot_monthly_dist(returns)
        
        # 交易图表（如有）
        if trade_list is not None:
            from .visualization import plot_pnl
            report['charts']['pnl'] = plot_pnl(trade_list)
        
        if price is not None and trade_list is not None:
            from .visualization import plot_orders, plot_position
            report['charts']['orders'] = plot_orders(price, trade_list)
            report['charts']['position'] = plot_position(price, trade_list)
    except ImportError:
        # 无可视化库时跳过
        pass
    
    return report
```

### `drawdown.py` 骨架

```python
"""
回撤分析
"""

import pandas as pd
import numpy as np
from typing import List, Tuple

try:
    import empyrical as ep
    HAS_EMPYRICAL = True
except ImportError:
    HAS_EMPYRICAL = False

def compute_drawdown_table(returns: pd.Series, top: int = 5) -> pd.DataFrame:
    """
    计算最大回撤表
    
    Args:
        returns: 策略收益率序列
        top: 显示前N个回撤
    
    Returns:
        DataFrame 包含回撤峰值、谷值、恢复点、持续时间
    """
    if len(returns) < 2:
        return _empty_drawdown_table(top)
    
    drawdowns = _get_top_drawdowns(returns, top)
    
    df = pd.DataFrame(
        index=range(len(drawdowns)),
        columns=[
            'Net drawdown %',
            'Peak date',
            'Valley date',
            'Recovery date',
            'Duration (days)',
        ]
    )
    
    cumulative = _cumulative_returns(returns)
    
    for i, (peak, valley, recovery) in enumerate(drawdowns):
        df.loc[i, 'Peak date'] = peak
        df.loc[i, 'Valley date'] = valley
        df.loc[i, 'Recovery date'] = recovery if not pd.isnull(recovery) else np.nan
        
        drawdown_val = (cumulative.loc[peak] - cumulative.loc[valley]) / cumulative.loc[peak]
        df.loc[i, 'Net drawdown %'] = drawdown_val * 100
        
        if not pd.isnull(recovery):
            df.loc[i, 'Duration (days)'] = (recovery - peak).days
        else:
            df.loc[i, 'Duration (days)'] = np.nan
    
    return df

def _get_top_drawdowns(returns: pd.Series, top: int) -> List[Tuple]:
    """获取前N个最大回撤区间"""
    cumulative = _cumulative_returns(returns)
    running_max = cumulative.cummax()
    underwater = (cumulative - running_max) / running_max
    
    drawdowns = []
    underwater_copy = underwater.copy()
    
    for _ in range(top):
        if underwater_copy.empty or underwater_copy.min() == 0:
            break
        
        valley = underwater_copy.idxmin()
        peak = underwater_copy[:valley][underwater_copy[:valley] == 0].index[-1]
        
        try:
            recovery = underwater_copy[valley:][underwater_copy[valley:] == 0].index[0]
        except IndexError:
            recovery = np.nan
        
        drawdowns.append((peak, valley, recovery))
        
        if not pd.isnull(recovery):
            underwater_copy = underwater_copy.drop(underwater_copy[peak:recovery].index[1:-1])
        else:
            underwater_copy = underwater_copy.loc[:peak]
    
    return drawdowns

def _cumulative_returns(returns: pd.Series) -> pd.Series:
    """累计收益"""
    if HAS_EMPYRICAL:
        return ep.cum_returns(returns, 1.0)
    return (1 + returns).cumprod()

def _empty_drawdown_table(top: int) -> pd.DataFrame:
    """空回撤表"""
    return pd.DataFrame(
        index=range(top),
        columns=[
            'Net drawdown %',
            'Peak date',
            'Valley date',
            'Recovery date',
            'Duration (days)',
        ]
    )
```

### `exporters/__init__.py`

```python
"""
报告导出器
"""

from typing import Optional
import pandas as pd

def export_summary(
    performance: pd.DataFrame,
    trade_stats: Optional[pd.DataFrame] = None,
    output_path: Optional[str] = None,
    format: str = 'markdown'
) -> str:
    """
    导出简版报告
    
    Args:
        performance: 绩效指标 DataFrame
        trade_stats: 交易统计 DataFrame（可选）
        output_path: 输出路径（可选）
        format: 输出格式 ('markdown', 'html', 'csv')
    
    Returns:
        格式化的报告字符串
    """
    exporters = {
        'markdown': _export_markdown,
        'html': _export_html,
        'csv': _export_csv,
    }
    
    exporter = exporters.get(format, _export_markdown)
    content = exporter(performance, trade_stats)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(content)
    
    return content

def _export_markdown(performance: pd.DataFrame, trade_stats: Optional[pd.DataFrame]) -> str:
    """Markdown 导出"""
    lines = ['# 策略绩效报告', '']
    
    lines.append('## 绩效指标')
    lines.append('')
    lines.append(performance.to_markdown())
    lines.append('')
    
    if trade_stats is not None:
        lines.append('## 交易统计')
        lines.append('')
        lines.append(trade_stats.to_markdown())
        lines.append('')
    
    return '\n'.join(lines)

def _export_html(performance: pd.DataFrame, trade_stats: Optional[pd.DataFrame]) -> str:
    """HTML 导出"""
    lines = ['<h1>策略绩效报告</h1>', '']
    
    lines.append('<h2>绩效指标</h2>')
    lines.append(performance.to_html())
    lines.append('')
    
    if trade_stats is not None:
        lines.append('<h2>交易统计</h2>')
        lines.append(trade_stats.to_html())
        lines.append('')
    
    return '\n'.join(lines)

def _export_csv(performance: pd.DataFrame, trade_stats: Optional[pd.DataFrame]) -> str:
    """CSV 导出"""
    lines = ['# 绩效指标']
    lines.append(performance.to_csv())
    lines.append('')
    
    if trade_stats is not None:
        lines.append('# 交易统计')
        lines.append(trade_stats.to_csv())
    
    return '\n'.join(lines)
```

## 边界说明

### 该抽的内容

1. ✅ 通用绩效指标（年化收益、夏普、回撤等）
2. ✅ 通用交易统计（胜率、盈亏比、持仓天数等）
3. ✅ 标准回撤表（峰值、谷值、恢复点）
4. ✅ 基础图表模板（累计曲线、回撤图等）
5. ✅ 标准导出格式（Markdown、HTML、CSV）

### 不该抽的内容

1. ❌ 某策略专属的评价话术（如"该策略适合震荡市"）
2. ❌ 某研究专题专属图表（如"因子IC衰减图"）
3. ❌ 特定平台的分析器封装（Backtrader TradeAnalyzer 解析）
4. ❌ 商业化评价话术（如评级打分）

## 横向比较能力

通过统一接口，实现：

1. **标准化指标口径**
   - 所有策略使用相同的年化因子（252）
   - 统一的夏普、索提诺计算公式
   - 统一的Alpha/Beta回归方法

2. **统一输出格式**
   - DataFrame 结构一致
   - 列名标准化（中文/英文双语支持）
   - NaN 处理统一

3. **横向对比流程**
   ```python
   # 策略A结果
   perf_a = compute_performance(returns_a, benchmark_returns)
   
   # 策略B结果
   perf_b = compute_performance(returns_b, benchmark_returns)
   
   # 横向对比
   comparison = pd.concat([perf_a, perf_b], axis=1, keys=['策略A', '策略B'])
   
   # 导出对比表
   export_summary(comparison, format='markdown')
   ```

## 依赖库

- **必需**：pandas, numpy
- **推荐**：empyrical（高性能指标计算）
- **可选**：
  - statsmodels（回归计算Alpha/Beta）
  - plotly/matplotlib（图表可视化）
  - pyfolio（深度分析）

## 使用示例

```python
from strategy_kits.validation.reporting import (
    compute_performance,
    compute_trade_stats,
    build_tearsheet,
    export_summary,
)

# 基础绩效计算
returns = pd.Series([...], index=pd.date_range('2020-01-01', '2023-12-31'))
benchmark = pd.Series([...], index=returns.index)

perf = compute_performance(returns, benchmark)
print(perf)

# 交易统计
trades = pd.DataFrame({
    'datein': [...],
    'dateout': [...],
    'pricein': [...],
    'priceout': [...],
})
stats = compute_trade_stats(trades)
print(stats)

# 完整报告
report = build_tearsheet(returns, benchmark, trades)
print(report['performance_metrics'])
print(report['drawdown_table'])

# 导出
export_summary(perf, stats, output_path='strategy_report.md', format='markdown')
```

## 通过门槛验证

- ✅ 新策略结果能直接进统一口径
- ✅ 同类策略可快速横向比较
- ✅ 最小接口已定义清晰
- ✅ 骨架文件可直接使用
- ✅ 指标总表完整
- ✅ 交易统计表完整
- ✅ 图表需求清晰