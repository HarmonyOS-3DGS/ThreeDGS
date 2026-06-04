"""Tests for task creation endpoint."""
import json
import pytest
from io import BytesIO


class TestCreateTask:
    def test_create_task(self, client):
        files_meta = json.dumps([{"original_filename": "test.mp4", "sha256": "abc", "file_size": 16}])
        response = client.post(
            "/tasks",
            data={"external_code": "EXT-001", "files_meta": files_meta},
            files={"files": ("test.mp4", BytesIO(b"fake video data"), "video/mp4")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert len(data["files"]) == 1
        assert data["files"][0]["original_filename"] == "test.mp4"
        assert data["files"][0]["file_path"] != ""

    def test_create_task_without_external_code(self, client):
        response = client.post("/tasks", data={})
        assert response.status_code == 422

    def test_create_task_meta_file_mismatch(self, client):
        files_meta = json.dumps([
            {"original_filename": "a.mp4", "sha256": "x", "file_size": 1},
            {"original_filename": "b.mp4", "sha256": "y", "file_size": 2},
        ])
        response = client.post(
            "/tasks",
            data={"external_code": "EXT-002", "files_meta": files_meta},
            files={"files": ("a.mp4", BytesIO(b"data"), "video/mp4")},
        )
        assert response.status_code == 400
