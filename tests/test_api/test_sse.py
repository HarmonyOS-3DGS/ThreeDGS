"""Tests for SSE endpoint."""
import pytest
from io import BytesIO

from backend.core.database import Project


class TestSSE:
    def test_sse_events(self, client, db_session):
        create = client.post("/upload", data={"name": "sse-test"}, files={"file": ("t.mp4", BytesIO(b"x"), "video/mp4")})
        project_id = create.json()["id"]

        # Mark project as completed so SSE generator exits immediately
        project = db_session.query(Project).filter(Project.id == project_id).first()
        project.status = "completed"
        project.current_stage = "completed"
        db_session.commit()

        response = client.get(f"/projects/{project_id}/events")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_sse_nonexistent_project(self, client):
        response = client.get("/projects/123e4567-e89b-12d3-a456-426614174000/events")
        assert response.status_code == 404
