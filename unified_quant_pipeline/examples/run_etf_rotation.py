"""ETF轮动策略运行示例

用法:
    python examples/run_etf_rotation.py
    python examples/run_etf_rotation.py --config configs/etf_rotation.yaml
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import PipelineConfig
from core.pipeline import MLPipeline
from utils.logger import setup_logging


def main() -> None:
    """运行ETF轮动策略."""
    parser = argparse.ArgumentParser(description="ETF轮动策略")
    parser.add_argument(
        "--config", default="configs/etf_rotation.yaml", help="配置文件路径"
    )
    parser.add_argument("--dry-run", action="store_true", help="仅试运行")
    args = parser.parse_args()

    setup_logging(level="INFO")
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Loading config from {args.config}")
        config = PipelineConfig.from_yaml(args.config)

        pipeline = MLPipeline(config)
        result = pipeline.run(dry_run=args.dry_run)

        print("\n" + "=" * 50)
        print("ETF轮动结果")
        print("=" * 50)
        print(f"选中ETF: {result['selected_stocks']}")
        print(f"权重: {result['weights']}")

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
