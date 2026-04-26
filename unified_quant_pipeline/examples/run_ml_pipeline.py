"""ML量化选股流水线示例

演示完整的机器学习量化选股流程：
1. 数据获取
2. 因子计算
3. 预处理
4. 标签构建
5. 模型训练
6. 预测选股

用法:
    python examples/run_ml_pipeline.py
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import PipelineConfig
from core.pipeline import MLPipeline
from utils.logger import setup_logging


def main() -> None:
    """运行ML量化选股流水线."""
    setup_logging(level="INFO")
    logger = logging.getLogger(__name__)

    # 使用默认配置
    config = PipelineConfig(
        data={"source": "akshare", "index": "000905"},
        factors={"factors": ["momentum_20", "volatility", "pe", "roe"]},
        model={"name": "random_forest", "params": {"n_estimators": 200}},
        portfolio={"n_stocks": 10},
    )

    pipeline = MLPipeline(config)

    # 试运行（不回测）
    logger.info("Running ML pipeline (dry run)...")
    result = pipeline.run(dry_run=True)

    print("\n" + "=" * 50)
    print("ML选股结果")
    print("=" * 50)
    print(f"选中股票: {result['selected_stocks']}")
    print(f"模型指标: {result['model_metrics']}")


if __name__ == "__main__":
    main()
