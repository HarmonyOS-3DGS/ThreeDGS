"""Shared utilities for Celery tasks."""

import os

from backend.core.config import TASK_OUTPUT_DIR


def task_output_path(task_id: str, *parts: str) -> str:
    path = os.path.join(TASK_OUTPUT_DIR, str(task_id), *parts)
    return path


def find_newest_ply(search_dir: str, filename: str) -> str | None:
    """递归搜索指定文件名的 ply，返回最新的全路径。"""
    results = []
    for root, _dirs, files in os.walk(search_dir):
        for f in files:
            if f == filename:
                results.append(os.path.join(root, f))
    if not results:
        return None
    return max(results, key=os.path.getmtime)
