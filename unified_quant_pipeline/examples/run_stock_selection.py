"""多因子选股策略运行示例

用法:
    python examples/run_stock_selection.py
    python examples/run_stock_selection.py --config configs/stock_selection.yaml
    python examples/run_stock_selection.py --dry-run
"""

import sys
import os
import argparse
import logging

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import PipelineConfig
from core.pipeline import MLPipeline
from utils.logger import setup_logging


def main() -> None:
    """运行多因子选股策略."""
    parser = argparse.ArgumentParser(description="多因子选股策略")
    parser.add_argument(
        "--config", default="configs/stock_selection.yaml", help="配置文件路径"
    )
    parser.add_argument("--dry-run", action="store_true", help="仅试运行，不执行回测")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    args = parser.parse_args()

    # 配置日志
    setup_logging(level=args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # 加载配置
        logger.info(f"Loading config from {args.config}")
        config = PipelineConfig.from_yaml(args.config)

        # 创建流水线
        pipeline = MLPipeline(config)

        # 运行
        logger.info("Starting pipeline...")
        result = pipeline.run(dry_run=args.dry_run)

        # 输出结果
        print("\n" + "=" * 50)
        print("选股结果")
        print("=" * 50)
        print(f"选中股票: {result['selected_stocks']}")
        print(f"权重: {result['weights']}")
        print(f"模型指标: {result['model_metrics']}")

        if result.get("performance_metrics"):
            print(f"\n回测指标:")
            for k, v in result["performance_metrics"].items():
                print(f"  {k}: {v}")

        logger.info("Pipeline completed successfully")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
