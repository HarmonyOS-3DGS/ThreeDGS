"""Stage 4: Compression and finalization task (stub)."""
import os
import time
from backend.worker.celery_app import app
from backend.worker.models.compressor import Compressor
from backend.worker.tasks.shared import update_task, task_output_path
from backend.core.database import SessionLocal, TaskFile


def _add_output_file(task_id: str, path: str, mime: str):
    try:
        db = SessionLocal()
        try:
            tf = TaskFile(
                task_id=task_id,
                fileName=os.path.basename(path),
                sha256="",
                contentLength=os.path.getsize(path),
                fileUrl=path,
                fileRole="compressed_model",
                mimeType=mime,
            )
            db.add(tf)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


@app.task(bind=True, time_limit=600)
def compress_result(self, prev_result: dict):
    """Stub: Simulate format compression and finalize task."""
    task_id = prev_result["task_id"]
    update_task(task_id, "compressing", 85)
    try:
        self.update_state(state="PROGRESS", meta={"current": 85, "total": 100, "stage": "compressing"})
    except Exception:
        pass

    try:
        time.sleep(2)

        output_dir = task_output_path(task_id, "compressed")
        spz_path = Compressor.compress_ply_to_spz(prev_result["model_path"], output_dir)
        sog_path = Compressor.compress_ply_to_sog(prev_result["model_path"], output_dir)

        _add_output_file(task_id, spz_path, "application/octet-stream")
        _add_output_file(task_id, sog_path, "application/octet-stream")

        update_task(task_id, "compressing", 95)
        try:
            self.update_state(state="PROGRESS", meta={"current": 95, "total": 100, "stage": "compressing"})
        except Exception:
            pass

        time.sleep(1)

        update_task(task_id, "completed", 100, status="completed")
        try:
            self.update_state(state="SUCCESS", meta={"current": 100, "total": 100, "stage": "completed"})
        except Exception:
            pass

        return {**prev_result, "compressed_spz": spz_path, "compressed_sog": sog_path}
    except Exception as e:
        update_task(task_id, "compressing", 95, status="failed", error=str(e))
        raise
