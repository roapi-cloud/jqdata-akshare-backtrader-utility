"""Configuration classes for factor preprocessing and scoring."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal, Dict, Union


@dataclass
class PreprocessConfig:
    """预处理配置类

    Attributes:
        fill_method: 缺失值填充方法 ("mean", "median", "zero")
        fill_group_col: 填充分组列名，None 表示不按组填充
        winsorize_method: 去极值方法 ("mad", "quantile")
        winsorize_n: MAD 方法的倍数
        winsorize_quantiles: 分位数方法的上下限
        standardize_method: 标准化方法 ("zscore", "rank")
        standardize_group_col: 标准化分组列名，None 表示不按组
    """
    fill_method: Literal["mean", "median", "zero"] = "median"
    fill_group_col: Optional[str] = "industry"
    winsorize_method: Literal["mad", "quantile"] = "mad"
    winsorize_n: float = 3.0
    winsorize_quantiles: tuple[float, float] = (0.01, 0.99)
    standardize_method: Literal["zscore", "rank"] = "zscore"
    standardize_group_col: Optional[str] = None

    def __post_init__(self):
        if self.winsorize_n <= 0:
            raise ValueError(f"winsorize_n must be positive, got {self.winsorize_n}")
        if not (0 < self.winsorize_quantiles[0] < self.winsorize_quantiles[1] < 1):
            raise ValueError(
                f"Invalid quantiles: {self.winsorize_quantiles}"
            )


@dataclass
class ScoreConfig:
    """打分配置类

    Attributes:
        method: 打分方法 ("equal", "ic", "icir", "pca", "custom")
        weights: 自定义权重字典，method="custom" 时使用
        direction: 因子方向，"ascending" 表示因子值越大分数越高
                  或传入字典为每个因子单独指定方向
        ic_window: IC/IR 计算窗口（仅对 ic/icir 方法有效）
        rank_first: 打分前是否先转秩
        ret_col: 收益率列名（用于 IC/IR 计算）
    """
    method: Literal["equal", "ic", "icir", "pca", "custom"] = "equal"
    weights: Optional[Dict[str, float]] = None
    direction: Union[str, Dict[str, str]] = "ascending"
    ic_window: int = 5
    rank_first: bool = True
    ret_col: Optional[str] = None

    def __post_init__(self):
        if self.ic_window <= 0:
            raise ValueError(f"ic_window must be positive, got {self.ic_window}")
        if self.method == "custom" and self.weights is None:
            raise ValueError("weights must be provided when method='custom'")
