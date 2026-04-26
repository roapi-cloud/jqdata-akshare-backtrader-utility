# 批量运行所有策略脚本 - 支持.py和.txt策略文件
import subprocess
import sys
import os
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def find_strategies():
    """扫描目录下所有策略文件"""
    strategies = []
    workdir = r"E:\jqdata_akshare_backtrader_utility\聚宽有价值策略558"

    for f in os.listdir(workdir):
        if f.endswith(".py"):
            strategies.append(
                {"name": f.replace(".py", ""), "file": f, "type": "python"}
            )
        elif f.endswith(".txt"):
            # 读取txt文件检查是否是策略代码
            filepath = os.path.join(workdir, f)
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    content = file.read(500)
                    # 检查是否包含聚宽策略特征代码
                    if (
                        "def initialize" in content
                        or "def set_param" in content
                        or "quakecat" in content
                    ):
                        strategies.append(
                            {"name": f.replace(".txt", ""), "file": f, "type": "jqdata"}
                        )
            except:
                pass

    return strategies


def run_strategy(strategy):
    workdir = r"E:\jqdata_akshare_backtrader_utility\聚宽有价值策略558"
    print(f"\n{'=' * 60}")
    print(f"运行策略: {strategy['name']}")
    print(f"文件: {strategy['file']}")
    print(f"类型: {strategy['type']}")
    print(f"{'=' * 60}")

    if strategy["type"] == "python":
        cmd = [sys.executable, strategy["file"]]
    else:
        # txt策略需要先迁移，这里暂时跳过
        print(f"暂不支持直接运行txt策略: {strategy['name']}")
        return False

    try:
        result = subprocess.run(
            cmd, cwd=workdir, capture_output=True, text=True, timeout=300
        )
        print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"策略运行超时: {strategy['name']}")
        return False
    except Exception as e:
        print(f"运行出错: {e}")
        return False


def main():
    strategies = find_strategies()
    print(f"找到 {len(strategies)} 个策略文件:")
    for i, s in enumerate(strategies, 1):
        print(f"  {i}. [{s['type']}] {s['name']}")

    results = []
    for i, strategy in enumerate(strategies, 1):
        print(f"\n[{i}/{len(strategies)}] ", end="")
        success = run_strategy(strategy)
        results.append({"name": strategy["name"], "success": success})
        print(f"结果: {'OK' if success else 'FAILED'}")

    print(f"\n{'=' * 60}")
    print("批量运行结果汇总")
    print(f"{'=' * 60}")
    for r in results:
        status = "OK" if r["success"] else "FAILED"
        print(f"{r['name']}: {status}")

    success_count = sum(1 for r in results if r["success"])
    print(f"\n成功: {success_count}/{len(results)}")


if __name__ == "__main__":
    main()
