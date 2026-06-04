"""Stage 2: COLMAP SfM task (stub)."""
import time
from backend.worker.celery_app import app
from backend.worker.models.preprocessor import Preprocessor
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


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_colmap(self, prev_result: dict):
    """Stub: Simulate COLMAP Structure-from-Motion."""
    task_id = prev_result["task_id"]
    _update_task(task_id, "colmap", 30)
    try:
        self.update_state(state="PROGRESS", meta={"current": 30, "total": 100, "stage": "colmap"})
    except Exception:
        pass

    time.sleep(3)

    output_dir = f"/tmp/{task_id}/colmap"
    Preprocessor.run_colmap(prev_result["frames_dir"], output_dir)

    _update_task(task_id, "colmap", 45)
    try:
        self.update_state(state="PROGRESS", meta={"current": 45, "total": 100, "stage": "colmap"})
    except Exception:
        pass

    return {**prev_result, "colmap_dir": output_dir}
