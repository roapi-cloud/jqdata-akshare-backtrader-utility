"""
全局配置文件
包含路径、日期范围、股票池、数据库连接等配置
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "output"
FACTOR_OUTPUT_DIR = DATA_DIR / "factors"
MAPPING_OUTPUT_DIR = DATA_DIR / "mappings"
REPORT_OUTPUT_DIR = DATA_DIR / "reports"
GENERATED_CODE_DIR = DATA_DIR / "generated_code"


@dataclass
class Settings:
    """全局配置类"""

    # ========== 路径配置 ==========
    project_root: Path = PROJECT_ROOT
    strategy_source_dir: Path = field(
        default_factory=lambda: Path(r"E:\jqdata_strategies")
    )
    factor_output_dir: Path = FACTOR_OUTPUT_DIR
    mapping_output_dir: Path = MAPPING_OUTPUT_DIR
    report_output_dir: Path = REPORT_OUTPUT_DIR
    generated_code_dir: Path = GENERATED_CODE_DIR

    # ========== 数据库配置 ==========
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'output' / 'factors.db'}"
    factor_table_prefix: str = "factor_"

    # ========== 聚宽数据源配置 ==========
    jq_username: str = ""
    jq_password: str = ""
    jq_host: str = "https://dataapi.joinquant.com"

    # ========== 日期范围配置 ==========
    start_date: str = "2015-01-01"
    end_date: str = "2024-12-31"
    frequency: str = "daily"  # daily, weekly, monthly, minute

    # ========== 股票池配置 ==========
    stock_pool: str = "all_a_shares"  # all_a_shares, hs300, zz500, zz1000, cyb, kcb
    stock_pool_list: List[str] = field(default_factory=list)
    exclude_st: bool = True
    exclude_new_stocks_days: int = 60  # 排除上市不足N天的股票

    # ========== 因子分类配置 ==========
    factor_categories_file: Path = field(
        default_factory=lambda: PROJECT_ROOT / "config" / "factor_categories.json"
    )

    # ========== 处理配置 ==========
    max_workers: int = 4
    batch_size: int = 50
    enable_cache: bool = True
    cache_dir: Path = field(default_factory=lambda: PROJECT_ROOT / ".cache")

    # ========== 验证配置 ==========
    factor_nan_threshold: float = 0.1  # 因子NaN比例超过此值则标记为异常
    factor_outlier_std: float = 5.0  # 超出均值N倍标准差视为异常值
    min_ic_threshold: float = 0.02  # 最小IC阈值

    # ========== 日志配置 ==========
    log_level: str = "INFO"
    log_file: Path = field(
        default_factory=lambda: PROJECT_ROOT / "output" / "pipeline.log"
    )

    def __post_init__(self):
        """初始化后确保所有目录存在"""
        for dir_path in [
            self.factor_output_dir,
            self.mapping_output_dir,
            self.report_output_dir,
            self.generated_code_dir,
            self.cache_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_stock_pool_codes(self) -> List[str]:
        """获取股票池代码列表"""
        if self.stock_pool_list:
            return self.stock_pool_list

        pool_mapping = {
            "all_a_shares": "全A股",
            "hs300": "沪深300",
            "zz500": "中证500",
            "zz1000": "中证1000",
            "cyb": "创业板",
            "kcb": "科创板",
        }
        return [pool_mapping.get(self.stock_pool, self.stock_pool)]


# 默认配置实例
default_settings = Settings()
