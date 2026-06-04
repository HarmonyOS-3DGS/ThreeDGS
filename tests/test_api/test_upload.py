"""Tests for upload endpoint."""
import pytest
from io import BytesIO


class TestUpload:
    def test_upload_video(self, client):
        data = {"name": "test-project"}
        files = {"file": ("test.mp4", BytesIO(b"fake video data"), "video/mp4")}
        response = client.post("/upload", data=data, files=files)
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["name"] == "test-project"
        assert "id" in json_data
        assert json_data["status"] == "pending"

    def test_upload_without_file(self, client):
        response = client.post("/upload", data={"name": "test"})
        assert response.status_code == 422

    def test_upload_without_name(self, client):
        files = {"file": ("test.mp4", BytesIO(b"data"), "video/mp4")}
        response = client.post("/upload", data={}, files=files)
        assert response.status_code == 422
