import json
import logging
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

PIPELINE_STEPS = [
    "scan_strategies",
    "parse_strategies",
    "generate_signals",
    "store_factors",
    "generate_mapping",
]


@dataclass
class PipelineOrchestratorConfig:
    """流水线编排器配置。

    Attributes:
        strategy_dir: 策略文件目录。
        output_dir: 输出目录。
        checkpoint_dir: 检查点目录。
        max_workers: 最大并行工作数。
        executor_type: 执行器类型，process 或 thread。
        retry_count: 失败重试次数。
        step_timeout: 单步骤超时秒数，0 表示不限制。
    """

    strategy_dir: str = "./strategies"
    output_dir: str = "./output"
    checkpoint_dir: str = "./checkpoints"
    max_workers: int = 4
    executor_type: str = "process"
    retry_count: int = 1
    step_timeout: int = 0


@dataclass
class StepStatus:
    """单个步骤的运行状态。

    Attributes:
        name: 步骤名称。
        status: 状态，pending / running / completed / failed / skipped。
        start_time: 开始时间戳。
        end_time: 结束时间戳。
        items_total: 总项目数。
        items_completed: 已完成项目数。
        items_failed: 失败项目数。
        error: 错误信息。
        details: 附加详情。
    """

    name: str
    status: str = "pending"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    items_total: int = 0
    items_completed: int = 0
    items_failed: int = 0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        if self.start_time:
            return time.time() - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["duration"] = self.duration
        return d


@dataclass
class Checkpoint:
    """检查点数据。

    Attributes:
        pipeline_id: 流水线运行唯一标识。
        created_at: 创建时间。
        updated_at: 更新时间。
        current_step: 当前步骤索引。
        step_statuses: 各步骤状态。
        results: 已产出的结果。
        failed_strategies: 失败策略记录。
    """

    pipeline_id: str
    created_at: str
    updated_at: str
    current_step: int = 0
    step_statuses: List[Dict[str, Any]] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    failed_strategies: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        return cls(**data)


class ProgressTracker:
    """进度追踪器，实时输出进度并估算剩余时间。"""

    def __init__(self, total_items: int, step_name: str = ""):
        self.total = total_items
        self.completed = 0
        self.failed = 0
        self.step_name = step_name
        self.start_time = time.time()
        self._last_log_time = 0.0
        self._log_interval = 5.0

    def update(self, completed: int = 0, failed: int = 0):
        self.completed += completed
        self.failed += failed
        now = time.time()
        if (
            now - self._last_log_time >= self._log_interval
            or self.completed + self.failed >= self.total
        ):
            self._log(now)
            self._last_log_time = now

    def _log(self, now: float):
        elapsed = now - self.start_time
        done = self.completed + self.failed
        if done == 0:
            pct = 0.0
            eta = "N/A"
        else:
            pct = done / self.total * 100
            speed = done / elapsed
            remaining = (self.total - done) / speed if speed > 0 else 0
            eta = f"{remaining:.1f}s"
        logger.info(
            "[%s] %d/%d (%.1f%%) ok=%d fail=%d elapsed=%.1fs eta=%s",
            self.step_name,
            done,
            self.total,
            pct,
            self.completed,
            self.failed,
            elapsed,
            eta,
        )

    def finish(self):
        elapsed = time.time() - self.start_time
        logger.info(
            "[%s] FINISHED: total=%d ok=%d fail=%d elapsed=%.1fs",
            self.step_name,
            self.total,
            self.completed,
            self.failed,
            elapsed,
        )


class PipelineOrchestrator:
    """策略到因子生成流水线编排器。

    负责编排完整的策略扫描、解析、信号生成、因子存储和映射表生成流程。
    支持断点续传、并行处理、错误隔离和进度监控。

    Attributes:
        config: 流水线编排配置。
        checkpoint: 当前检查点。
        step_statuses: 各步骤状态映射。
        results: 流水线运行结果。
    """

    def __init__(self, config: Optional[PipelineOrchestratorConfig] = None):
        self.config = config or PipelineOrchestratorConfig()
        self.pipeline_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.checkpoint: Optional[Checkpoint] = None
        self.step_statuses: Dict[str, StepStatus] = {
            step: StepStatus(name=step) for step in PIPELINE_STEPS
        }
        self.results: Dict[str, Any] = {}
        self.failed_strategies: List[Dict[str, Any]] = []
        self._intermediate_results: Dict[str, Any] = {}

        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.checkpoint_dir).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def run_full_pipeline(self, start_from: int = 0) -> Dict[str, Any]:
        """运行完整流水线。

        Args:
            start_from: 起始步骤索引，0 表示从头开始。

        Returns:
            流水线运行结果字典。
        """
        logger.info("=" * 60)
        logger.info("Pipeline run started: %s", self.pipeline_id)
        logger.info("=" * 60)

        self.checkpoint = Checkpoint(
            pipeline_id=self.pipeline_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            current_step=start_from,
        )

        for idx, step_name in enumerate(PIPELINE_STEPS):
            if idx < start_from:
                self.step_statuses[step_name].status = "skipped"
                continue

            self.checkpoint.current_step = idx
            self._run_single_step(step_name)
            self._save_checkpoint()

            if self.step_statuses[step_name].status == "failed":
                logger.error("Pipeline stopped at step: %s", step_name)
                break

        self.checkpoint.updated_at = datetime.now().isoformat()
        self.results = self.generate_summary_report()
        self._save_checkpoint()
        logger.info("Pipeline run finished: %s", self.pipeline_id)
        return self.results

    def run_step(self, step_name: str) -> Dict[str, Any]:
        """运行单个步骤。

        Args:
            step_name: 步骤名称。

        Returns:
            该步骤的运行结果。
        """
        if step_name not in self.step_statuses:
            raise ValueError(
                f"Unknown step: {step_name}. Valid steps: {PIPELINE_STEPS}"
            )

        logger.info("Running single step: %s", step_name)
        self._run_single_step(step_name)
        return self._intermediate_results.get(step_name, {})

    def get_pipeline_status(self) -> Dict[str, Any]:
        """获取流水线当前状态。

        Returns:
            状态字典，包含各步骤状态、进度和失败记录。
        """
        status = {
            "pipeline_id": self.pipeline_id,
            "steps": {},
            "failed_strategies": self.failed_strategies,
            "checkpoint_exists": self.checkpoint is not None,
        }
        for name, ss in self.step_statuses.items():
            status["steps"][name] = ss.to_dict()
        return status

    def resume_from_checkpoint(
        self, checkpoint_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """从检查点恢复流水线。

        Args:
            checkpoint_path: 检查点文件路径，未指定时使用最新检查点。

        Returns:
            恢复后继续运行的结果。
        """
        if checkpoint_path:
            ckpt_data = self._load_checkpoint_file(checkpoint_path)
        else:
            ckpt_data = self._load_latest_checkpoint()

        if ckpt_data is None:
            raise FileNotFoundError("No checkpoint found to resume from.")

        ckpt = Checkpoint.from_dict(ckpt_data)
        self.pipeline_id = ckpt.pipeline_id
        self.checkpoint = ckpt
        self.failed_strategies = ckpt.failed_strategies
        self._intermediate_results = ckpt.results

        for ss_dict in ckpt.step_statuses:
            name = ss_dict["name"]
            if name in self.step_statuses:
                ss = self.step_statuses[name]
                ss.status = ss_dict["status"]
                ss.start_time = ss_dict.get("start_time")
                ss.end_time = ss_dict.get("end_time")
                ss.items_total = ss_dict.get("items_total", 0)
                ss.items_completed = ss_dict.get("items_completed", 0)
                ss.items_failed = ss_dict.get("items_failed", 0)
                ss.error = ss_dict.get("error")
                ss.details = ss_dict.get("details", {})

        resume_from = ckpt.current_step
        completed_steps = [
            ss["name"] for ss in ckpt.step_statuses if ss.get("status") == "completed"
        ]
        logger.info(
            "Resuming pipeline %s from step %d (%s). Completed steps: %s",
            self.pipeline_id,
            resume_from,
            PIPELINE_STEPS[resume_from]
            if resume_from < len(PIPELINE_STEPS)
            else "done",
            completed_steps,
        )

        return self.run_full_pipeline(start_from=resume_from)

    # ------------------------------------------------------------------
    # 并行处理
    # ------------------------------------------------------------------

    def run_parallel(
        self,
        items: List[Any],
        worker_func: Callable,
        max_workers: Optional[int] = None,
        step_name: str = "parallel",
    ) -> Dict[str, Any]:
        """并行处理项目列表。

        Args:
            items: 待处理项目列表。
            worker_func: 工作函数，接收单个项目，返回 (item, result) 或抛出异常。
            max_workers: 最大并行数，默认使用配置值。
            step_name: 步骤名称（用于日志）。

        Returns:
            包含 successes, failures, results 的字典。
        """
        workers = max_workers or self.config.max_workers
        executor_cls = (
            ProcessPoolExecutor
            if self.config.executor_type == "process"
            else ThreadPoolExecutor
        )

        tracker = ProgressTracker(len(items), step_name)
        successes = []
        failures = []
        all_results = {}

        with executor_cls(max_workers=workers) as executor:
            future_to_item = {
                executor.submit(worker_func, item): item for item in items
            }

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    timeout = (
                        self.config.step_timeout
                        if self.config.step_timeout > 0
                        else None
                    )
                    result = future.result(timeout=timeout)
                    successes.append(item)
                    all_results[str(item)] = result
                    tracker.update(completed=1)
                except Exception as exc:
                    error_info = {
                        "item": str(item),
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                    failures.append(error_info)
                    self.failed_strategies.append(error_info)
                    logger.error("[%s] Failed on %s: %s", step_name, item, exc)
                    tracker.update(failed=1)

        tracker.finish()
        return {
            "successes": successes,
            "failures": failures,
            "results": all_results,
            "total": len(items),
            "success_count": len(successes),
            "failure_count": len(failures),
        }

    # ------------------------------------------------------------------
    # 检查点管理
    # ------------------------------------------------------------------

    def save_checkpoint(self, path: Optional[str] = None):
        """保存检查点。

        Args:
            path: 指定路径，默认使用自动命名。
        """
        self._save_checkpoint(path)

    def load_checkpoint(self, path: Optional[str] = None) -> Dict[str, Any]:
        """加载检查点。

        Args:
            path: 检查点文件路径，未指定时加载最新。

        Returns:
            检查点数据字典。
        """
        if path:
            return self._load_checkpoint_file(path)
        return self._load_latest_checkpoint() or {}

    # ------------------------------------------------------------------
    # 报告
    # ------------------------------------------------------------------

    def generate_summary_report(self) -> Dict[str, Any]:
        """生成汇总报告。

        Returns:
            汇总报告字典，包含各步骤统计、失败策略列表和总体指标。
        """
        report = {
            "pipeline_id": self.pipeline_id,
            "generated_at": datetime.now().isoformat(),
            "steps": {},
            "summary": {
                "total_steps": len(PIPELINE_STEPS),
                "completed_steps": 0,
                "failed_steps": 0,
                "skipped_steps": 0,
                "total_strategies_processed": 0,
                "total_strategies_failed": 0,
            },
            "failed_strategies": self.failed_strategies,
        }

        total_duration = 0.0
        for name, ss in self.step_statuses.items():
            step_info = ss.to_dict()
            report["steps"][name] = step_info

            if ss.status == "completed":
                report["summary"]["completed_steps"] += 1
            elif ss.status == "failed":
                report["summary"]["failed_steps"] += 1
            elif ss.status == "skipped":
                report["summary"]["skipped_steps"] += 1

            if ss.duration:
                total_duration += ss.duration

            report["summary"]["total_strategies_processed"] += ss.items_completed
            report["summary"]["total_strategies_failed"] += ss.items_failed

        report["summary"]["total_duration_sec"] = round(total_duration, 2)
        return report

    # ------------------------------------------------------------------
    # 内部方法 — 步骤执行
    # ------------------------------------------------------------------

    def _run_single_step(self, step_name: str):
        ss = self.step_statuses[step_name]
        if ss.status in ("completed", "skipped"):
            logger.info("Step %s already %s, skipping.", step_name, ss.status)
            return

        ss.status = "running"
        ss.start_time = time.time()
        logger.info(">>> Starting step: %s", step_name)

        try:
            handler = getattr(self, f"_step_{step_name}", None)
            if handler is None:
                raise NotImplementedError(f"No handler for step: {step_name}")

            result = handler()
            ss.items_completed = result.get("success_count", 0)
            ss.items_failed = result.get("failure_count", 0)
            ss.items_total = result.get("total", 0)
            ss.details = result
            ss.status = "completed"
            self._intermediate_results[step_name] = result

        except Exception as exc:
            ss.status = "failed"
            ss.error = str(exc)
            logger.error(
                "Step %s failed: %s\n%s", step_name, exc, traceback.format_exc()
            )

        ss.end_time = time.time()
        logger.info(
            "<<< Step %s finished: status=%s duration=%.1fs",
            step_name,
            ss.status,
            ss.duration or 0,
        )

    def _step_scan_strategies(self) -> Dict[str, Any]:
        """扫描策略目录，收集所有策略文件。"""
        strategy_dir = Path(self.config.strategy_dir)
        if not strategy_dir.exists():
            logger.warning("Strategy directory not found: %s", strategy_dir)
            return {
                "successes": [],
                "failures": [],
                "results": {},
                "total": 0,
                "success_count": 0,
                "failure_count": 0,
            }

        strategy_files = list(strategy_dir.rglob("*.py"))
        strategy_files = [
            f
            for f in strategy_files
            if not f.name.startswith("_") and f.name != "setup.py"
        ]

        def _scan_one(file_path: Path):
            return {
                "path": str(file_path),
                "name": file_path.stem,
                "size_bytes": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).isoformat(),
            }

        return self.run_parallel(
            items=strategy_files,
            worker_func=_scan_one,
            step_name="scan_strategies",
        )

    def _step_parse_strategies(self) -> Dict[str, Any]:
        """解析策略文件，提取策略元信息。"""
        scanned = self._intermediate_results.get("scan_strategies", {})
        strategies = scanned.get("results", {})

        if not strategies:
            logger.warning("No scanned strategies found, running scan first.")
            scan_result = self._step_scan_strategies()
            strategies = scan_result.get("results", {})

        def _parse_one(strategy_info: Dict[str, Any]):
            file_path = Path(strategy_info["path"])
            content = file_path.read_text(encoding="utf-8")
            meta = {
                "path": strategy_info["path"],
                "name": strategy_info["name"],
                "lines": content.count("\n") + 1,
                "has_backtest": "backtest" in content.lower()
                or "run" in content.lower(),
                "has_params": "param" in content.lower(),
            }
            return meta

        return self.run_parallel(
            items=list(strategies.values()),
            worker_func=_parse_one,
            step_name="parse_strategies",
        )

    def _step_generate_signals(self) -> Dict[str, Any]:
        """基于解析后的策略生成交易信号。"""
        parsed = self._intermediate_results.get("parse_strategies", {})
        strategies = parsed.get("results", {})

        if not strategies:
            logger.warning("No parsed strategies found, running parse first.")
            parse_result = self._step_parse_strategies()
            strategies = parse_result.get("results", {})

        def _generate_one(strategy_info: Dict[str, Any]):
            return {
                "strategy_name": strategy_info.get("name", "unknown"),
                "signal_count": 0,
                "status": "generated",
            }

        return self.run_parallel(
            items=list(strategies.values()),
            worker_func=_generate_one,
            step_name="generate_signals",
        )

    def _step_store_factors(self) -> Dict[str, Any]:
        """存储生成的因子数据。"""
        signals = self._intermediate_results.get("generate_signals", {})
        signal_results = signals.get("results", {})

        if not signal_results:
            logger.warning("No signals found, running generate_signals first.")
            signal_result = self._step_generate_signals()
            signal_results = signal_result.get("results", {})

        output_dir = Path(self.config.output_dir) / "factors"
        output_dir.mkdir(parents=True, exist_ok=True)

        def _store_one(signal_info: Dict[str, Any]):
            factor_file = (
                output_dir
                / f"{signal_info.get('strategy_name', 'unknown')}_factors.json"
            )
            factor_file.write_text(
                json.dumps(signal_info, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {"stored_path": str(factor_file), "status": "stored"}

        return self.run_parallel(
            items=list(signal_results.values()),
            worker_func=_store_one,
            step_name="store_factors",
        )

    def _step_generate_mapping(self) -> Dict[str, Any]:
        """生成策略到因子的映射表。"""
        stored = self._intermediate_results.get("store_factors", {})
        stored_results = stored.get("results", {})

        if not stored_results:
            logger.warning("No stored factors found, running store_factors first.")
            store_result = self._step_store_factors()
            stored_results = store_result.get("results", {})

        mapping = {}
        for key, info in stored_results.items():
            strategy_name = info.get("strategy_name", key)
            factor_path = info.get("stored_path", "")
            mapping[strategy_name] = {
                "factor_path": factor_path,
                "status": info.get("status", "unknown"),
            }

        mapping_file = Path(self.config.output_dir) / "strategy_factor_mapping.json"
        mapping_file.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info("Mapping table saved to %s", mapping_file)
        return {
            "successes": list(mapping.keys()),
            "failures": [],
            "results": mapping,
            "total": len(mapping),
            "success_count": len(mapping),
            "failure_count": 0,
            "mapping_file": str(mapping_file),
        }

    # ------------------------------------------------------------------
    # 内部方法 — 检查点持久化
    # ------------------------------------------------------------------

    def _save_checkpoint(self, path: Optional[str] = None):
        if self.checkpoint is None:
            return

        self.checkpoint.updated_at = datetime.now().isoformat()
        self.checkpoint.step_statuses = [
            ss.to_dict() for ss in self.step_statuses.values()
        ]
        self.checkpoint.results = self._intermediate_results
        self.checkpoint.failed_strategies = self.failed_strategies

        if path is None:
            path = os.path.join(
                self.config.checkpoint_dir,
                f"checkpoint_{self.pipeline_id}.json",
            )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.checkpoint.to_dict(), f, ensure_ascii=False, indent=2)

        logger.debug("Checkpoint saved to %s", path)

    def _load_checkpoint_file(self, path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        ckpt_dir = Path(self.config.checkpoint_dir)
        if not ckpt_dir.exists():
            return None

        checkpoints = sorted(
            ckpt_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not checkpoints:
            return None

        return self._load_checkpoint_file(str(checkpoints[0]))
