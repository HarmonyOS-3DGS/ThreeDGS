"""Stage 1: Frame extraction task (stub)."""
import time
import os
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
        pass  # Allow tests without DB


@app.task(bind=True, max_retries=3, default_retry_delay=10)
def extract_frames(self, project_id: str, video_path: str, fps: int = 5):
    """Stub: Simulate FFmpeg frame extraction."""
    _update_project(project_id, "extracting_frames", 10)
    try:
        self.update_state(state="PROGRESS", meta={"current": 10, "total": 100, "stage": "extracting"})
    except Exception:
        pass

    # Simulate work
    time.sleep(2)

    output_dir = f"/tmp/{project_id}/frames"
    Preprocessor.extract_frames(video_path, output_dir, fps)

    _update_project(project_id, "extracting_frames", 25)
    try:
        self.update_state(state="PROGRESS", meta={"current": 25, "total": 100, "stage": "extracting"})
    except Exception:
        pass

    return {"project_id": project_id, "frames_dir": output_dir}
