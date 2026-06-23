"""Stage 2: COLMAP SfM 任务（Stub）。"""

import time

from backend.core.path_utils import task_output_path
from backend.core.repository import TaskRepository
from backend.worker.celery_app import app
from backend.worker.models.preprocessor import Preprocessor


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_colmap(self, prev_result: dict):
    """Stub: 模拟 COLMAP SfM。"""
    task_id = prev_result["task_id"]
    TaskRepository.update_progress(task_id, "colmap", 30)
    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 30, "total": 100, "stage": "colmap"},
        )
    except Exception:
        pass

    try:
        time.sleep(3)

        output_dir = task_output_path(task_id, "colmap")
        Preprocessor.run_colmap(prev_result["frames_dir"], output_dir)

        TaskRepository.update_progress(task_id, "colmap", 45)
        try:
            self.update_state(
                state="PROGRESS",
                meta={"current": 45, "total": 100, "stage": "colmap"},
            )
        except Exception:
            pass

        return {**prev_result, "colmap_dir": output_dir}
    except Exception as e:
        TaskRepository.update_progress(task_id, "colmap", 45, status="failed", error=str(e))
        raise
