"""Stage 4: Compression and finalization task (stub)."""
import time
from backend.worker.celery_app import app
from backend.worker.models.compressor import Compressor
from backend.core.database import SessionLocal, Project
from datetime import datetime


def _update_project(project_id: str, stage: str, progress: int, status: str = None, error: str = None):
    try:
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.current_stage = stage
                project.progress = progress
                if status:
                    project.status = status
                if error:
                    project.error_message = error
                if status == "completed":
                    project.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    except Exception:
        pass


@app.task(bind=True, time_limit=600)
def compress_result(self, prev_result: dict):
    """Stub: Simulate format compression and finalize project."""
    project_id = prev_result["project_id"]
    _update_project(project_id, "compressing", 85)
    try:
        self.update_state(state="PROGRESS", meta={"current": 85, "total": 100, "stage": "compressing"})
    except Exception:
        pass

    time.sleep(2)

    output_dir = f"/tmp/{project_id}/compressed"
    spz_path = Compressor.compress_ply_to_spz(prev_result["model_path"], output_dir)
    sog_path = Compressor.compress_ply_to_sog(prev_result["model_path"], output_dir)

    _update_project(project_id, "compressing", 95)
    try:
        self.update_state(state="PROGRESS", meta={"current": 95, "total": 100, "stage": "compressing"})
    except Exception:
        pass

    time.sleep(1)

    _update_project(project_id, "completed", 100, status="completed")
    try:
        self.update_state(state="SUCCESS", meta={"current": 100, "total": 100, "stage": "completed"})
    except Exception:
        pass

    return {
        **prev_result,
        "compressed_spz": spz_path,
        "compressed_sog": sog_path,
    }
