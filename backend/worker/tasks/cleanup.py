"""Periodic task cleanup for expired tasks and model files."""
import os
import shutil
from datetime import datetime, timedelta

from backend.worker.celery_app import app
from backend.core.database import SessionLocal, Task, TaskFile, TaskStatus
from backend.core.config import settings
from backend.worker.tasks.shared import TASK_OUTPUT_DIR


@app.task
def cleanup_pending_tasks():
    """清理长时间未启动的 pending 任务."""
    ttl_hours = settings.task_pending_ttl_hours
    cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)

    db = SessionLocal()
    try:
        expired = db.query(Task).filter(
            Task.status == TaskStatus.PENDING.value,
            Task.created_at < cutoff,
        ).all()

        for task in expired:
            if os.path.exists(task_dir := os.path.join(TASK_OUTPUT_DIR, str(task.id))):
                shutil.rmtree(task_dir, ignore_errors=True)
            db.query(TaskFile).filter(TaskFile.task_id == task.id).delete()
            db.delete(task)

        if expired:
            db.commit()
    finally:
        db.close()


@app.task
def cleanup_completed_tasks():
    """清理长时间未下载的 completed 任务及其输出文件."""
    ttl_days = settings.task_completed_ttl_days
    cutoff = datetime.utcnow() - timedelta(days=ttl_days)

    db = SessionLocal()
    try:
        expired = db.query(Task).filter(
            Task.status == TaskStatus.COMPLETED.value,
            Task.completed_at < cutoff,
        ).all()

        for task in expired:
            if os.path.exists(task_dir := os.path.join(TASK_OUTPUT_DIR, str(task.id))):
                shutil.rmtree(task_dir, ignore_errors=True)
            db.query(TaskFile).filter(TaskFile.task_id == task.id).delete()
            db.delete(task)

        if expired:
            db.commit()
    finally:
        db.close()
