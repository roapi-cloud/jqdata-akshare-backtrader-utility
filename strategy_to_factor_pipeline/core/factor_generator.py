"""
因子信号生成模块

根据解析后的策略规则，生成每日选股信号。
支持二值信号、权重信号、排名信号，支持批量生成和增量更新。
"""

import os
import logging
from datetime import datetime
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class FactorGenerator:
    """因子信号生成器

    根据策略规则生成每日选股信号，支持多种信号类型和并行计算。

    Attributes:
        data_source: 数据源对象，需提供 get_stock_data 等方法
        output_dir: 信号输出目录
        cache_dir: 缓存目录
    """

    BINARY = "binary"
    WEIGHT = "weight"
    RANK = "rank"

    def __init__(self, data_source, output_dir: str):
        """初始化因子信号生成器

        Args:
            data_source: 数据源对象，需实现获取股票数据的方法
            output_dir: 信号文件输出目录
        """
        self.data_source = data_source
        self.output_dir = output_dir
        self.cache_dir = os.path.join(output_dir, "cache")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

    def generate_signals(
        self,
        strategy_rules: dict,
        date_range: pd.DatetimeIndex,
        stock_pool: list[str],
        signal_types: Optional[list[str]] = None,
        max_workers: int = 4,
        incremental: bool = True,
    ) -> pd.DataFrame:
        """批量生成多个策略、多个日期的信号

        Args:
            strategy_rules: 策略规则字典，格式:
                {
                    "strategy_name": {
                        "type": "stock_selection",
                        "conditions": [...],
                        "weight_method": "equal_weight",
                        ...
                    },
                    ...
                }
            date_range: 日期范围
            stock_pool: 股票池，股票代码列表
            signal_types: 需要生成的信号类型列表，默认全部生成
            max_workers: 并行工作进程数
            incremental: 是否增量生成（跳过已有缓存的日期）

        Returns:
            包含所有信号的 DataFrame，列: [date, stock_code, strategy_name, signal_type, value]
        """
        if signal_types is None:
            signal_types = [self.BINARY, self.WEIGHT, self.RANK]

        all_signals = []

        for strategy_name, rules in strategy_rules.items():
            logger.info(f"Generating signals for strategy: {strategy_name}")

            # 增量生成：加载已有信号，只处理缺失日期
            if incremental:
                cached = self._load_cached_signals(strategy_name)
                if not cached.empty:
                    existing_dates = set(cached["date"].unique())
                    dates_to_process = [
                        d for d in date_range if d not in existing_dates
                    ]
                    all_signals.append(cached)
                else:
                    dates_to_process = list(date_range)
            else:
                dates_to_process = list(date_range)

            if not dates_to_process:
                logger.info(f"All signals cached for strategy: {strategy_name}")
                continue

            # 按日期并行生成信号
            date_tasks = [
                (strategy_name, rules, date, stock_pool, signal_types)
                for date in dates_to_process
            ]

            if max_workers > 1 and len(date_tasks) > 1:
                day_signals = self._parallel_generate(date_tasks, max_workers)
            else:
                day_signals = [self._generate_day_signals(*task) for task in date_tasks]

            for sig in day_signals:
                if sig is not None and not sig.empty:
                    all_signals.append(sig)

        if not all_signals:
            return pd.DataFrame(
                columns=["date", "stock_code", "strategy_name", "signal_type", "value"]
            )

        result = pd.concat(all_signals, ignore_index=True)
        result = result.sort_values(
            ["date", "strategy_name", "signal_type", "stock_code"]
        ).reset_index(drop=True)
        return result

    def _parallel_generate(self, tasks: list, max_workers: int) -> list:
        """并行生成每日信号

        Args:
            tasks: 任务列表，每个元素为 (strategy_name, rules, date, stock_pool, signal_types)
            max_workers: 最大并行数

        Returns:
            每日信号 DataFrame 列表
        """
        results = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._generate_day_signals, *task): task
                for task in tasks
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    task = futures[future]
                    logger.error(f"Error generating signals for {task[2]}: {e}")
                    results.append(None)
        return results

    @staticmethod
    def _generate_day_signals(
        strategy_name: str,
        rules: dict,
        date: pd.Timestamp,
        stock_pool: list[str],
        signal_types: list[str],
    ) -> pd.DataFrame:
        """生成单个策略在单个日期的所有信号

        Args:
            strategy_name: 策略名称
            rules: 策略规则
            date: 日期
            stock_pool: 股票池
            signal_types: 信号类型列表

        Returns:
            信号 DataFrame
        """
        signals = []

        # 根据策略规则筛选股票
        selected_stocks = _apply_strategy_rules(rules, date, stock_pool)

        # 生成二值信号
        if FactorGenerator.BINARY in signal_types:
            binary_sig = FactorGenerator.generate_binary_signals(
                selected_stocks, stock_pool, date
            )
            if binary_sig is not None and not binary_sig.empty:
                binary_df = binary_sig.reset_index()
                binary_df.columns = ["stock_code", "value"]
                binary_df["date"] = date
                binary_df["strategy_name"] = strategy_name
                binary_df["signal_type"] = FactorGenerator.BINARY
                signals.append(binary_df)

        # 生成权重信号
        if FactorGenerator.WEIGHT in signal_types:
            weight_method = rules.get("weight_method", "equal_weight")
            portfolio_weights = _calculate_weights(
                selected_stocks, weight_method, rules
            )
            weight_sig = FactorGenerator.generate_weight_signals(
                portfolio_weights, date
            )
            if weight_sig is not None and not weight_sig.empty:
                weight_df = weight_sig.reset_index()
                weight_df.columns = ["stock_code", "value"]
                weight_df["date"] = date
                weight_df["strategy_name"] = strategy_name
                weight_df["signal_type"] = FactorGenerator.WEIGHT
                signals.append(weight_df)

        # 生成排名信号
        if FactorGenerator.RANK in signal_types:
            rank_method = rules.get("rank_method", "equal_rank")
            stock_ranks = _calculate_ranks(selected_stocks, rank_method, rules)
            rank_sig = FactorGenerator.generate_rank_signals(stock_ranks, date)
            if rank_sig is not None and not rank_sig.empty:
                rank_df = rank_sig.reset_index()
                rank_df.columns = ["stock_code", "value"]
                rank_df["date"] = date
                rank_df["strategy_name"] = strategy_name
                rank_df["signal_type"] = FactorGenerator.RANK
                signals.append(rank_df)

        if not signals:
            return pd.DataFrame()

        return pd.concat(signals, ignore_index=True)

    @staticmethod
    def generate_binary_signals(
        selected_stocks: list[str],
        all_stocks: list[str],
        date: pd.Timestamp,
    ) -> pd.Series:
        """生成二值信号（1=选中，0=未选中）

        Args:
            selected_stocks: 被策略选中的股票代码列表
            all_stocks: 全量股票代码列表
            date: 信号日期

        Returns:
            二值信号 Series，index 为股票代码，value 为 0 或 1
        """
        selected_set = set(selected_stocks)
        signals = pd.Series(
            [1.0 if stock in selected_set else 0.0 for stock in all_stocks],
            index=all_stocks,
            name=str(date),
            dtype=float,
        )
        return signals

    @staticmethod
    def generate_weight_signals(
        portfolio_weights: dict[str, float],
        date: pd.Timestamp,
    ) -> pd.Series:
        """生成权重信号（持仓权重）

        Args:
            portfolio_weights: 股票权重字典 {stock_code: weight}
            date: 信号日期

        Returns:
            权重信号 Series，index 为股票代码，value 为权重值
        """
        if not portfolio_weights:
            return pd.Series(name=str(date), dtype=float)

        signals = pd.Series(portfolio_weights, name=str(date), dtype=float)
        signals.index.name = "stock_code"
        return signals

    @staticmethod
    def generate_rank_signals(
        stock_ranks: dict[str, float],
        date: pd.Timestamp,
    ) -> pd.Series:
        """生成排名信号（股票在策略中的排名）

        Args:
            stock_ranks: 股票排名字典 {stock_code: rank}
            date: 信号日期

        Returns:
            排名信号 Series，index 为股票代码，value 为排名值
        """
        if not stock_ranks:
            return pd.Series(name=str(date), dtype=float)

        signals = pd.Series(stock_ranks, name=str(date), dtype=float)
        signals.index.name = "stock_code"
        return signals

    def save_signals(
        self,
        signals: pd.DataFrame,
        strategy_name: str,
        output_path: Optional[str] = None,
    ) -> str:
        """保存信号到文件

        Args:
            signals: 信号 DataFrame
            strategy_name: 策略名称
            output_path: 输出路径，默认使用 output_dir/strategy_name/signals.parquet

        Returns:
            实际保存的文件路径
        """
        if output_path is None:
            strategy_dir = os.path.join(self.output_dir, strategy_name)
            os.makedirs(strategy_dir, exist_ok=True)
            output_path = os.path.join(strategy_dir, "signals.parquet")

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存为 parquet 格式（高效存储）
        signals.to_parquet(output_path, index=False)

        # 同时保存到缓存
        cache_path = os.path.join(self.cache_dir, f"{strategy_name}_cache.parquet")
        signals.to_parquet(cache_path, index=False)

        logger.info(f"Signals saved to {output_path}, rows: {len(signals)}")
        return output_path

    def load_cached_signals(self, strategy_name: str) -> pd.DataFrame:
        """加载缓存的信号

        Args:
            strategy_name: 策略名称

        Returns:
            缓存的信号 DataFrame，若无缓存则返回空 DataFrame
        """
        return self._load_cached_signals(strategy_name)

    def _load_cached_signals(self, strategy_name: str) -> pd.DataFrame:
        """内部方法：加载缓存信号

        Args:
            strategy_name: 策略名称

        Returns:
            缓存的信号 DataFrame
        """
        cache_path = os.path.join(self.cache_dir, f"{strategy_name}_cache.parquet")
        if os.path.exists(cache_path):
            try:
                df = pd.read_parquet(cache_path)
                logger.info(
                    f"Loaded cached signals for {strategy_name}, rows: {len(df)}"
                )
                return df
            except Exception as e:
                logger.warning(f"Failed to load cache for {strategy_name}: {e}")
        return pd.DataFrame(
            columns=["date", "stock_code", "strategy_name", "signal_type", "value"]
        )

    def get_signal_summary(self, signals: pd.DataFrame) -> pd.DataFrame:
        """生成信号摘要统计

        Args:
            signals: 信号 DataFrame

        Returns:
            摘要 DataFrame，包含每个策略每日的信号统计
        """
        if signals.empty:
            return pd.DataFrame()

        summary = (
            signals.groupby(["date", "strategy_name", "signal_type"])
            .agg(
                total_stocks=("stock_code", "count"),
                selected_count=("value", lambda x: (x > 0).sum()),
                mean_value=("value", "mean"),
                std_value=("value", "std"),
            )
            .reset_index()
        )

        return summary


def _apply_strategy_rules(
    rules: dict,
    date: pd.Timestamp,
    stock_pool: list[str],
) -> list[str]:
    """根据策略规则筛选股票

    Args:
        rules: 策略规则
        date: 日期
        stock_pool: 股票池

    Returns:
        选中的股票代码列表
    """
    conditions = rules.get("conditions", [])

    if not conditions:
        # 无具体条件时，返回整个股票池
        return stock_pool

    # 从数据源获取股票数据
    stock_data = _fetch_stock_data(rules, date, stock_pool)

    if stock_data is None or stock_data.empty:
        return []

    selected = stock_data.copy()

    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator", ">")
        threshold = condition.get("threshold")

        if field is None or field not in selected.columns:
            continue

        if threshold is None:
            continue

        if operator == ">":
            selected = selected[selected[field] > threshold]
        elif operator == ">=":
            selected = selected[selected[field] >= threshold]
        elif operator == "<":
            selected = selected[selected[field] < threshold]
        elif operator == "<=":
            selected = selected[selected[field] <= threshold]
        elif operator == "==":
            selected = selected[selected[field] == threshold]
        elif operator == "!=":
            selected = selected[selected[field] != threshold]
        elif operator == "in":
            selected = selected[selected[field].isin(threshold)]
        elif operator == "top_n":
            selected = selected.nlargest(int(threshold), field)
        elif operator == "bottom_n":
            selected = selected.nsmallest(int(threshold), field)

    return (
        selected.index.tolist()
        if hasattr(selected, "index")
        else selected.get("stock_code", []).tolist()
    )


def _fetch_stock_data(
    rules: dict,
    date: pd.Timestamp,
    stock_pool: list[str],
) -> Optional[pd.DataFrame]:
    """从数据源获取股票数据

    Args:
        rules: 策略规则
        date: 日期
        stock_pool: 股票池

    Returns:
        股票数据 DataFrame
    """
    required_fields = rules.get("required_fields", [])

    # 尝试从 data_source 获取数据
    # 这里假设 data_source 有 get_stock_data 方法
    # 实际使用时需要根据具体数据源实现
    try:
        if hasattr(rules, "data_source") and hasattr(
            rules.data_source, "get_stock_data"
        ):
            return rules.data_source.get_stock_data(date, stock_pool, required_fields)
    except Exception as e:
        logger.warning(f"Failed to fetch stock data: {e}")

    return None


def _calculate_weights(
    selected_stocks: list[str],
    weight_method: str,
    rules: dict,
) -> dict[str, float]:
    """计算持仓权重

    Args:
        selected_stocks: 选中的股票列表
        weight_method: 权重计算方法
        rules: 策略规则

    Returns:
        权重字典 {stock_code: weight}
    """
    if not selected_stocks:
        return {}

    n = len(selected_stocks)

    if weight_method == "equal_weight":
        weight = 1.0 / n
        return {stock: weight for stock in selected_stocks}

    elif weight_method == "market_cap_weight":
        # 按市值加权
        market_caps = rules.get("market_caps", {})
        total_cap = sum(market_caps.get(s, 1.0) for s in selected_stocks)
        return {s: market_caps.get(s, 1.0) / total_cap for s in selected_stocks}

    elif weight_method == "inverse_volatility":
        # 按波动率倒数加权
        volatilities = rules.get("volatilities", {})
        inv_vols = {
            s: 1.0 / max(volatilities.get(s, 1.0), 1e-6) for s in selected_stocks
        }
        total = sum(inv_vols.values())
        return {s: v / total for s, v in inv_vols.items()}

    elif weight_method == "custom":
        # 自定义权重
        custom_weights = rules.get("custom_weights", {})
        total = sum(custom_weights.get(s, 0.0) for s in selected_stocks)
        if total > 0:
            return {s: custom_weights.get(s, 0.0) / total for s in selected_stocks}
        return {s: 1.0 / n for s in selected_stocks}

    else:
        # 默认等权
        weight = 1.0 / n
        return {stock: weight for stock in selected_stocks}


def _calculate_ranks(
    selected_stocks: list[str],
    rank_method: str,
    rules: dict,
) -> dict[str, float]:
    """计算股票排名

    Args:
        selected_stocks: 选中的股票列表
        rank_method: 排名方法
        rules: 策略规则

    Returns:
        排名字典 {stock_code: rank}
    """
    if not selected_stocks:
        return {}

    if rank_method == "equal_rank":
        return {stock: float(i + 1) for i, stock in enumerate(selected_stocks)}

    elif rank_method == "score_rank":
        # 按得分排名
        scores = rules.get("scores", {})
        sorted_stocks = sorted(
            selected_stocks,
            key=lambda s: scores.get(s, 0.0),
            reverse=True,
        )
        return {stock: float(i + 1) for i, stock in enumerate(sorted_stocks)}

    elif rank_method == "percentile_rank":
        # 百分位排名
        n = len(selected_stocks)
        return {stock: (i + 1) / n for i, stock in enumerate(selected_stocks)}

    else:
        return {stock: float(i + 1) for i, stock in enumerate(selected_stocks)}
