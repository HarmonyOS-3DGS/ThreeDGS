"""Periodic task cleanup for expired tasks and model files."""

import logging
import os
import shutil

from backend.core.config import TASK_OUTPUT_DIR, settings
from backend.core.repository import TaskRepository
from backend.core.storage import storage
from backend.worker.celery_app import app

logger = logging.getLogger(__name__)


def _cleanup_storage(task_id: str):
    """删除对象存储和本地磁盘上的任务文件（含算法中间产物）。"""
    prefix = f"tasks/{task_id}/"
    try:
        objects = storage.list_objects(prefix)
        for obj in objects:
            try:
                storage.delete_object(obj)
                logger.info("cleanup: deleted MinIO object %s", obj)
            except Exception:
                pass
        if objects:
            logger.info("cleanup: task=%s deleted %d MinIO objects", task_id, len(objects))
    except Exception:
        pass
    task_dir = os.path.join(TASK_OUTPUT_DIR, str(task_id))
    if os.path.exists(task_dir):
        shutil.rmtree(task_dir, ignore_errors=True)
        logger.info("cleanup: task=%s deleted local dir %s", task_id, task_dir)
    alg2_dir = os.path.join(
        settings.alg_host_data_dir,
        settings.alg2_ply_userdata_rel,
        f"{settings.alg2_ply_subdir_prefix}{task_id}",
    )
    if os.path.exists(alg2_dir):
        shutil.rmtree(alg2_dir, ignore_errors=True)
        logger.info("cleanup: task=%s deleted alg2 dir %s", task_id, alg2_dir)


@app.task
def cleanup_pending_tasks():
    """清理长时间未启动的 pending 任务."""
    ids = TaskRepository.cleanup_expired_pending(settings.task_pending_ttl_hours)
    for tid in ids:
        _cleanup_storage(tid)


@app.task
def cleanup_stale_processing():
    """标记超时的 processing 任务为 failed，防止 Worker 崩溃后任务永久卡住。"""
    TaskRepository.cleanup_expired_processing()


@app.task
def cleanup_completed_tasks():
    """清理长时间未下载的 completed 任务及其输出文件."""
    ids = TaskRepository.cleanup_expired_completed(settings.task_completed_ttl_days)
    for tid in ids:
        _cleanup_storage(tid)
