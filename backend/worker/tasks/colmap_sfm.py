"""Stage 2: COLMAP SfM task (stub)."""
import time
from backend.worker.celery_app import app
from backend.worker.models.preprocessor import Preprocessor
from backend.core.database import SessionLocal, Project


def _update_project(project_id: str, stage: str, progress: int):
    try:
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.current_stage = stage
                project.progress = progress
                db.commit()
        finally:
            db.close()
    except Exception:
        pass


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_colmap(self, prev_result: dict):
    """Stub: Simulate COLMAP Structure-from-Motion."""
    project_id = prev_result["project_id"]
    _update_project(project_id, "colmap_sfm", 30)
    try:
        self.update_state(state="PROGRESS", meta={"current": 30, "total": 100, "stage": "colmap"})
    except Exception:
        pass

    time.sleep(3)

    output_dir = f"/tmp/{project_id}/colmap"
    Preprocessor.run_colmap(prev_result["frames_dir"], output_dir)

    _update_project(project_id, "colmap_sfm", 45)
    try:
        self.update_state(state="PROGRESS", meta={"current": 45, "total": 100, "stage": "colmap"})
    except Exception:
        pass

    return {**prev_result, "colmap_dir": output_dir}
