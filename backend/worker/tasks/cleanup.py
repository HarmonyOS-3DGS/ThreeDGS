"""Periodic task cleanup for expired tasks and model files."""
import os
import shutil

from backend.worker.celery_app import app
from backend.core.config import settings, TASK_OUTPUT_DIR
from backend.core.repository import TaskRepository


@app.task
def cleanup_pending_tasks():
    """清理长时间未启动的 pending 任务."""
    ids = TaskRepository.cleanup_expired_pending(settings.task_pending_ttl_hours)
    for tid in ids:
        task_dir = os.path.join(TASK_OUTPUT_DIR, str(tid))
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)


@app.task
def cleanup_completed_tasks():
    """清理长时间未下载的 completed 任务及其输出文件."""
    ids = TaskRepository.cleanup_expired_completed(settings.task_completed_ttl_days)
    for tid in ids:
        task_dir = os.path.join(TASK_OUTPUT_DIR, str(tid))
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
