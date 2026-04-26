"""
测试因子生成器
"""

import pytest
from pathlib import Path
import tempfile
import json

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.factor_generator import FactorGenerator, FactorSignal
from config.settings import Settings


class TestFactorGenerator:
    """测试因子生成器"""

    @pytest.fixture
    def generator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = Settings()
            settings.factor_output_dir = Path(tmpdir)
            return FactorGenerator(settings)

    def test_generate_factor(self, generator):
        """测试生成单个因子"""
        strategy_info = {"name": "test_strategy", "frequency": "daily"}
        factor_logic = {
            "name": "test_factor",
            "description": "测试因子",
            "category": "momentum",
        }

        factor = generator.generate_factor(strategy_info, factor_logic)
        assert isinstance(factor, FactorSignal)
        assert factor.factor_name == "test_factor"

    def test_generate_batch(self, generator):
        """测试批量生成"""
        strategies = [
            {
                "name": "strategy1",
                "frequency": "daily",
                "factor_candidates": [
                    {"name": "factor1", "description": "因子1"},
                    {"name": "factor2", "description": "因子2"},
                ],
            }
        ]

        factors = generator.generate_batch(strategies)
        assert len(factors) == 2

    def test_export_factors(self, generator):
        """测试导出因子"""
        strategy_info = {"name": "test_strategy", "frequency": "daily"}
        factor_logic = {"name": "test_factor", "description": "测试因子"}

        generator.generate_factor(strategy_info, factor_logic)
        output_file = generator.export_factors()

        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) > 0

    def test_get_statistics(self, generator):
        """测试获取统计"""
        stats = generator.get_statistics()
        assert "total" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
