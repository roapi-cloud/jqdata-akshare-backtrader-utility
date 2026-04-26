"""
快速启动脚本 - 一键运行终极轮动策略框架

用法:
    python run.py                          # 使用默认配置运行研究模式
    python run.py --mode research          # 研究模式 (回测+评估)
    python run.py --mode simulation        # 模拟盘模式
    python run.py --config my_config.yaml  # 使用自定义配置
    python run.py --strategies etf_momentum_rsrs,multi_factor_epo  # 指定策略
"""

import sys
import os
import argparse
from datetime import datetime

# 添加框架路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rotation_strategy_framework.pipeline import Pipeline, PipelineConfig
from rotation_strategy_framework.strategy_registry import StrategyRegistry


def main():
    parser = argparse.ArgumentParser(description="终极轮动策略框架")
    parser.add_argument(
        "--mode",
        choices=["research", "simulation", "live"],
        default="research",
        help="运行模式 (默认: research)",
    )
    parser.add_argument("--config", type=str, help="配置文件路径 (YAML/JSON)")
    parser.add_argument("--strategies", type=str, help="策略列表 (逗号分隔)")
    parser.add_argument("--start", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--cash", type=float, help="初始资金")
    parser.add_argument("--top-k", type=int, help="选择最优策略数量")
    parser.add_argument("--etf-pool", type=str, help="ETF池 (逗号分隔)")
    parser.add_argument("--force-update", action="store_true", help="强制更新数据")
    parser.add_argument(
        "--no-walk-forward", action="store_true", help="跳过Walk-Forward验证"
    )

    args = parser.parse_args()

    # 加载配置
    if args.config and os.path.exists(args.config):
        print(f"加载配置文件: {args.config}")
        config = PipelineConfig.from_yaml(args.config)
    else:
        print("使用默认配置")
        config = PipelineConfig()

    # 覆盖命令行参数
    if args.mode:
        config.pipeline.mode = args.mode
    if args.start:
        config.data.start = args.start
    if args.end:
        config.data.end = args.end
    if args.cash:
        config.backtest.initial_cash = args.cash
    if args.top_k:
        config.evaluation.top_k = args.top_k
    if args.force_update:
        config.data.force_update = True
    if args.no_walk_forward:
        config.evaluation.walk_forward.enabled = False

    if args.strategies:
        config.strategies.names = [s.strip() for s in args.strategies.split(",")]
        config.strategies.auto_select = False

    if args.etf_pool:
        config.data.etf_pool = [s.strip() for s in args.etf_pool.split(",")]

    # 打印配置摘要
    print("\n" + "=" * 60)
    print("终极轮动策略框架 v1.0")
    print("=" * 60)
    print(f"模式: {config.pipeline.mode}")
    print(f"时间: {config.data.start} ~ {config.data.end}")
    print(f"资金: {config.backtest.initial_cash:,.0f}")
    print(f"ETF池: {config.data.etf_pool}")
    if config.strategies.names:
        print(f"策略: {config.strategies.names}")
    else:
        print(f"策略: 全部14种预设策略 (自动选择Top {config.evaluation.top_k})")
    print("=" * 60 + "\n")

    # 创建并运行流水线
    pipeline = Pipeline(config)

    try:
        if config.pipeline.mode == "research":
            result = pipeline.run_research()
            print("\n研究模式完成!")
            if result.get("selected_strategies"):
                print(f"最优策略: {result['selected_strategies']}")
            if result.get("portfolio_weights"):
                print(f"组合权重: {result['portfolio_weights']}")

        elif config.pipeline.mode == "simulation":
            pipeline.run_simulation()

        elif config.pipeline.mode == "live":
            pipeline.run_live()

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
