"""Stage 3: 3D Gaussian Splatting training task (stub)."""
import time
from backend.worker.celery_app import app
from backend.worker.models.trainer import Trainer
from backend.worker.tasks.shared import update_task, task_output_path


@app.task(bind=True, time_limit=3600)
def train_gaussian_splatting(self, prev_result: dict, iterations: int = 30000):
    """Stub: Simulate 3DGS training with progress updates."""
    task_id = prev_result["task_id"]
    update_task(task_id, "training", 50)

    for progress in range(50, 81, 5):
        try:
            self.update_state(state="PROGRESS", meta={"current": progress, "total": 100, "stage": "training"})
        except Exception:
            pass
        update_task(task_id, "training", progress)
        time.sleep(1)

    try:
        output_dir = task_output_path(task_id, "models")
        model_path = Trainer.train(prev_result["colmap_dir"], output_dir, iterations)

        update_task(task_id, "training", 80)
        try:
            self.update_state(state="PROGRESS", meta={"current": 80, "total": 100, "stage": "training"})
        except Exception:
            pass

        return {**prev_result, "model_path": model_path}
    except Exception as e:
        update_task(task_id, "training", 80, status="failed", error=str(e))
        raise
