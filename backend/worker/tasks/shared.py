"""Shared utilities for Celery tasks."""
import os

from backend.core.config import TASK_OUTPUT_DIR


def task_output_path(task_id: str, *parts: str) -> str:
    path = os.path.join(TASK_OUTPUT_DIR, str(task_id), *parts)
    return path
