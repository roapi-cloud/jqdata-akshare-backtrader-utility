"""Task orchestration helpers for strategy_kits automation."""

from .task_schema import validate_strategy_task_spec


def persist_task_artifacts(*args, **kwargs):
    from .artifacts import persist_task_artifacts as _impl
    return _impl(*args, **kwargs)


def validate_artifact_manifest(*args, **kwargs):
    from .artifact_contracts import validate_artifact_manifest as _impl
    return _impl(*args, **kwargs)


def validate_artifact_summary(*args, **kwargs):
    from .artifact_contracts import validate_artifact_summary as _impl
    return _impl(*args, **kwargs)


def build_prediction_frame_from_task(*args, **kwargs):
    from .task_runner import build_prediction_frame_from_task as _impl
    return _impl(*args, **kwargs)


def run_strategy_task(*args, **kwargs):
    from .task_runner import run_strategy_task as _impl
    return _impl(*args, **kwargs)


__all__ = [
    "build_prediction_frame_from_task",
    "persist_task_artifacts",
    "run_strategy_task",
    "validate_artifact_manifest",
    "validate_artifact_summary",
    "validate_strategy_task_spec",
]
