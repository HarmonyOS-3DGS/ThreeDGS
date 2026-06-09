"""Celery pipeline orchestration for 3DGS training."""
from celery import chain

from backend.core.config import settings
from backend.worker.tasks.extract_frames import extract_frames
from backend.worker.tasks.colmap_sfm import run_colmap
from backend.worker.tasks.train_gs import train_gaussian_splatting
from backend.worker.tasks.compress import compress_result
from backend.core.task_publisher import register_pipeline_submitter


def submit_training_pipeline(task_id: str, video_path: str):
    """Submit the 4-stage 3DGS training pipeline as a Celery task chain."""
    pipeline = chain(
        extract_frames.s(task_id, video_path, fps=settings.default_fps),
        run_colmap.s(),
        train_gaussian_splatting.s(iterations=settings.default_iterations),
        compress_result.s(),
    )
    return pipeline.apply_async()


# Worker 层初始化时向 Core 层注册自己
register_pipeline_submitter(submit_training_pipeline)
