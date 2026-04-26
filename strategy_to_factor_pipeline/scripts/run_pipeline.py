"""
主运行脚本
策略到因子转换流水线的入口
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.settings import Settings
from core.pipeline_orchestrator import PipelineOrchestrator


def main():
    parser = argparse.ArgumentParser(description="策略到因子转换流水线")
    parser.add_argument(
        "--mode",
        choices=["full", "scan_only", "parse_only", "generate_only"],
        default="full",
        help="运行模式",
    )
    parser.add_argument("--strategy-dir", type=str, help="策略文件目录")
    parser.add_argument("--output-dir", type=str, help="输出目录")
    parser.add_argument("--start-date", type=str, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--stock-pool", type=str, help="股票池")
    parser.add_argument("--workers", type=int, help="并行工作数")
    parser.add_argument("--log-level", type=str, default="INFO", help="日志级别")
    args = parser.parse_args()

    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)
    logger.add(
        project_root / "output" / "pipeline.log",
        level=args.log_level,
        rotation="10 MB",
    )

    # 创建配置
    settings = Settings()
    if args.strategy_dir:
        settings.strategy_source_dir = Path(args.strategy_dir)
    if args.output_dir:
        settings.project_root = Path(args.output_dir)
    if args.start_date:
        settings.start_date = args.start_date
    if args.end_date:
        settings.end_date = args.end_date
    if args.stock_pool:
        settings.stock_pool = args.stock_pool
    if args.workers:
        settings.max_workers = args.workers

    # 运行流水线
    orchestrator = PipelineOrchestrator(settings)
    result = orchestrator.run(mode=args.mode)

    # 输出结果
    logger.info("\n" + "=" * 60)
    logger.info("流水线运行完成")
    logger.info(f"模式: {args.mode}")
    for stage, stats in result.get("stages", {}).items():
        logger.info(f"  {stage}: {stats.get('elapsed_seconds', 0)}s")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
