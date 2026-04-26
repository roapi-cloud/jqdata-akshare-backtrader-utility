"""
运行时核心 (Runtime Core)
=========================

回测执行的核心逻辑：
- Cerebro 组装
- Broker 配置
- 分析器挂载
- 结果收集

这是策略接入的最小入口：
```python
from strategy_kits.execution.backtrader_runtime import run_backtest

result = run_backtest(config, MyStrategyClass)
```
"""

import backtrader as bt
from typing import Type, Optional, Dict, Any, List
import pandas as pd

from .config import BacktraderConfig, CommissionConfig, AnalyzerConfig
from .datafeed import load_datafeeds, AkshareDataFeed
from .analyzers import TradeRecordAnalyzer, PerformanceAnalyzer, SQNAnalyzer


def build_broker(cerebro: bt.Cerebro, config: BacktraderConfig) -> Any:
    """
    构建并配置 Broker

    Args:
        cerebro: Cerebro 实例
        config: 回测配置

    Returns:
        配置好的 Broker 实例
    """
    # 设置初始资金
    cerebro.broker.setcash(config.initial_cash)

    # 设置滑点
    config.slippage.apply_to_broker(cerebro.broker)

    # 设置佣金（使用自定义 CommissionInfo）
    comminfo = _create_commission_info(config.commission)
    cerebro.broker.addcommissioninfo(comminfo)

    return cerebro.broker


def _create_commission_info(config: CommissionConfig) -> bt.CommInfoBase:
    """
    创建佣金信息对象

    支持 A 股模式：买入佣金 + 卖出佣金 + 印花税
    """
    class AShareCommission(bt.CommInfoBase):
        params = (
            ("stamp_duty", config.stamp_duty),
            ("stocklike", config.stocklike),
            ("commtype", bt.CommInfoBase.COMM_PERC),
            ("percabs", config.percabs),
        )

        def _getcommission(self, size, price, pseudoexec):
            if size > 0:  # 买入
                return abs(size) * price * self.p.commission
            elif size < 0:  # 卖出（加印花税）
                return abs(size) * price * (self.p.commission + self.p.stamp_duty)
            return 0

    return AShareCommission(commission=config.commission)


def build_analyzers(cerebro: bt.Cerebro, config: AnalyzerConfig):
    """
    挂载分析器

    Args:
        cerebro: Cerebro 实例
        config: 分析器配置
    """
    # 基础收益率
    if config.returns:
        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns", tann=252)

    # 夏普比率
    if config.sharpe:
        cerebro.addanalyzer(
            bt.analyzers.SharpeRatio,
            _name="sharpe",
            timeframe=bt.TimeFrame.Years,
            riskfreerate=0.04,
            annualize=True,
            factor=250
        )

    # 回撤
    if config.drawdown:
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

    # 交易分析
    if config.trade_analyzer:
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")

    # 交易成本
    if config.transactions:
        cerebro.addanalyzer(bt.analyzers.Transactions, _name="transactions")

    # SQN
    if config.sqn:
        cerebro.addanalyzer(SQNAnalyzer, _name="sqn")

    # 周期统计
    if config.period_stats:
        cerebro.addanalyzer(bt.analyzers.PeriodStats, _name="period_stats")

    # 时间序列收益率
    if config.time_return:
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="time_return")

    # 详细交易记录
    if config.trade_record:
        cerebro.addanalyzer(TradeRecordAnalyzer, _name="trade_record")

    # 自定义分析器
    for analyzer in config.custom_analyzers:
        cerebro.addanalyzer(analyzer)


def run_backtest(
    config: BacktraderConfig,
    strategy_cls: Type[bt.Strategy],
    data_bundle: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    运行回测（主入口）

    这是核心接口之一：
    - 输入：配置对象 + 策略类
    - 输出：回测结果字典

    Args:
        config: 回测配置
        strategy_cls: 策略类（继承自 bt.Strategy 或 JQ2BTBaseStrategy）
        data_bundle: 预加载数据（可选，用于外部数据传入）

    Returns:
        包含以下字段的字典：
        - 'cerebro': Cerebro 实例
        - 'strategy': 策略实例
        - 'results': 原始回测结果
        - 'portfolio_value': 最终组合价值
        - 'nav_series': 净值序列
        - 'metrics': 绩效指标 DataFrame
        - 'trades': 交易记录 DataFrame
        - 'analyzers': 分析器结果字典
    """
    # 初始化 Cerebro
    cerebro = bt.Cerebro()

    # 加载数据
    if data_bundle is not None:
        # 使用预加载数据
        for name, data in data_bundle.items():
            cerebro.adddata(data, name=name)
    else:
        # 从数据源加载
        datafeeds = load_datafeeds(
            symbols=config.symbols,
            start_date=config.start_date,
            end_date=config.end_date,
            data_config=config.data_config.__dict__ if config.data_config else None
        )
        for data in datafeeds:
            cerebro.adddata(data, name=data._name)

    # 配置 Broker
    build_broker(cerebro, config)

    # 挂载分析器
    build_analyzers(cerebro, config.analyzer_config)

    # 添加策略
    cerebro.addstrategy(strategy_cls, **config.strategy_params)

    # 打印初始资金
    if config.printlog:
        print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')

    # 运行回测
    results = cerebro.run(tradehistory=config.tradehistory)
    strategy = results[0]

    # 打印最终资金
    if config.printlog:
        print(f'Final Portfolio Value: {cerebro.broker.getvalue():.2f}')

    # 收集结果
    result_dict = _collect_results(cerebro, strategy, config)

    return result_dict


def _collect_results(
    cerebro: bt.Cerebro,
    strategy: bt.Strategy,
    config: BacktraderConfig
) -> Dict[str, Any]:
    """收集回测结果"""
    result = {
        'cerebro': cerebro,
        'strategy': strategy,
        'portfolio_value': cerebro.broker.getvalue(),
    }

    # 提取净值序列
    if hasattr(strategy, 'navs') and strategy.navs:
        navs = strategy.navs
    else:
        # 从分析器获取
        navs = []
        for i in range(strategy.datas[0].buflen()):
            navs.append(cerebro.broker.getvalue())

    # 构建日期索引
    dates = []
    for i in range(strategy.datas[0].buflen()):
        try:
            d = strategy.datas[0].datetime.date(-i)
            dates.insert(0, d)
        except:
            break

    # 确保长度一致
    min_len = min(len(navs), len(dates))
    nav_series = pd.Series(navs[:min_len], index=dates[:min_len])
    result['nav_series'] = nav_series

    # 提取分析器结果
    analyzers_result = {}

    # 交易记录
    if hasattr(strategy.analyzers, 'trade_record'):
        trade_analyzer = strategy.analyzers.trade_record
        trades_df = trade_analyzer.get_dataframe()
        result['trades'] = trades_df
        analyzers_result['trade_record'] = trade_analyzer.get_analysis()

    # 夏普
    if hasattr(strategy.analyzers, 'sharpe'):
        analyzers_result['sharpe'] = strategy.analyzers.sharpe.get_analysis()

    # 回撤
    if hasattr(strategy.analyzers, 'drawdown'):
        analyzers_result['drawdown'] = strategy.analyzers.drawdown.get_analysis()

    # SQN
    if hasattr(strategy.analyzers, 'sqn'):
        analyzers_result['sqn'] = strategy.analyzers.sqn.get_analysis()

    # 交易统计
    if hasattr(strategy.analyzers, 'trade_analyzer'):
        analyzers_result['trade_stats'] = strategy.analyzers.trade_analyzer.get_analysis()

    result['analyzers'] = analyzers_result

    # 计算绩效指标
    from .analyzers import analyze_performance

    # 获取基准
    benchmark_nav = None
    if config.benchmark:
        try:
            feed = AkshareDataFeed(cache_dir=config.data_config.cache_dir if config.data_config else './data_cache')
            benchmark_nav = feed.get_index_daily(
                config.benchmark,
                config.start_date,
                config.end_date
            )
        except Exception as e:
            print(f"基准加载失败: {e}")

    result['metrics'] = analyze_performance(nav_series, benchmark_nav)
    result['benchmark_nav'] = benchmark_nav

    return result


def quick_backtest(
    strategy_cls: Type[bt.Strategy],
    symbols: List[str],
    start_date: str,
    end_date: str,
    initial_cash: float = 1_000_000,
    **strategy_params
) -> Dict[str, Any]:
    """
    快速回测接口

    用于简单场景，无需完整配置对象

    Example:
        ```python
        result = quick_backtest(
            MyStrategy,
            symbols=['000001.XSHE', '600519.XSHG'],
            start_date='2020-01-01',
            end_date='2023-12-31'
        )
        ```
    """
    config = BacktraderConfig(
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        initial_cash=initial_cash,
        strategy_params=strategy_params
    )
    return run_backtest(config, strategy_cls)
