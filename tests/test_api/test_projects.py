"""Tests for task query and start endpoints."""
import json
import pytest
from io import BytesIO


class TestTasks:
    def _create_task(self, client, code="T-001"):
        files_meta = json.dumps([{"original_filename": "test.mp4", "sha256": "abc", "file_size": 4}])
        return client.post(
            "/tasks",
            data={"external_code": code, "files_meta": files_meta},
            files={"files": ("test.mp4", BytesIO(b"data"), "video/mp4")},
        )

    def test_create_and_query(self, client):
        create_resp = self._create_task(client)
        task_id = create_resp.json()["task_id"]

        resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"

    def test_query_nonexistent(self, client):
        resp = client.get("/tasks/123e4567-e89b-12d3-a456-426614174000")
        assert resp.status_code == 404

    def test_start_task(self, client):
        create_resp = self._create_task(client)
        task_id = create_resp.json()["task_id"]

        resp = client.post(f"/tasks/{task_id}/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["msg"] == "success"
        assert data["remaining_time"] == 15

    def test_start_already_started(self, client):
        create_resp = self._create_task(client)
        task_id = create_resp.json()["task_id"]

        client.post(f"/tasks/{task_id}/start")
        resp = client.post(f"/tasks/{task_id}/start")
        assert resp.status_code == 400

    def test_query_after_start(self, client):
        create_resp = self._create_task(client)
        task_id = create_resp.json()["task_id"]

        client.post(f"/tasks/{task_id}/start")
        resp = client.get(f"/tasks/{task_id}")
        assert resp.json()["status"] == "processing"
