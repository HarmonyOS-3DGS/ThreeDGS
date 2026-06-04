"""Tests for project query endpoints."""
import pytest
from io import BytesIO


class TestProjects:
    def test_list_projects(self, client):
        # Create a project first
        client.post("/upload", data={"name": "list-test"}, files={"file": ("t.mp4", BytesIO(b"x"), "video/mp4")})
        response = client.get("/projects")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1

    def test_get_project(self, client):
        create = client.post("/upload", data={"name": "get-test"}, files={"file": ("t.mp4", BytesIO(b"x"), "video/mp4")})
        project_id = create.json()["id"]
        response = client.get(f"/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "get-test"

    def test_get_nonexistent_project(self, client):
        response = client.get("/projects/123e4567-e89b-12d3-a456-426614174000")
        assert response.status_code == 404
