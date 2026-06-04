"""Celery application configuration."""
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
        "backend.worker.tasks.compress",
        "backend.worker.tasks.pipeline",
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
)
