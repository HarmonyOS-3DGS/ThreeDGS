"""3DGS 训练流水线编排（Celery 四阶段链 / 外部算法一体化）。"""

import logging

from celery import chain

from backend.core.config import settings
from backend.core.database import Task  # database.py 重导出了 models.task.Task
from backend.core.task_publisher import register_pipeline_submitter
from backend.worker.tasks.colmap_sfm import run_colmap
from backend.worker.tasks.external_algorithm import run_external_algorithm
from backend.worker.tasks.extract_frames import extract_frames
from backend.worker.tasks.finalize import finalize_outputs
from backend.worker.tasks.train_gs import train_gaussian_splatting

logger = logging.getLogger(__name__)


def submit_training_pipeline(task_id: str, video_path: str):
    """提交训练流水线。按 scene 路由到不同算法。"""
    from backend.core.database import SessionLocal

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        scene = task.scene if task else ""
    finally:
        db.close()

    if settings.alg_enabled:
        if scene == "commodity":
            from backend.worker.tasks.commodity_algorithm import run_commodity_algorithm

            steps = [run_commodity_algorithm.s(task_id, video_path)]
            logger.info(
                "pipeline routing: task=%s scene=%s -> commodity_algorithm",
                task_id,
                scene,
            )
        else:
            steps = [run_external_algorithm.s(task_id, video_path)]
            logger.info(
                "pipeline routing: task=%s scene=%s -> external_algorithm",
                task_id,
                scene,
            )
    else:
        has_output = bool(settings.output_types)
        steps = [
            extract_frames.s(task_id, video_path, fps=settings.default_fps),
            run_colmap.s(),
            train_gaussian_splatting.s(iterations=settings.default_iterations),
        ]
        logger.info("pipeline routing: task=%s scene=%s -> stub chain", task_id, scene)
        if has_output:
            steps.append(finalize_outputs.s())

    pipeline = chain(*steps)
    return pipeline.apply_async()


# Worker 层初始化时向 Core 层注册自己
register_pipeline_submitter(submit_training_pipeline)
