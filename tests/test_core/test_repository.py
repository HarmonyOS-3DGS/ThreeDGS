"""Tests for TaskRepository."""

import os
import tempfile
from datetime import datetime

import pytest

from backend.core.database import SessionLocal, Task, TaskFile
from backend.core.repository import TaskRepository


class TestAddOutputFile:
    def test_default_role_is_raw_model(self):
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test.ply")
            with open(fpath, "w") as f:
                f.write("test")
            tf = TaskRepository.add_output_file("test-id", fpath, "application/octet-stream")
            assert tf is not None
            assert tf.fileRole == "raw_model"
            _cleanup(tf)

    def test_custom_role(self):
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test.spz")
            with open(fpath, "w") as f:
                f.write("test")
            tf = TaskRepository.add_output_file(
                "test-id", fpath, "application/octet-stream", file_role="compressed_model"
            )
            assert tf is not None
            assert tf.fileRole == "compressed_model"
            _cleanup(tf)

    def test_storage_url_stored(self):
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test.ply")
            with open(fpath, "w") as f:
                f.write("test")
            tf = TaskRepository.add_output_file(
                "test-id", fpath, "application/octet-stream", storage_url="s3://bucket/key.ply"
            )
            assert tf is not None
            assert tf.fileUrl == "s3://bucket/key.ply"
            _cleanup(tf)


class TestFindFileByName:
    def test_default_role_is_raw_model(self):
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test.ply")
            with open(fpath, "w") as f:
                f.write("test")
            tf = TaskRepository.add_output_file("test-id-2", fpath, "application/octet-stream")
            assert tf is not None
            db = SessionLocal()
            try:
                result = TaskRepository(db).find_file_by_name("test-id-2", "test.ply")
                assert result is not None
                assert result.fileRole == "raw_model"
            finally:
                db.close()
            _cleanup(tf)


class TestClientIdFiltering:
    """Repository 的 client_id 过滤行为。"""

    @pytest.fixture(autouse=True)
    def _clean_tasks(self, db_session):
        db_session.query(Task).delete()
        db_session.commit()

    def test_create_stores_client_id(self, db_session):
        repo = TaskRepository(db_session)
        task = repo.create("proj-1", "ext-1", "indoor", client_id="partner-a")
        db_session.commit()
        assert task.client_id == "partner-a"

    def test_get_filters_by_client_id(self, db_session):
        repo = TaskRepository(db_session)
        t1 = repo.create("proj-1", "ext-a", "indoor", client_id="partner-a")
        repo.create("proj-1", "ext-b", "indoor", client_id="partner-b")
        db_session.commit()

        got = repo.get(t1.id, project_id="proj-1", client_id="partner-a")
        assert got is not None
        assert got.id == t1.id

        got_b = repo.get(t1.id, project_id="proj-1", client_id="partner-b")
        assert got_b is None

    def test_get_ignores_client_id_when_none(self, db_session):
        repo = TaskRepository(db_session)
        t = repo.create("proj-1", "ext", "indoor", client_id="partner-a")
        db_session.commit()

        got = repo.get(t.id, project_id="proj-1")
        assert got is not None
        assert got.id == t.id

    def test_list_by_project_filters_by_client_id(self, db_session):
        repo = TaskRepository(db_session)
        repo.create("proj-1", "ext-a", "indoor", client_id="partner-a")
        repo.create("proj-1", "ext-b", "indoor", client_id="partner-b")
        repo.create("proj-1", "ext-c", "indoor", client_id="partner-a")
        db_session.commit()

        tasks = repo.list_by_project("proj-1", client_id="partner-a")
        assert len(tasks) == 2

    def test_list_by_project_returns_all_when_no_client_id(self, db_session):
        repo = TaskRepository(db_session)
        repo.create("proj-1", "ext-a", "indoor", client_id="partner-a")
        repo.create("proj-1", "ext-b", "indoor", client_id="partner-b")
        db_session.commit()

        tasks = repo.list_by_project("proj-1")
        assert len(tasks) == 2


class TestEstimateQueueWait:
    """Tests for TaskRepository.estimate_queue_wait & cleanup_expired_processing."""

    @pytest.fixture(autouse=True)
    def _clean_tasks(self, db_session):
        db_session.query(Task).delete()
        db_session.commit()

    def test_no_tasks_ahead_returns_own_time(self, db_session):
        task = Task(
            project_id="proj-queue",
            external_code="q-0",
            scene="indoor",
            status="processing",
            progress=0,
        )
        db_session.add(task)
        db_session.commit()
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining == 100

    def test_pending_ahead_adds_queue_time(self, db_session):
        ahead = Task(
            project_id="proj-queue",
            external_code="q-ahead",
            scene="indoor",
            status="pending",
            created_at=datetime(2020, 1, 1),
        )
        task = Task(
            project_id="proj-queue",
            external_code="q-self",
            scene="indoor",
            status="pending",
            created_at=datetime(2020, 1, 2),
        )
        db_session.add_all([ahead, task])
        db_session.commit()
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining == 200

    def test_processing_ahead_adds_queue_time(self, db_session):
        ahead = Task(
            project_id="proj-queue",
            external_code="q-ahead",
            scene="indoor",
            status="processing",
            created_at=datetime(2020, 1, 1),
            updated_at=datetime.utcnow(),
        )
        task = Task(
            project_id="proj-queue",
            external_code="q-self",
            scene="indoor",
            status="pending",
            created_at=datetime(2020, 1, 2),
        )
        db_session.add_all([ahead, task])
        db_session.commit()
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining == 200

    def test_worker_count_divides_queue(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.worker_count", 2)
        ahead = Task(
            project_id="proj-queue",
            external_code="q-ahead",
            scene="indoor",
            status="pending",
            created_at=datetime(2020, 1, 1),
        )
        task = Task(
            project_id="proj-queue",
            external_code="q-self",
            scene="indoor",
            status="pending",
            created_at=datetime(2020, 1, 2),
        )
        db_session.add_all([ahead, task])
        db_session.commit()
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining == 150

    def test_progress_reduces_own_time(self, db_session):
        task = Task(
            project_id="proj-queue",
            external_code="q-progress",
            scene="indoor",
            status="processing",
            progress=50,
            created_at=datetime(2020, 1, 1),
        )
        db_session.add(task)
        db_session.commit()
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining == 50

    def test_cross_project_counted(self, db_session):
        other = Task(
            project_id="other-proj",
            external_code="other",
            scene="indoor",
            status="pending",
            created_at=datetime(2020, 1, 1),
        )
        task = Task(
            project_id="proj-queue",
            external_code="q-self",
            scene="indoor",
            status="pending",
            created_at=datetime(2020, 1, 2),
        )
        db_session.add_all([other, task])
        db_session.commit()
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining == 200

    def test_stale_processing_not_counted(self, db_session):
        stale = Task(
            project_id="proj-queue",
            external_code="q-stale",
            scene="indoor",
            status="processing",
            created_at=datetime(2020, 1, 1),
            updated_at=datetime(2020, 1, 1),
        )
        task = Task(
            project_id="proj-queue",
            external_code="q-self",
            scene="indoor",
            status="pending",
            created_at=datetime(2020, 1, 2),
        )
        db_session.add_all([stale, task])
        db_session.commit()
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining == 100

    def test_cleanup_expired_marks_failed(self):
        """cleanup_expired_processing 标记超时任务为 failed。"""
        stale = Task(
            project_id="proj-queue",
            external_code="q-stale",
            scene="indoor",
            status="processing",
            created_at=datetime(2020, 1, 1),
            updated_at=datetime(2020, 1, 1),
        )
        fresh = Task(
            project_id="proj-queue", external_code="q-fresh", scene="indoor", status="processing"
        )
        db = SessionLocal()
        try:
            db.add_all([stale, fresh])
            db.commit()
            ids = TaskRepository.cleanup_expired_processing()
            assert stale.id in ids
            db.refresh(stale)
            assert stale.status == "failed"
            assert stale.error_message == "任务执行超时，已被系统自动终止"
            db.refresh(fresh)
            assert fresh.status == "processing"
        finally:
            db.close()


def _cleanup(tf: TaskFile):
    db = SessionLocal()
    try:
        db.delete(tf)
        db.commit()
    finally:
        db.close()
