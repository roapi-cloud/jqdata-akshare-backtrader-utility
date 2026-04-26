import logging
from typing import Any, Dict, List, Optional
from datetime import date
import pandas as pd
import joblib
from pathlib import Path

from .config import PipelineConfig
from .base import (
    BaseFactor,
    BasePreprocessor,
    BaseLabelBuilder,
    BaseModel,
    BaseStrategy,
)
from .registry import (
    FACTOR_REGISTRY,
    PREPROCESSOR_REGISTRY,
    LABEL_REGISTRY,
    MODEL_REGISTRY,
    STRATEGY_REGISTRY,
)

logger = logging.getLogger(__name__)


class MLPipeline:
    """ML量化选股流水线编排器。

    负责协调数据获取、因子计算、预处理、标签构建、模型训练/预测、
    组合构建和回测评估的完整流程。支持滚动窗口训练和定期调仓。

    Attributes:
        config: 流水线配置。
        factors: 因子实例列表。
        preprocessor: 预处理器实例。
        label_builder: 标签构建器实例。
        model: 模型实例。
        strategy: 策略实例。
        results: 流水线运行结果。
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.factors: List[BaseFactor] = []
        self.preprocessor: Optional[BasePreprocessor] = None
        self.label_builder: Optional[BaseLabelBuilder] = None
        self.model: Optional[BaseModel] = None
        self.strategy: Optional[BaseStrategy] = None
        self.results: Dict[str, Any] = {}
        self._build_pipeline()

    def _build_pipeline(self) -> None:
        """根据配置自动组装各组件。

        从注册中心获取配置的因子、预处理器、标签构建器、模型和策略实例。
        """
        self._build_factors()
        self._build_preprocessor()
        self._build_label_builder()
        self._build_model()
        self._build_strategy()
        logger.info("Pipeline components built successfully.")

    def _build_factors(self) -> None:
        """构建因子实例列表。"""
        for factor_name in self.config.factors:
            factor_cls = FACTOR_REGISTRY.get(factor_name)
            self.factors.append(factor_cls(name=factor_name))
        logger.info(f"Built {len(self.factors)} factors: {self.config.factors}")

    def _build_preprocessor(self) -> None:
        """构建预处理器实例。"""
        preprocess_config = self.config.preprocess
        preprocessor_cls = PREPROCESSOR_REGISTRY.get("default")
        self.preprocessor = preprocessor_cls(
            name="default", config=preprocess_config.__dict__
        )

    def _build_label_builder(self) -> None:
        """构建标签构建器实例。"""
        label_config = self.config.label
        label_builder_cls = LABEL_REGISTRY.get(label_config.method)
        self.label_builder = label_builder_cls(
            name=label_config.method, config=label_config.__dict__
        )

    def _build_model(self) -> None:
        """构建模型实例。"""
        model_config = self.config.model
        model_cls = MODEL_REGISTRY.get(model_config.name)
        self.model = model_cls(name=model_config.name, config=model_config.params)

    def _build_strategy(self) -> None:
        """构建策略实例。"""
        portfolio_config = self.config.portfolio
        strategy_cls = STRATEGY_REGISTRY.get(portfolio_config.weighting)
        self.strategy = strategy_cls(
            name=portfolio_config.weighting, config=portfolio_config.__dict__
        )

    def _get_trade_dates(self) -> List[date]:
        """获取调仓日期列表。

        Returns:
            按时间排序的调仓日期列表。
        """
        from jqdatasdk import get_trade_days

        start = self.config.data.start_date
        end = self.config.data.end_date
        freq = self.config.data.frequency

        trade_days = get_trade_days(start_date=start, end_date=end)
        if freq == "monthly":
            trade_days = self._resample_to_monthly(trade_days)
        elif freq == "weekly":
            trade_days = self._resample_to_weekly(trade_days)

        return [pd.Timestamp(d).date() for d in trade_days]

    def _resample_to_monthly(self, trade_days: pd.Index) -> List[pd.Timestamp]:
        """将交易日重采样到月度频率。"""
        trade_days = pd.to_datetime(trade_days)
        monthly = trade_days.groupby(trade_days.to_period("M")).last()
        return monthly.tolist()

    def _resample_to_weekly(self, trade_days: pd.Index) -> List[pd.Timestamp]:
        """将交易日重采样到周度频率。"""
        trade_days = pd.to_datetime(trade_days)
        weekly = trade_days.groupby(trade_days.to_period("W")).last()
        return weekly.tolist()

    def _get_stock_pool(self, trade_date: date) -> List[str]:
        """获取指定日期的股票池。

        Args:
            trade_date: 交易日期。

        Returns:
            符合条件的股票代码列表。
        """
        from jqdatasdk import get_index_stocks, get_security_info

        index_stocks = get_index_stocks(self.config.data.index, trade_date)
        list_days = self.config.data.list_days

        valid_stocks = []
        for stock in index_stocks:
            info = get_security_info(stock)
            days_listed = (
                pd.Timestamp(trade_date) - pd.Timestamp(info.start_date)
            ).days
            if days_listed >= list_days:
                valid_stocks.append(stock)

        return valid_stocks

    def _compute_factors(self, stocks: List[str], trade_date: date) -> pd.DataFrame:
        """计算所有因子。

        Args:
            stocks: 股票代码列表。
            trade_date: 交易日期。

        Returns:
            因子值数据框，索引为股票代码。
        """
        factor_dfs = []
        for factor in self.factors:
            df = factor.compute(stocks, trade_date)
            factor_dfs.append(df)

        if factor_dfs:
            result = pd.concat(factor_dfs, axis=1)
        else:
            result = pd.DataFrame(index=stocks)

        return result

    def _preprocess(self, factor_df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
        """执行因子预处理流程。

        Args:
            factor_df: 原始因子数据框。
            trade_date: 交易日期。

        Returns:
            预处理后的因子数据框。
        """
        if self.preprocessor is None:
            return factor_df

        df = self.preprocessor.winsorize(factor_df)
        df = self.preprocessor.fill_na(df)
        df = self.preprocessor.neutralize(df)
        if self.config.preprocess.standardize:
            df = self.preprocessor.standardize(df)

        return df

    def _build_labels(self, stocks: List[str], trade_date: date) -> pd.Series:
        """构建训练标签。

        Args:
            stocks: 股票代码列表。
            trade_date: 交易日期。

        Returns:
            标签序列。
        """
        if self.label_builder is None:
            return pd.Series(dtype=float)

        return self.label_builder.build(
            stocks,
            trade_date,
            holding_period=self.config.label.holding_period,
        )

    def _train_model(self, X: pd.DataFrame, y: pd.Series) -> None:
        """训练模型。

        Args:
            X: 训练特征。
            y: 训练标签。
        """
        if self.model is None:
            raise ValueError("Model is not initialized.")

        self.model.train(X, y)
        logger.info(
            f"Model trained on {len(X)} samples with {len(X.columns)} features."
        )

    def _predict(self, X: pd.DataFrame) -> pd.Series:
        """执行预测。

        Args:
            X: 预测特征。

        Returns:
            预测值序列。
        """
        if self.model is None:
            raise ValueError("Model is not initialized.")

        return self.model.predict(X)

    def _build_portfolio(
        self, predictions: pd.Series, trade_date: date
    ) -> Dict[str, float]:
        """构建投资组合。

        Args:
            predictions: 预测值序列。
            trade_date: 交易日期。

        Returns:
            股票权重字典。
        """
        if self.strategy is None:
            raise ValueError("Strategy is not initialized.")

        selected = self.strategy.select_stocks(predictions, trade_date)
        weights = self.strategy.compute_weights(selected, predictions, trade_date)
        return weights

    def _run_backtest(self, portfolio_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行回测评估。

        Args:
            portfolio_history: 历史组合权重列表。

        Returns:
            回测结果字典。
        """
        logger.info("Running backtest evaluation...")
        results = {
            "total_return": 0.0,
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "portfolio_history": portfolio_history,
        }
        return results

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """执行完整流水线。

        Args:
            dry_run: 是否为试运行模式（仅打印日志，不执行实际操作）。

        Returns:
            流水线运行结果。
        """
        trade_dates = self._get_trade_dates()
        logger.info(f"Pipeline running on {len(trade_dates)} trade dates.")

        portfolio_history = []
        train_window = self.config.model.train_window

        for i, trade_date in enumerate(trade_dates):
            logger.info(f"Processing trade date: {trade_date}")

            if dry_run:
                logger.info(f"[DRY RUN] Would process {trade_date}")
                continue

            stocks = self._get_stock_pool(trade_date)
            if not stocks:
                logger.warning(f"No valid stocks on {trade_date}, skipping.")
                continue

            factor_df = self._compute_factors(stocks, trade_date)
            factor_df = self._preprocess(factor_df, trade_date)

            if self.model is not None and self.model.is_fitted:
                predictions = self._predict(factor_df)
            else:
                predictions = pd.Series(0.0, index=stocks)

            weights = self._build_portfolio(predictions, trade_date)
            portfolio_history.append({"date": trade_date, "weights": weights})

            labels = self._build_labels(stocks, trade_date)
            if not labels.empty and len(labels) > 0:
                self._train_model(factor_df.loc[labels.index], labels)

        self.results = self._run_backtest(portfolio_history)
        return self.results

    def save(self, path: str) -> None:
        """保存流水线状态。

        Args:
            path: 保存路径。
        """
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        state = {
            "config": self.config,
            "results": self.results,
        }
        joblib.dump(state, save_path / "pipeline_state.pkl")

        if self.model is not None and self.model.is_fitted:
            self.model.save(str(save_path / "model.pkl"))

        logger.info(f"Pipeline state saved to {path}")

    def load(self, path: str) -> "MLPipeline":
        """加载流水线状态。

        Args:
            path: 保存路径。

        Returns:
            当前流水线实例。
        """
        load_path = Path(path)

        state = joblib.load(load_path / "pipeline_state.pkl")
        self.config = state["config"]
        self.results = state["results"]

        model_path = load_path / "model.pkl"
        if model_path.exists() and self.model is not None:
            self.model.load(str(model_path))

        logger.info(f"Pipeline state loaded from {path}")
        return self

    def train(self, output_dir: str = "models") -> None:
        """训练模型并保存到指定目录。

        Args:
            output_dir: 模型保存目录。
        """
        trade_dates = self._get_trade_dates()
        train_window = self.config.model.train_window

        logger.info(f"Training model with window size {train_window}")

        for i, trade_date in enumerate(trade_dates):
            stocks = self._get_stock_pool(trade_date)
            if not stocks:
                continue

            factor_df = self._compute_factors(stocks, trade_date)
            factor_df = self._preprocess(factor_df, trade_date)

            labels = self._build_labels(stocks, trade_date)
            if labels.empty:
                continue

            X = factor_df.loc[labels.index]
            y = labels
            self._train_model(X, y)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.save(str(output_path))
        logger.info(f"Model trained and saved to {output_dir}")

    def backtest(
        self, model_path: str, output_dir: str = "output/backtest"
    ) -> Dict[str, Any]:
        """加载模型并运行回测。

        Args:
            model_path: 已训练模型的路径。
            output_dir: 回测结果输出目录。

        Returns:
            回测结果字典。
        """
        self.load(model_path)

        trade_dates = self._get_trade_dates()
        portfolio_history = []

        for trade_date in trade_dates:
            stocks = self._get_stock_pool(trade_date)
            if not stocks:
                continue

            factor_df = self._compute_factors(stocks, trade_date)
            factor_df = self._preprocess(factor_df, trade_date)

            if self.model is not None and self.model.is_fitted:
                predictions = self._predict(factor_df)
                weights = self._build_portfolio(predictions, trade_date)
                portfolio_history.append({"date": str(trade_date), "weights": weights})

        self.results = self._run_backtest(portfolio_history)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        import json

        with open(output_path / "backtest_results.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, default=str, indent=2, ensure_ascii=False)

        logger.info(f"Backtest results saved to {output_dir}")
        return self.results

    def predict(self, model_path: str, date: Optional[str] = None) -> List[str]:
        """加载模型并执行预测选股。

        Args:
            model_path: 模型路径。
            date: 预测日期，格式 YYYY-MM-DD，默认为最新交易日。

        Returns:
            预测选中的股票代码列表。
        """
        self.load(model_path)

        if date is None:
            from jqdatasdk import get_trade_days

            trade_days = get_trade_days(end_date=date)
            date = trade_days[-1]

        trade_date = pd.Timestamp(date).date()
        stocks = self._get_stock_pool(trade_date)
        factor_df = self._compute_factors(stocks, trade_date)
        factor_df = self._preprocess(factor_df, trade_date)

        if self.model is not None and self.model.is_fitted:
            predictions = self._predict(factor_df)
            weights = self._build_portfolio(predictions, trade_date)
            return list(weights.keys())

        return []

    def print_report(self) -> None:
        """打印回测报告到控制台。"""
        if not self.results:
            print("No backtest results available. Run backtest first.")
            return

        print("=" * 50)
        print("回测报告")
        print("=" * 50)
        print(f"总收益率:       {self.results.get('total_return', 0):.2%}")
        print(f"年化收益率:     {self.results.get('annual_return', 0):.2%}")
        print(f"最大回撤:       {self.results.get('max_drawdown', 0):.2%}")
        print(f"夏普比率:       {self.results.get('sharpe_ratio', 0):.2f}")
        print("=" * 50)
