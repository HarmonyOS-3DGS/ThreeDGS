"""Celery 应用配置与 Beat 定时任务调度。"""

from celery import Celery

from backend.core.config import settings

app = Celery(
    "3dgs",
    broker=settings.celery_broker_url or "memory://",
    backend=settings.celery_result_backend or "cache+memory://",
    include=[
        "backend.worker.tasks.extract_frames",
        "backend.worker.tasks.colmap_sfm",
        "backend.worker.tasks.train_gs",
        "backend.worker.tasks.finalize",
        "backend.worker.tasks.pipeline",
        "backend.worker.tasks.cleanup",
        "backend.worker.tasks.external_algorithm",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "cleanup-pending-tasks": {
            "task": "backend.worker.tasks.cleanup.cleanup_pending_tasks",
            "schedule": 1800.0,  # 30 分钟
        },
        "cleanup-completed-tasks": {
            "task": "backend.worker.tasks.cleanup.cleanup_completed_tasks",
            "schedule": 3600.0,  # 1 小时
        },
    },
)
