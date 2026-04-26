"""
测试策略解析器
"""

import pytest
from pathlib import Path
import tempfile

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.strategy_parser import StrategyParser, ParsedStrategy


class TestStrategyParser:
    """测试策略解析器"""

    @pytest.fixture
    def parser(self):
        return StrategyParser()

    @pytest.fixture
    def temp_strategy_file(self):
        """创建临时策略文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
def initialize(context):
    g.stock_num = 10

def handle_data(context, data):
    stocks = get_index_stocks('000300.XSHG')
    for stock in stocks:
        order_target_value(stock, 10000)
""")
            f.flush()
            yield Path(f.name)

    def test_parse_file(self, parser, temp_strategy_file):
        """测试解析文件"""
        result = parser.parse_file(temp_strategy_file)
        assert result is not None
        assert isinstance(result, ParsedStrategy)

    def test_parse_extract_functions(self, parser, temp_strategy_file):
        """测试提取函数"""
        result = parser.parse_file(temp_strategy_file)
        func_names = [f.name for f in result.functions]
        assert "initialize" in func_names
        assert "handle_data" in func_names

    def test_parse_extract_data_sources(self, parser, temp_strategy_file):
        """测试提取数据源"""
        result = parser.parse_file(temp_strategy_file)
        assert "get_index_stocks" in result.data_sources
        assert "order_target_value" in result.data_sources


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
