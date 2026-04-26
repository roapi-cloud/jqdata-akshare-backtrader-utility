"""
测试流水线编排器
"""

import pytest
from pathlib import Path
import tempfile

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pipeline_orchestrator import PipelineOrchestrator
from config.settings import Settings


class TestPipelineOrchestrator:
    """测试流水线编排器"""

    @pytest.fixture
    def settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            settings = Settings()
            settings.strategy_source_dir = tmp_path / "strategies"
            settings.strategy_source_dir.mkdir(exist_ok=True)
            settings.factor_output_dir = tmp_path / "factors"
            settings.mapping_output_dir = tmp_path / "mappings"
            settings.report_output_dir = tmp_path / "reports"
            settings.generated_code_dir = tmp_path / "generated_code"
            yield settings

    def test_orchestrator_init(self, settings):
        """测试编排器初始化"""
        orchestrator = PipelineOrchestrator(settings)
        assert orchestrator is not None

    def test_run_scan_only(self, settings):
        """测试仅扫描模式"""
        orchestrator = PipelineOrchestrator(settings)
        result = orchestrator.run(mode="scan_only")
        assert "stages" in result
        assert "scan" in result["stages"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
