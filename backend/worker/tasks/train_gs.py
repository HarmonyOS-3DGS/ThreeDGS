"""Stage 3: 3D Gaussian Splatting training task (stub)."""
import time
from backend.worker.celery_app import app
from backend.worker.models.trainer import Trainer
from backend.core.database import SessionLocal, Task


def _update_task(task_id: str, stage: str, progress: int):
    try:
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.current_stage = stage
                task.progress = progress
                db.commit()
        finally:
            db.close()
    except Exception:
        pass


@app.task(bind=True, time_limit=3600)
def train_gaussian_splatting(self, prev_result: dict, iterations: int = 30000):
    """Stub: Simulate 3DGS training with progress updates."""
    task_id = prev_result["task_id"]
    _update_task(task_id, "training", 50)

    for progress in range(50, 81, 5):
        try:
            self.update_state(
                state="PROGRESS",
                meta={"current": progress, "total": 100, "stage": "training"},
            )
        except Exception:
            pass
        _update_task(task_id, "training", progress)
        time.sleep(1)

    output_dir = f"/tmp/{task_id}/models"
    model_path = Trainer.train(prev_result["colmap_dir"], output_dir, iterations)

    _update_task(task_id, "training", 80)
    try:
        self.update_state(state="PROGRESS", meta={"current": 80, "total": 100, "stage": "training"})
    except Exception:
        pass

    return {**prev_result, "model_path": model_path}
