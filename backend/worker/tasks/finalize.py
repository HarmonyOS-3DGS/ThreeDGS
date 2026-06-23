"""通用输出处理器 — 替代原 compress.py 的 compress_result 任务。

提供两个入口：
  1. run_finalize(task_id, ply_path) — 纯函数（不做状态更新），算法任务直接调用
  2. finalize_outputs(prev_result) — Celery 任务，仅 stub 链使用
"""

import logging
import os
import shutil
import time

from backend.core.config import COMPRESSIBLE_FORMATS, settings
from backend.core.path_utils import task_output_path
from backend.core.repository import TaskRepository
from backend.worker.celery_app import app
from backend.worker.compressor import compress_model

logger = logging.getLogger(__name__)


def _add_output_file(task_id: str, path: str, mime: str, file_role: str = "raw_model"):
    """上传到对象存储并写 DB，失败时打 warning 不阻断流程。"""
    object_name = f"tasks/{task_id}/output/{os.path.basename(path)}"
    try:
        from backend.core.storage import storage

        storage.upload_file(object_name, path)
        file_url = object_name
    except Exception:
        file_url = path
    result = TaskRepository.add_output_file(
        task_id, path, mime, storage_url=file_url, file_role=file_role
    )
    if result is None:
        logger.warning("add_output_file failed for task=%s path=%s", task_id, path)


def run_finalize(task_id: str, ply_path: str) -> dict[str, str]:
    """核心终化逻辑：复制/压缩模型、上传到存储、写 DB。

    算法任务在找到 PLY 后直接调用此函数，确保终化与算法在同一进程执行。

    **不做状态更新** — 调用方（算法任务 / finalize_outputs）负责
    在调用成功后设置 ``status="completed"``。

    Returns:
        dict of {output_type: local_path}

    Raises:
        任意 IO / DB 异常，由调用方处理
    """
    output_dir = task_output_path(task_id, "output")
    os.makedirs(output_dir, exist_ok=True)

    output_types = settings.output_types
    outputs: dict[str, str] = {}

    for t in output_types:
        if t == "raw_model":
            dest = os.path.join(output_dir, "model.ply")
            shutil.copy2(ply_path, dest)
            _add_output_file(task_id, dest, "application/octet-stream", file_role="raw_model")
            outputs[t] = dest

    compress_formats = [t for t in output_types if t in COMPRESSIBLE_FORMATS]
    if compress_formats:
        results = compress_model(ply_path, output_dir, compress_formats)
        for _fmt, path in results.items():
            _add_output_file(
                task_id, path, "application/octet-stream", file_role="compressed_model"
            )
            outputs[_fmt] = path

    return outputs


@app.task(bind=True, time_limit=600)
def finalize_outputs(self, prev_result: dict):
    """Celery 任务：stub 链终化。委托给 run_finalize() 后更新进度。"""
    task_id = prev_result["task_id"]
    ply_path = prev_result.get("model_path")
    if not ply_path:
        TaskRepository.update_progress(
            task_id, "failed", 0, status="failed", error="prev_result missing model_path"
        )
        raise ValueError("prev_result missing model_path")

    try:
        outputs = run_finalize(task_id, ply_path)
        TaskRepository.update_progress(task_id, "compressing", 95)
        time.sleep(1)
        TaskRepository.update_progress(task_id, "completed", 100, status="completed")
    except Exception as e:
        TaskRepository.update_progress(task_id, "failed", 0, status="failed", error=str(e))
        raise

    try:
        self.update_state(
            state="SUCCESS",
            meta={"current": 100, "total": 100, "stage": "completed"},
        )
    except Exception:
        pass

    return {**prev_result, "outputs": outputs}
