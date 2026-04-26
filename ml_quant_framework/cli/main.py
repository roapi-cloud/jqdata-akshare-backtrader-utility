#!/usr/bin/env python
"""ML量化框架命令行入口"""

import argparse
import sys
from pathlib import Path


def main():
    """CLI入口函数，解析参数并分发到对应命令处理函数。"""
    parser = argparse.ArgumentParser(
        description="ML量化选股框架 - 通用机器学习量化流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行完整流水线
  python -m ml_quant_framework run --config configs/ml_factor_strategy.yaml

  # 仅训练模型
  python -m ml_quant_framework train --config configs/ml_factor_strategy.yaml

  # 回测
  python -m ml_quant_framework backtest --config configs/ml_factor_strategy.yaml

  # 列出可用因子
  python -m ml_quant_framework list-factors

  # 列出可用模型
  python -m ml_quant_framework list-models
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run 命令
    run_parser = subparsers.add_parser("run", help="运行完整流水线")
    run_parser.add_argument("--config", "-c", required=True, help="配置文件路径")
    run_parser.add_argument("--dry-run", action="store_true", help="试运行")
    run_parser.add_argument("--output", "-o", default="output", help="输出目录")

    # train 命令
    train_parser = subparsers.add_parser("train", help="训练模型")
    train_parser.add_argument("--config", "-c", required=True, help="配置文件路径")
    train_parser.add_argument("--model", "-m", default=None, help="覆盖模型名称")
    train_parser.add_argument("--output", "-o", default="models", help="模型保存目录")

    # backtest 命令
    bt_parser = subparsers.add_parser("backtest", help="运行回测")
    bt_parser.add_argument("--config", "-c", required=True, help="配置文件路径")
    bt_parser.add_argument("--model-path", required=True, help="已训练模型路径")
    bt_parser.add_argument("--output", "-o", default="output/backtest", help="输出目录")

    # predict 命令
    pred_parser = subparsers.add_parser("predict", help="预测选股")
    pred_parser.add_argument("--config", "-c", required=True, help="配置文件路径")
    pred_parser.add_argument("--model-path", required=True, help="模型路径")
    pred_parser.add_argument("--date", "-d", default=None, help="预测日期 YYYY-MM-DD")

    # list-factors 命令
    subparsers.add_parser("list-factors", help="列出所有可用因子")

    # list-models 命令
    subparsers.add_parser("list-models", help="列出所有可用模型")

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化项目 (创建配置模板)")
    init_parser.add_argument("--output", "-o", default="configs", help="配置输出目录")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # 分发到对应命令
    if args.command == "run":
        cmd_run(args)
    elif args.command == "train":
        cmd_train(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "predict":
        cmd_predict(args)
    elif args.command == "list-factors":
        cmd_list_factors()
    elif args.command == "list-models":
        cmd_list_models()
    elif args.command == "init":
        cmd_init(args)


def cmd_run(args):
    """运行完整流水线。

    Args:
        args: 命令行参数，包含 config, dry_run, output。
    """
    from ml_quant_framework.core.config import PipelineConfig
    from ml_quant_framework.core.pipeline import MLPipeline

    print(f"加载配置: {args.config}")
    config = PipelineConfig.from_yaml(args.config)

    pipeline = MLPipeline(config)
    results = pipeline.run(dry_run=args.dry_run)

    print("流水线执行完成!")
    return results


def cmd_train(args):
    """训练模型。

    Args:
        args: 命令行参数，包含 config, model, output。
    """
    from ml_quant_framework.core.config import PipelineConfig
    from ml_quant_framework.core.pipeline import MLPipeline

    config = PipelineConfig.from_yaml(args.config)
    if args.model:
        config.model.name = args.model

    pipeline = MLPipeline(config)
    pipeline.train(output_dir=args.output)
    print(f"模型已保存至: {args.output}")


def cmd_backtest(args):
    """运行回测。

    Args:
        args: 命令行参数，包含 config, model_path, output。
    """
    from ml_quant_framework.core.config import PipelineConfig
    from ml_quant_framework.core.pipeline import MLPipeline

    config = PipelineConfig.from_yaml(args.config)
    pipeline = MLPipeline(config)
    results = pipeline.backtest(model_path=args.model_path, output_dir=args.output)
    pipeline.print_report()


def cmd_predict(args):
    """预测选股。

    Args:
        args: 命令行参数，包含 config, model_path, date。
    """
    from ml_quant_framework.core.config import PipelineConfig
    from ml_quant_framework.core.pipeline import MLPipeline

    config = PipelineConfig.from_yaml(args.config)
    pipeline = MLPipeline(config)
    stocks = pipeline.predict(model_path=args.model_path, date=args.date)

    print("预测选股结果:")
    for stock in stocks:
        print(f"  {stock}")


def cmd_list_factors():
    """列出所有可用因子。"""
    from ml_quant_framework.factors.registry_helpers import list_available_factors

    factors = list_available_factors()
    print("可用因子列表:")
    for f in sorted(factors):
        print(f"  - {f}")


def cmd_list_models():
    """列出所有可用模型。"""
    from ml_quant_framework.core.registry import MODEL_REGISTRY

    models = MODEL_REGISTRY.list()
    print("可用模型列表:")
    for m in sorted(models):
        print(f"  - {m}")


def cmd_init(args):
    """初始化项目，创建配置模板。

    Args:
        args: 命令行参数，包含 output。
    """
    import shutil

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    # 复制模板配置
    template_dir = Path(__file__).parent.parent.parent / "configs"
    for template in template_dir.glob("*.yaml"):
        shutil.copy(template, output)

    print(f"项目已初始化，配置模板位于: {output}")


if __name__ == "__main__":
    main()
