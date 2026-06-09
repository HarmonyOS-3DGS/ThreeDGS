"""Tests for task creation endpoint."""


class TestCreateTask:
    def _create_body(self):
        return {
            "externalCode": "EXT-001",
            "fileInfos": [
                {
                    "fileName": "test.mp4",
                    "sha256": "abc",
                    "contentLength": 16,
                    "fileUrl": "/tmp/test/test.mp4",
                }
            ],
            "scene": "indoor",
        }

    def test_create_task(self, client):
        body = self._create_body()
        response = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        assert response.status_code == 200
        data = response.json()
        assert data["ret"]["code"] == 0
        assert "taskId" in data
        assert len(data["fileInfos"]) == 1
        assert data["fileInfos"][0]["fileName"] == "test.mp4"

    def test_create_task_missing_required(self, client):
        body = {"externalCode": "EXT-001", "scene": "indoor"}
        response = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        assert response.status_code in (400, 422)

    def test_create_task_missing_project_id(self, client):
        body = self._create_body()
        response = client.post("/tasks", json=body)
        assert response.status_code == 422
