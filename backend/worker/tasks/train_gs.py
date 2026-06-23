"""Stage 3: 3D Gaussian Splatting 训练任务（Stub）。"""

import time

from backend.core.path_utils import task_output_path
from backend.core.repository import TaskRepository
from backend.worker.celery_app import app
from backend.worker.models.trainer import Trainer


@app.task(bind=True, time_limit=3600)
def train_gaussian_splatting(self, prev_result: dict, iterations: int = 30000):
    """Stub: 模拟 3DGS 训练并更新进度。"""
    task_id = prev_result["task_id"]
    TaskRepository.update_progress(task_id, "training", 50)

    for progress in range(50, 81, 5):
        try:
            self.update_state(
                state="PROGRESS",
                meta={"current": progress, "total": 100, "stage": "training"},
            )
        except Exception:
            pass
        TaskRepository.update_progress(task_id, "training", progress)
        time.sleep(1)

    try:
        output_dir = task_output_path(task_id, "models")
        model_path = Trainer.train(prev_result["colmap_dir"], output_dir, iterations)

        TaskRepository.update_progress(task_id, "training", 80)
        try:
            self.update_state(
                state="PROGRESS",
                meta={"current": 80, "total": 100, "stage": "training"},
            )
        except Exception:
            pass

        return {**prev_result, "model_path": model_path}
    except Exception as e:
        TaskRepository.update_progress(task_id, "training", 80, status="failed", error=str(e))
        raise
