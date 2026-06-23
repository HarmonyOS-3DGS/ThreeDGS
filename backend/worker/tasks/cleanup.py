"""Periodic task cleanup for expired tasks and model files.

DB 清理任务由 M1 Beat 定时发布到 Redis，任意 Worker 可执行。
本地文件清理由每个 Worker 进程内嵌的后台线程自动执行。
"""

import logging
import os
import shutil
import threading
import time
from datetime import datetime, timedelta

from backend.core.config import TASK_OUTPUT_DIR, settings
from backend.core.database import SessionLocal, Task, TaskStatus
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


def _cleanup_local_files():
    """查询 DB 中过期的任务，遍历本地目录，有则删除，无则跳过。不改 DB。"""
    cutoff = datetime.utcnow() - timedelta(days=settings.task_completed_ttl_days)
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task)
            .filter(
                Task.status.in_(
                    [
                        TaskStatus.PENDING.value,
                        TaskStatus.COMPLETED.value,
                        TaskStatus.FAILED.value,
                    ]
                ),
                Task.updated_at < cutoff,
            )
            .all()
        )
        for t in tasks:
            _cleanup_storage(t.id)
    finally:
        db.close()


def _cleanup_loop():
    """Worker 内嵌守护线程：每 30 分钟清理一次本地文件。首次立即执行。"""
    try:
        _cleanup_local_files()
    except Exception:
        logger.exception("local cleanup failed")
    while True:
        time.sleep(1800)
        try:
            _cleanup_local_files()
        except Exception:
            logger.exception("local cleanup failed")


def start_local_cleanup_scheduler():
    """在 Worker 进程中启动本地文件清理守护线程。"""
    t = threading.Thread(target=_cleanup_loop, daemon=True)
    t.start()
    logger.info("local cleanup scheduler started")


@app.task
def cleanup_pending_tasks():
    """清理长时间未启动的 pending 任务（仅 DB）。"""
    TaskRepository.cleanup_expired_pending(settings.task_pending_ttl_hours)


@app.task
def cleanup_stale_processing():
    """标记超时的 processing 任务为 failed，防止 Worker 崩溃后任务永久卡住。"""
    TaskRepository.cleanup_expired_processing()


@app.task
def cleanup_completed_tasks():
    """清理超时的 completed / failed 任务（仅 DB）。"""
    TaskRepository.cleanup_expired_completed(settings.task_completed_ttl_days)
