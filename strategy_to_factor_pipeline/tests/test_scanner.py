"""
测试策略扫描器
"""

import pytest
from pathlib import Path
import tempfile
import os

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.strategy_scanner import StrategyScanner, StrategyInfo


class TestStrategyScanner:
    """测试策略扫描器"""

    @pytest.fixture
    def temp_strategy_dir(self):
        """创建临时策略目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试策略文件
            test_file = Path(tmpdir) / "test_strategy.py"
            test_file.write_text("""
# 标题: 测试策略
# 作者: test

def initialize(context):
    pass

def handle_data(context, data):
    pass
""")
            yield Path(tmpdir)

    def test_scan_finds_files(self, temp_strategy_dir):
        """测试扫描能找到文件"""
        scanner = StrategyScanner(temp_strategy_dir)
        strategies = scanner.scan()
        assert len(strategies) > 0

    def test_scan_excludes_non_strategy(self, temp_strategy_dir):
        """测试扫描排除非策略文件"""
        # 创建测试文件
        test_file = temp_strategy_dir / "test_test.py"
        test_file.write_text("# test file")

        scanner = StrategyScanner(temp_strategy_dir)
        strategies = scanner.scan()

        # 应该排除test_开头的文件
        for s in strategies:
            assert "test_test" not in s.file_name

    def test_get_statistics(self, temp_strategy_dir):
        """测试获取统计信息"""
        scanner = StrategyScanner(temp_strategy_dir)
        scanner.scan()
        stats = scanner.get_statistics()
        assert "total_strategies" in stats
        assert stats["total_strategies"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
