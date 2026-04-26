from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import date
import pandas as pd


class BaseComponent(ABC):
    """所有量化ML流水线组件的根基类。

    定义组件的标准接口，包括配置管理、拟合、转换和预测方法。
    所有具体组件应继承此类并实现相应的抽象方法。
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._is_fitted = False

    @abstractmethod
    def fit(
        self, X: pd.DataFrame, y: Optional[pd.Series] = None, **kwargs
    ) -> "BaseComponent":
        """拟合组件参数。

        Args:
            X: 输入特征数据框。
            y: 目标标签序列（可选）。
            **kwargs: 其他拟合参数。

        Returns:
            拟合后的组件实例。
        """
        ...

    @abstractmethod
    def transform(self, X: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """转换输入数据。

        Args:
            X: 输入数据框。
            **kwargs: 其他转换参数。

        Returns:
            转换后的数据框。
        """
        ...

    @abstractmethod
    def predict(self, X: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """基于输入数据进行预测。

        Args:
            X: 输入特征数据框。
            **kwargs: 其他预测参数。

        Returns:
            预测结果数据框。
        """
        ...

    def fit_transform(
        self, X: pd.DataFrame, y: Optional[pd.Series] = None, **kwargs
    ) -> pd.DataFrame:
        """拟合并转换数据。

        Args:
            X: 输入特征数据框。
            y: 目标标签序列（可选）。
            **kwargs: 其他参数。

        Returns:
            转换后的数据框。
        """
        return self.fit(X, y, **kwargs).transform(X, **kwargs)

    @property
    def is_fitted(self) -> bool:
        """返回组件是否已拟合。"""
        return self._is_fitted

    def get_params(self) -> Dict[str, Any]:
        """获取组件配置参数。

        Returns:
            配置参数字典。
        """
        return self.config.copy()

    def set_params(self, **params) -> "BaseComponent":
        """设置组件配置参数。

        Args:
            **params: 要设置的参数键值对。

        Returns:
            当前组件实例。
        """
        self.config.update(params)
        return self


class BaseFactor(BaseComponent):
    """因子计算基类。

    定义因子计算的标准接口，子类需实现 `compute` 方法来计算特定因子值。
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)

    @abstractmethod
    def compute(self, stocks: List[str], date: date, **kwargs) -> pd.DataFrame:
        """计算指定股票池在指定日期的因子值。

        Args:
            stocks: 股票代码列表。
            date: 计算日期。
            **kwargs: 其他计算参数。

        Returns:
            因子值数据框，索引为股票代码，列为因子名称。
        """
        ...

    def fit(
        self, X: pd.DataFrame, y: Optional[pd.Series] = None, **kwargs
    ) -> "BaseFactor":
        """因子通常无需拟合，直接返回自身。"""
        self._is_fitted = True
        return self

    def transform(self, X: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """因子通常无需转换，直接返回输入。"""
        return X

    def predict(self, X: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """因子通常无需预测，直接返回输入。"""
        return X


class BasePreprocessor(BaseComponent):
    """数据预处理基类。

    封装因子数据的去极值、缺失值填充、中性化和标准化等预处理流程。
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)

    @abstractmethod
    def winsorize(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """去极值处理。

        Args:
            df: 输入因子数据框。
            **kwargs: 去极值参数。

        Returns:
            去极值后的数据框。
        """
        ...

    @abstractmethod
    def fill_na(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """缺失值填充。

        Args:
            df: 输入因子数据框。
            **kwargs: 填充参数。

        Returns:
            填充后的数据框。
        """
        ...

    @abstractmethod
    def neutralize(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """因子中性化。

        Args:
            df: 输入因子数据框。
            **kwargs: 中性化参数。

        Returns:
            中性化后的数据框。
        """
        ...

    @abstractmethod
    def standardize(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """因子标准化。

        Args:
            df: 输入因子数据框。
            **kwargs: 标准化参数。

        Returns:
            标准化后的数据框。
        """
        ...


class BaseLabelBuilder(BaseComponent):
    """标签构建基类。

    定义如何基于未来收益构建训练标签，支持分类标签和回归标签。
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)

    @abstractmethod
    def build(
        self, stocks: List[str], date: date, holding_period: int = 20, **kwargs
    ) -> pd.Series:
        """构建指定日期的训练标签。

        Args:
            stocks: 股票代码列表。
            date: 标签构建基准日期。
            holding_period: 持有期（交易日）。
            **kwargs: 其他构建参数。

        Returns:
            标签序列，索引为股票代码。
        """
        ...


class BaseModel(BaseComponent):
    """机器学习模型基类。

    封装模型的训练、预测、评估和序列化接口。
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.feature_names: Optional[List[str]] = None

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> "BaseModel":
        """训练模型。

        Args:
            X: 训练特征数据框。
            y: 训练标签序列。
            **kwargs: 其他训练参数。

        Returns:
            训练后的模型实例。
        """
        ...

    @abstractmethod
    def predict(self, X: pd.DataFrame, **kwargs) -> pd.Series:
        """预测。

        Args:
            X: 预测特征数据框。
            **kwargs: 其他预测参数。

        Returns:
            预测值序列。
        """
        ...

    @abstractmethod
    def evaluate(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, float]:
        """评估模型性能。

        Args:
            X: 测试特征数据框。
            y: 测试标签序列。
            **kwargs: 其他评估参数。

        Returns:
            评估指标字典。
        """
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        """保存模型到指定路径。

        Args:
            path: 保存路径。
        """
        ...

    @abstractmethod
    def load(self, path: str) -> "BaseModel":
        """从指定路径加载模型。

        Args:
            path: 模型路径。

        Returns:
            加载后的模型实例。
        """
        ...

    @abstractmethod
    def feature_importance(self) -> pd.DataFrame:
        """获取特征重要性。

        Returns:
            特征重要性数据框。
        """
        ...


class BaseStrategy(BaseComponent):
    """量化策略基类。

    定义策略的调仓逻辑、组合构建和订单生成接口。
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)

    @abstractmethod
    def select_stocks(self, predictions: pd.Series, date: date, **kwargs) -> List[str]:
        """基于模型预测选择目标股票。

        Args:
            predictions: 模型预测值序列，索引为股票代码。
            date: 调仓日期。
            **kwargs: 其他选择参数。

        Returns:
            选中的股票代码列表。
        """
        ...

    @abstractmethod
    def compute_weights(
        self, stocks: List[str], predictions: pd.Series, date: date, **kwargs
    ) -> Dict[str, float]:
        """计算组合中各股票的权重。

        Args:
            stocks: 选中的股票代码列表。
            predictions: 模型预测值序列。
            date: 调仓日期。
            **kwargs: 其他权重计算参数。

        Returns:
            股票权重字典，键为股票代码，值为权重。
        """
        ...

    @abstractmethod
    def rebalance(
        self,
        current_portfolio: Dict[str, float],
        target_weights: Dict[str, float],
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """生成调仓订单。

        Args:
            current_portfolio: 当前持仓字典。
            target_weights: 目标权重字典。
            **kwargs: 其他调仓参数。

        Returns:
            订单列表。
        """
        ...
