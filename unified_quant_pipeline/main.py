"""统一量化策略流水线 - 主入口

用法:
    python main.py                          # 使用默认配置
    python main.py --config config.yaml     # 指定配置
    python main.py --strategy stock         # 使用内置策略
    python main.py --dry-run                # 试运行
    python main.py --list-strategies        # 列出可用策略

内置策略:
    stock    - 多因子选股
    etf      - ETF轮动
    ml       - ML流水线
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import PipelineConfig
from core.pipeline import MLPipeline
from utils.logger import setup_logging

# 内置策略配置映射
BUILTIN_STRATEGIES: dict[str, str] = {
    "stock": "configs/stock_selection.yaml",
    "etf": "configs/etf_rotation.yaml",
    "ml": "configs/default.yaml",
}


def list_strategies() -> None:
    """列出可用策略."""
    print("\n可用策略:")
    print("-" * 40)
    for name, config in BUILTIN_STRATEGIES.items():
        print(f"  {name:10s} - {config}")
    print()


def main() -> None:
    """运行统一量化策略流水线."""
    parser = argparse.ArgumentParser(
        description="统一量化策略流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        choices=list(BUILTIN_STRATEGIES.keys()),
        help="使用内置策略",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅试运行，不执行回测")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    parser.add_argument("--list-strategies", action="store_true", help="列出可用策略")
    parser.add_argument(
        "--save-model", type=str, default=None, help="保存模型到指定路径"
    )
    parser.add_argument(
        "--load-model", type=str, default=None, help="从指定路径加载模型"
    )

    args = parser.parse_args()

    # 列出策略
    if args.list_strategies:
        list_strategies()
        return

    # 配置日志
    setup_logging(level=args.log_level)
    logger = logging.getLogger(__name__)

    # 确定配置文件
    if args.config:
        config_path = args.config
    elif args.strategy:
        config_path = BUILTIN_STRATEGIES[args.strategy]
    else:
        config_path = "configs/default.yaml"

    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    try:
        # 加载配置
        logger.info(f"Loading config: {config_path}")
        config = PipelineConfig.from_yaml(config_path)

        # 创建流水线
        pipeline = MLPipeline(config)

        # 加载模型（如果指定）
        if args.load_model:
            pipeline = MLPipeline.load(args.load_model)
            logger.info(f"Model loaded from {args.load_model}")

        # 运行
        logger.info(f"Starting pipeline (dry_run={args.dry_run})...")
        result = pipeline.run(dry_run=args.dry_run)

        # 输出结果
        print("\n" + "=" * 60)
        print("流水线运行结果")
        print("=" * 60)
        print(f"选中股票: {result['selected_stocks']}")
        print(f"权重: {result['weights']}")

        if result.get("model_metrics"):
            print(f"\n模型指标:")
            for k, v in result["model_metrics"].items():
                print(f"  {k}: {v:.4f}")

        if result.get("performance_metrics"):
            print(f"\n回测指标:")
            for k, v in result["performance_metrics"].items():
                print(f"  {k}: {v:.4f}")

        # 保存模型
        if args.save_model:
            pipeline.save(args.save_model)
            logger.info(f"Model saved to {args.save_model}")

        logger.info("Pipeline completed successfully")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
