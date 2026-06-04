"""Stage 1: Frame extraction task (stub)."""
import time
import os
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
        pass  # Allow tests without DB


@app.task(bind=True, max_retries=3, default_retry_delay=10)
def extract_frames(self, task_id: str, video_path: str, fps: int = 5):
    """Stub: Simulate FFmpeg frame extraction."""
    _update_task(task_id, "extracting", 10)
    try:
        self.update_state(state="PROGRESS", meta={"current": 10, "total": 100, "stage": "extracting"})
    except Exception:
        pass

    time.sleep(2)

    output_dir = f"/tmp/{task_id}/frames"
    Preprocessor.extract_frames(video_path, output_dir, fps)

    _update_task(task_id, "extracting", 25)
    try:
        self.update_state(state="PROGRESS", meta={"current": 25, "total": 100, "stage": "extracting"})
    except Exception:
        pass

    return {"task_id": task_id, "frames_dir": output_dir}
