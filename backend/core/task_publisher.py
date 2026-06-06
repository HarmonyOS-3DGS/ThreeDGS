"""Task publishing abstraction — decouples API layer from Worker layer.

API 层通过此模块提交训练任务，Worker 层在启动时注册具体实现。
这样 API 无需知道 Celery 的存在。
"""
from typing import Callable

# 类型别名: (task_id, video_path) -> None
PipelineSubmitter = Callable[[str, str], None]

_submitter: PipelineSubmitter | None = None


def register_pipeline_submitter(fn: PipelineSubmitter) -> None:
    """注册流水线提交器（由 Worker 层在初始化时调用）。"""
    global _submitter
    _submitter = fn


def submit_pipeline(task_id: str, video_path: str) -> None:
    """提交训练流水线。

    Raises:
        RuntimeError: 如果 Worker 层尚未注册提交器。
    """
    if _submitter is None:
        raise RuntimeError(
            "Pipeline submitter not registered. "
            "Make sure the Worker layer is initialized before calling this."
        )
    _submitter(task_id, video_path)
