"""Tests for SSE endpoint."""
import json
import pytest
from io import BytesIO

from backend.core.database import Task


class TestSSE:
    def _create_task(self, client):
        files_meta = json.dumps([{"original_filename": "t.mp4", "sha256": "abc", "file_size": 4}])
        return client.post(
            "/tasks",
            data={"external_code": "SSE-TEST", "files_meta": files_meta},
            files={"files": ("t.mp4", BytesIO(b"data"), "video/mp4")},
        )

    def test_sse_events(self, client, db_session):
        create = self._create_task(client)
        task_id = create.json()["task_id"]

        task = db_session.query(Task).filter(Task.id == task_id).first()
        task.status = "completed"
        task.current_stage = "completed"
        db_session.commit()

        response = client.get(f"/tasks/{task_id}/events")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_sse_nonexistent(self, client):
        response = client.get("/tasks/123e4567-e89b-12d3-a456-426614174000/events")
        assert response.status_code == 404
