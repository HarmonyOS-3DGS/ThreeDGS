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
        assert len(data["uploadInfos"]) == 1
        assert data["uploadInfos"][0]["fileName"] == "test.mp4"

    def test_create_task_missing_required(self, client):
        body = {"externalCode": "EXT-001", "scene": "indoor"}
        response = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        assert response.status_code in (400, 422)

    def test_create_task_missing_project_id(self, client):
        body = self._create_body()
        response = client.post("/tasks", json=body)
        assert response.status_code == 422

    def test_uploadinfos_has_url_and_method(self, client):
        body = self._create_body()
        resp = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        info = resp.json()["uploadInfos"][0]
        assert "url" in info
        assert "method" in info
        assert info["method"] == "PUT"

    def test_upload_file_endpoint(self, client):
        body = self._create_body()
        resp = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        info = resp.json()["uploadInfos"][0]
        put_resp = client.put(info["url"], content=b"dummy_video_data")
        assert put_resp.status_code == 200

    def test_upload_duplicate_fails(self, client):
        body = self._create_body()
        resp = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        info = resp.json()["uploadInfos"][0]
        client.put(info["url"], content=b"dummy")
        dup = client.put(info["url"], content=b"dummy")
        assert dup.status_code == 400

    def test_full_upload_and_start_flow(self, client):
        body = self._create_body()
        create = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        task_id = create.json()["taskId"]
        # upload
        info = create.json()["uploadInfos"][0]
        client.put(info["url"], content=b"dummy")
        # start
        start = client.post(f"/tasks/{task_id}/start", headers={"projectId": "proj-01"})
        assert start.status_code == 200
        # query
        query = client.get(f"/tasks/{task_id}", headers={"projectId": "proj-01"})
        assert query.json()["status"] == "processing"

    def test_create_with_multiple_files(self, client):
        body = self._create_body()
        body["fileInfos"].append({
            "fileName": "frame_001.jpg", "sha256": "", "contentLength": 0,
            "fileUrl": "", "fileRole": "source_images",
        })
        resp = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        assert resp.status_code == 200
        assert len(resp.json()["uploadInfos"]) == 2

    def test_start_without_upload_fails(self, client):
        body = self._create_body()
        resp = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        task_id = resp.json()["taskId"]
        start = client.post(f"/tasks/{task_id}/start", headers={"projectId": "proj-01"})
        assert start.status_code == 400

    def test_download_not_found(self, client):
        resp = client.get("/tasks/999999/download/nonexistent.spz",
                          headers={"projectId": "proj-01"})
        assert resp.status_code == 404

    def test_uploadinfos_has_objectid(self, client):
        body = self._create_body()
        resp = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        info = resp.json()["uploadInfos"][0]
        assert info["objectId"] == "test.mp4"

    def test_create_invalid_scene(self, client):
        body = self._create_body()
        body["scene"] = "invalid"
        resp = client.post("/tasks", json=body, headers={"projectId": "proj-01"})
        assert resp.status_code == 422
