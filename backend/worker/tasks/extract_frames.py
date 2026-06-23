"""Stage 1: 帧提取任务（Stub）。"""

import time

from backend.core.path_utils import task_output_path
from backend.core.repository import TaskRepository
from backend.worker.celery_app import app
from backend.worker.models.preprocessor import Preprocessor
from backend.worker.tasks.file_utils import ensure_input_video


@app.task(bind=True, max_retries=3, default_retry_delay=10)
def extract_frames(self, task_id: str, video_path: str, fps: int = 5):
    """Stub: Simulate FFmpeg frame extraction."""
    ensure_input_video(task_id)
    TaskRepository.update_progress(task_id, "extracting", 10)
    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 10, "total": 100, "stage": "extracting"},
        )
    except Exception:
        pass

    try:
        time.sleep(2)

        output_dir = task_output_path(task_id, "frames")
        Preprocessor.extract_frames(video_path, output_dir, fps)

        TaskRepository.update_progress(task_id, "extracting", 25)
        try:
            self.update_state(
                state="PROGRESS",
                meta={"current": 25, "total": 100, "stage": "extracting"},
            )
        except Exception:
            pass

        return {"task_id": task_id, "frames_dir": output_dir}
    except Exception as e:
        TaskRepository.update_progress(task_id, "extracting", 25, status="failed", error=str(e))
        raise
