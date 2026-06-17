"""Tests for SSE endpoint."""

from datetime import UTC, datetime, timedelta

import jwt

from backend.core.database import Task

_TEST_JWT = jwt.encode(
    {"client_id": "test-client", "exp": datetime.now(UTC) + timedelta(hours=1)},
    "test-jwt-secret",
    algorithm="HS256",
)


class TestSSE:
    def _create_task(self, client):
        body = {
            "externalCode": "SSE-TEST",
            "fileInfos": [
                {
                    "fileName": "t.mp4",
                    "sha256": "abc",
                    "contentLength": 4,
                    "fileUrl": "/tmp/test/t.mp4",
                }
            ],
            "scene": "indoor",
        }
        return client.post("/tasks", json=body, headers={"projectId": "proj-01"})

    def test_sse_events(self, client, db_session):
        create = self._create_task(client)
        task_id = create.json()["taskId"]

        task = db_session.query(Task).filter(Task.id == task_id).first()
        task.client_id = "test-client"
        task.status = "completed"
        task.current_stage = "completed"
        db_session.commit()

        headers = {"projectId": "proj-01", "Authorization": f"Bearer {_TEST_JWT}"}
        response = client.get(f"/tasks/{task_id}/events", headers=headers)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_sse_nonexistent(self, client):
        headers = {"projectId": "proj-01", "Authorization": f"Bearer {_TEST_JWT}"}
        response = client.get("/tasks/999999/events", headers=headers)
        assert response.status_code == 404
