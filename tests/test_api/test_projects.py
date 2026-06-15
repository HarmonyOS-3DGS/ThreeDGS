"""Tests for task query and start endpoints."""

import sys

import pytest

from backend.core.database import TaskFile


class TestTasks:
    def _create_body(self):
        return {
            "externalCode": "T-001",
            "fileInfos": [
                {
                    "fileName": "test.mp4",
                    "sha256": "abc",
                    "contentLength": 4,
                    "fileUrl": "/tmp/test/test.mp4",
                }
            ],
            "scene": "indoor",
        }

    def _create_task(self, client, code="T-001"):
        body = self._create_body()
        body["externalCode"] = code
        return client.post("/tasks", json=body, headers={"projectId": "proj-01"})

    def _upload_first_file(self, client, create_resp):
        """上传第一个文件到本地端点，使 start 能通过文件存在检查。"""
        upload_info = create_resp.json()["uploadInfos"][0]
        url = upload_info["url"]
        if url.startswith("/"):
            client.put(url, content=b"dummy_data")
        return create_resp

    def test_create_and_query(self, client):
        create_resp = self._create_task(client)
        task_id = create_resp.json()["taskId"]

        resp = client.get(f"/tasks/{task_id}", headers={"projectId": "proj-01"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ret"]["code"] == 0
        assert data["status"] == "pending"

    def test_query_nonexistent(self, client):
        resp = client.get("/tasks/999999", headers={"projectId": "proj-01"})
        assert resp.status_code == 404

    def test_start_task(self, client):
        create_resp = self._create_task(client)
        self._upload_first_file(client, create_resp)
        task_id = create_resp.json()["taskId"]

        resp = client.post(f"/tasks/{task_id}/start", headers={"projectId": "proj-01"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ret"]["code"] == 0
        assert data["remainingTime"] == 15

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows asyncio/anyio crash bug")
    def test_start_already_started(self, client):
        create_resp = self._create_task(client)
        self._upload_first_file(client, create_resp)
        task_id = create_resp.json()["taskId"]

        client.post(f"/tasks/{task_id}/start", headers={"projectId": "proj-01"})
        resp = client.post(f"/tasks/{task_id}/start", headers={"projectId": "proj-01"})
        assert resp.status_code == 400

    def test_query_after_start(self, client):
        create_resp = self._create_task(client)
        self._upload_first_file(client, create_resp)
        task_id = create_resp.json()["taskId"]

        client.post(f"/tasks/{task_id}/start", headers={"projectId": "proj-01"})
        resp = client.get(f"/tasks/{task_id}", headers={"projectId": "proj-01"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    def test_query_download_infos_from_db(self, client, db_session):
        create_resp = self._create_task(client)
        task_id = create_resp.json()["taskId"]

        # 模拟 compress 阶段写入 output 文件记录
        tf = TaskFile(
            task_id=task_id,
            fileName="model.spz",
            sha256="",
            contentLength=100,
            fileUrl="/tmp/test.spz",
            fileRole="compressed_model",
            mimeType="application/octet-stream",
        )
        db_session.add(tf)
        db_session.commit()

        resp = client.get(f"/tasks/{task_id}", headers={"projectId": "proj-01"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["downloadInfos"]) == 1
        assert data["downloadInfos"][0]["fileName"] == "model.spz"
        assert data["downloadInfos"][0]["method"] == "GET"

    def test_query_raw_model_in_downloads(self, client, db_session):
        create_resp = self._create_task(client)
        task_id = create_resp.json()["taskId"]

        tf = TaskFile(
            task_id=task_id,
            fileName="model.ply",
            sha256="",
            contentLength=200,
            fileUrl="/tmp/model.ply",
            fileRole="raw_model",
            mimeType="application/octet-stream",
        )
        db_session.add(tf)
        db_session.commit()

        resp = client.get(f"/tasks/{task_id}", headers={"projectId": "proj-01"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["downloadInfos"]) == 1
        assert data["downloadInfos"][0]["fileName"] == "model.ply"

    def test_query_mixed_roles(self, client, db_session):
        create_resp = self._create_task(client)
        task_id = create_resp.json()["taskId"]

        for role, fname in [("raw_model", "model.ply"), ("compressed_model", "model.spz")]:
            tf = TaskFile(
                task_id=task_id,
                fileName=fname,
                sha256="",
                contentLength=100,
                fileUrl=f"/tmp/{fname}",
                fileRole=role,
                mimeType="application/octet-stream",
            )
            db_session.add(tf)
        db_session.commit()

        resp = client.get(f"/tasks/{task_id}", headers={"projectId": "proj-01"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["downloadInfos"]) == 2
