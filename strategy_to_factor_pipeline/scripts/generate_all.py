"""
批量生成脚本
批量处理所有策略并生成因子
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.settings import Settings
from core.pipeline_orchestrator import PipelineOrchestrator


def generate_all():
    """批量生成所有因子"""
    logger.info("开始批量生成因子...")

    settings = Settings()
    orchestrator = PipelineOrchestrator(settings)

    # 运行完整流水线
    result = orchestrator.run(mode="full")

    # 输出统计
    stats = result.get("stages", {})
    logger.info("\n批量生成统计:")
    for stage, info in stats.items():
        logger.info(f"  {stage}: {info}")

    return result


if __name__ == "__main__":
    generate_all()
