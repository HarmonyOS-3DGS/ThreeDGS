"""通用输出处理器 — 替代原 compress.py 的 compress_result 任务。"""

import os
import shutil
import time

from backend.core.config import COMPRESSIBLE_FORMATS, settings
from backend.core.repository import TaskRepository
from backend.worker.celery_app import app
from backend.worker.compressor import compress_model
from backend.worker.tasks.shared import task_output_path


def _add_output_file(task_id: str, path: str, mime: str, file_role: str = "raw_model"):
    """上传到对象存储并写 DB。"""
    object_name = f"tasks/{task_id}/output/{os.path.basename(path)}"
    try:
        from backend.core.storage import storage

        storage.upload_file(object_name, path)
        file_url = object_name
    except Exception:
        file_url = path
    TaskRepository.add_output_file(task_id, path, mime, storage_url=file_url, file_role=file_role)


@app.task(bind=True, time_limit=600)
def finalize_outputs(self, prev_result: dict):
    """根据 output_types 配置输出最终文件：raw_model 直接复制，spz/sog 压缩后存入。"""
    task_id = prev_result["task_id"]
    ply_path = prev_result.get("model_path")
    if not ply_path:
        raise ValueError("prev_result missing model_path")

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

    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 95, "total": 100, "stage": "compressing"},
        )
    except Exception:
        pass

    TaskRepository.update_progress(task_id, "compressing", 95)
    time.sleep(1)
    TaskRepository.update_progress(task_id, "completed", 100, status="completed")

    try:
        self.update_state(
            state="SUCCESS",
            meta={"current": 100, "total": 100, "stage": "completed"},
        )
    except Exception:
        pass

    return {**prev_result, "outputs": outputs}
