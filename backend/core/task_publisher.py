"""Task publishing abstraction — 解耦 API 层与 Worker 层。

设计要点：
  - API 层调用 submit_pipeline()，不 import Celery
  - Worker 层启动时通过 register_pipeline_submitter() 注册实现
  - 首次调用时才懒加载 pipeline 模块（触发自动注册）
  - 类 GoF Bridge 模式：抽象与实现分离

数据流：
  API tasks.py                    Worker pipeline.py
      │                                    │
      │ submit_pipeline(task_id, path)     │ register_pipeline_submitter(fn)
      ▼                                    ▼
   task_publisher.py ──懒加载──▶ pipeline.submit_training_pipeline
"""

from collections.abc import Callable

PipelineSubmitter = Callable[[str, str], None]

_submitter: PipelineSubmitter | None = None


def _ensure_submitter():
    """首次调用时 import pipeline 模块，触发其 register 回调。"""
    global _submitter
    if _submitter is None:
        try:
            import backend.worker.tasks.pipeline  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "Cannot import worker pipeline module. Ensure Celery dependencies are installed."
            ) from e


def register_pipeline_submitter(fn: PipelineSubmitter) -> None:
    """Worker 层注册流水线提交器。由 pipeline.py 在模块导入时自动调用。"""
    global _submitter
    _submitter = fn


def submit_pipeline(task_id: str, video_path: str) -> None:
    """API 层调用此方法提交训练流水线。内部自动加载 Worker 层。"""
    _ensure_submitter()
    if _submitter is None:
        raise RuntimeError(
            "Pipeline submitter not registered. "
            "Make sure the Worker layer is initialized before calling this."
        )
    _submitter(task_id, video_path)
