"""Celery 应用配置与 Beat 定时任务调度。"""

from celery import Celery
from celery.signals import worker_process_init

from backend.core.config import settings
from backend.core.logging import LOG_CONFIG

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
        "backend.worker.tasks.commodity_algorithm",
    ],
)


@worker_process_init.connect
def _start_local_cleanup(**kwargs):
    """每个 Worker 进程启动时，自动拉起本地文件清理守护线程。"""
    from backend.worker.tasks.cleanup import start_local_cleanup_scheduler

    start_local_cleanup_scheduler()


app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    worker_hijack_root_logger=False,
    worker_logconfig=LOG_CONFIG,
    beat_schedule={
        "cleanup-pending-tasks": {
            "task": "backend.worker.tasks.cleanup.cleanup_pending_tasks",
            "schedule": 1800.0,  # 30 分钟
        },
        "cleanup-stale-processing": {
            "task": "backend.worker.tasks.cleanup.cleanup_stale_processing",
            "schedule": 300.0,  # 5 分钟
        },
        "cleanup-completed-tasks": {
            "task": "backend.worker.tasks.cleanup.cleanup_completed_tasks",
            "schedule": 3600.0,  # 1 小时
        },
    },
)
