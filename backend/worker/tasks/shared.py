"""Shared utilities for Celery tasks."""
import logging
import os

from backend.core.config import settings, TASK_OUTPUT_DIR
from backend.core.repository import TaskRepository

logger = logging.getLogger(__name__)


def update_task(task_id: str, stage: str, progress: int, status: str = None, error: str = None):
    try:
        TaskRepository.update_progress(task_id, stage, progress, status=status, error=error)
    except Exception as e:
        logger.warning(f"更新任务 {task_id} 失败: {e}")


def task_output_path(task_id: str, *parts: str) -> str:
    path = os.path.join(TASK_OUTPUT_DIR, str(task_id), *parts)
    return path
