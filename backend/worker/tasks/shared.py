"""Shared utilities for Celery tasks."""
import logging
import os
from datetime import datetime

from backend.core.database import SessionLocal, Task
from backend.core.config import settings, TASK_OUTPUT_DIR

logger = logging.getLogger(__name__)


def update_task(task_id: str, stage: str, progress: int, status: str = None, error: str = None):
    try:
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.current_stage = stage
                task.progress = progress
                task.remaining_time = 0 if status == "completed" else max(0, 15 - progress // 7)
                if status:
                    task.status = status
                if error:
                    task.error_message = error
                if status == "completed":
                    task.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"更新任务 {task_id} 失败: {e}")


def task_output_path(task_id: str, *parts: str) -> str:
    path = os.path.join(TASK_OUTPUT_DIR, str(task_id), *parts)
    return path
