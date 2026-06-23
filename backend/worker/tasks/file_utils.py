"""File-related utilities for Celery tasks: video download, PLY search."""

import logging
import os
import time

from backend.core.constants import SUPPORTED_VIDEO_EXTS
from backend.core.path_utils import task_output_path

logger = logging.getLogger(__name__)

_DOWNLOAD_BACKOFF = [1, 2, 4]
_DOWNLOAD_RETRIES = len(_DOWNLOAD_BACKOFF)


def ensure_input_video(task_id: str) -> str:
    """确保算法输入目录存在视频文件，不存在则从存储下载（带退避重试）。

    Returns:
        本地视频文件路径

    Raises:
        FileNotFoundError: DB 无文件记录或下载重试耗尽
    """
    local_dir = task_output_path(task_id, "")
    os.makedirs(local_dir, exist_ok=True)

    for f in os.listdir(local_dir):
        if f.lower().endswith(SUPPORTED_VIDEO_EXTS):
            logger.info("input video already exists: %s", f)
            return os.path.join(local_dir, f)

    from backend.core.database import SessionLocal
    from backend.core.models.task_file import TaskFile

    db = SessionLocal()
    try:
        task_file = (
            db.query(TaskFile)
            .filter(TaskFile.task_id == task_id, TaskFile.fileRole == "source_video")
            .first()
        )
        if not task_file:
            task_file = db.query(TaskFile).filter(TaskFile.task_id == task_id).first()
            if task_file:
                logger.info("fallback to file: %s (role=%s)", task_file.fileName, task_file.fileRole)
        if not task_file:
            raise FileNotFoundError(f"task {task_id}: no files in DB")
    finally:
        db.close()

    from backend.core.storage import storage

    local_path = os.path.join(local_dir, task_file.fileName)
    last_err = None
    for attempt, delay in enumerate(_DOWNLOAD_BACKOFF, 1):
        try:
            logger.info(
                "downloading video from storage %s -> %s (attempt %d/%d)",
                task_file.fileUrl,
                local_path,
                attempt,
                _DOWNLOAD_RETRIES,
            )
            storage.download_file(task_file.fileUrl, local_path)
            if not os.path.isfile(local_path):
                raise OSError(f"download completed but file not found: {local_path}")
            logger.info("download complete: %s", local_path)
            return local_path
        except Exception as e:
            last_err = e
            logger.warning("download attempt %d failed: %s, retry in %ds", attempt, e, delay)
            if attempt < _DOWNLOAD_RETRIES:
                time.sleep(delay)

    raise FileNotFoundError(
        f"task {task_id}: download failed after {_DOWNLOAD_RETRIES} retries: {last_err}"
    )


def find_newest_ply(search_dir: str, filename: str) -> str | None:
    """递归搜索指定文件名的 ply，返回最新的全路径。"""
    results = []
    try:
        for root, _dirs, files in os.walk(search_dir):
            for f in files:
                if f == filename:
                    results.append(os.path.join(root, f))
    except PermissionError:
        logger.warning("permission denied searching: %s", search_dir)
    except OSError:
        logger.warning("error searching directory: %s", search_dir)
    if not results:
        return None
    return max(results, key=os.path.getmtime)
