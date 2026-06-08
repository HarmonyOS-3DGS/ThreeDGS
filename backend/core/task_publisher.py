"""Task publishing abstraction — decouples API layer from Worker layer.

API 层通过此模块提交训练任务，Worker 层在启动时注册具体实现。
这样 API 无需知道 Celery 的存在。
"""
from typing import Callable

# 类型别名: (task_id, video_path) -> None
PipelineSubmitter = Callable[[str, str], None]

_submitter: PipelineSubmitter | None = None


def _ensure_submitter():
    global _submitter
    if _submitter is None:
        try:
            import backend.worker.tasks.pipeline  # noqa: F401  trigger register_pipeline_submitter
        except ImportError as e:
            raise RuntimeError(
                "Cannot import worker pipeline module. "
                "Ensure Celery dependencies are installed."
            ) from e


def register_pipeline_submitter(fn: PipelineSubmitter) -> None:
    """注册流水线提交器（由 Worker 层在初始化时调用）。"""
    global _submitter
    _submitter = fn


def submit_pipeline(task_id: str, video_path: str) -> None:
    """提交训练流水线。首次调用时自动加载 Worker 层。"""
    _ensure_submitter()
    if _submitter is None:
        raise RuntimeError(
            "Pipeline submitter not registered. "
            "Make sure the Worker layer is initialized before calling this."
        )
    _submitter(task_id, video_path)
