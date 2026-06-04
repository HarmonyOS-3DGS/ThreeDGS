"""Stage 4: Compression and finalization task (stub)."""
import time
from backend.worker.celery_app import app
from backend.worker.models.compressor import Compressor
from backend.core.database import SessionLocal, Task
from datetime import datetime


def _update_task(task_id: str, stage: str, progress: int, status: str = None, error: str = None):
    try:
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.current_stage = stage
                task.progress = progress
                task.remaining_time = max(0, 15 - progress // 7)
                if status:
                    task.status = status
                if error:
                    task.error_message = error
                if status == "completed":
                    task.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    except Exception:
        pass


@app.task(bind=True, time_limit=600)
def compress_result(self, prev_result: dict):
    """Stub: Simulate format compression and finalize task."""
    task_id = prev_result["task_id"]
    _update_task(task_id, "compressing", 85)
    try:
        self.update_state(state="PROGRESS", meta={"current": 85, "total": 100, "stage": "compressing"})
    except Exception:
        pass

    time.sleep(2)

    output_dir = f"/tmp/{task_id}/compressed"
    spz_path = Compressor.compress_ply_to_spz(prev_result["model_path"], output_dir)
    sog_path = Compressor.compress_ply_to_sog(prev_result["model_path"], output_dir)

    _update_task(task_id, "compressing", 95)
    try:
        self.update_state(state="PROGRESS", meta={"current": 95, "total": 100, "stage": "compressing"})
    except Exception:
        pass

    time.sleep(1)

    _update_task(task_id, "completed", 100, status="completed")
    try:
        self.update_state(state="SUCCESS", meta={"current": 100, "total": 100, "stage": "completed"})
    except Exception:
        pass

    return {
        **prev_result,
        "compressed_spz": spz_path,
        "compressed_sog": sog_path,
    }
