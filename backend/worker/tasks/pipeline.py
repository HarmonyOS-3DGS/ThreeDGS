"""3DGS 训练流水线编排（Celery 四阶段链 / 外部算法一体化）。"""

from celery import chain

from backend.core.config import settings
from backend.core.task_publisher import register_pipeline_submitter
from backend.worker.tasks.colmap_sfm import run_colmap
from backend.worker.tasks.external_algorithm import run_external_algorithm
from backend.worker.tasks.extract_frames import extract_frames
from backend.worker.tasks.finalize import finalize_outputs
from backend.worker.tasks.train_gs import train_gaussian_splatting


def submit_training_pipeline(task_id: str, video_path: str):
    """提交训练流水线。alg_enabled=true 时走外部算法一体化。"""
    has_output = bool(settings.output_types)

    if settings.alg_enabled:
        steps = [run_external_algorithm.s(task_id, video_path)]
    else:
        steps = [
            extract_frames.s(task_id, video_path, fps=settings.default_fps),
            run_colmap.s(),
            train_gaussian_splatting.s(iterations=settings.default_iterations),
        ]

    if has_output:
        steps.append(finalize_outputs.s())

    pipeline = chain(*steps)
    return pipeline.apply_async()


# Worker 层初始化时向 Core 层注册自己
register_pipeline_submitter(submit_training_pipeline)
