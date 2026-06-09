"""3DGS 训练流水线编排（Celery 四阶段链）。"""

from celery import chain

from backend.core.config import settings
from backend.core.task_publisher import register_pipeline_submitter
from backend.worker.tasks.colmap_sfm import run_colmap
from backend.worker.tasks.compress import compress_result
from backend.worker.tasks.extract_frames import extract_frames
from backend.worker.tasks.train_gs import train_gaussian_splatting


def submit_training_pipeline(task_id: str, video_path: str):
    """提交 4 阶段 3DGS 训练流水线。"""
    pipeline = chain(
        extract_frames.s(task_id, video_path, fps=settings.default_fps),
        run_colmap.s(),
        train_gaussian_splatting.s(iterations=settings.default_iterations),
        compress_result.s(),
    )
    return pipeline.apply_async()


# Worker 层初始化时向 Core 层注册自己
register_pipeline_submitter(submit_training_pipeline)
