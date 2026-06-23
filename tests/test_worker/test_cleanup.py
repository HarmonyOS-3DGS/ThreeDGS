"""Tests for cleanup tasks."""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

from backend.core.database import Task, TaskStatus
from backend.worker.tasks.cleanup import (
    _cleanup_local_files,
    _cleanup_storage,
    cleanup_completed_tasks,
    cleanup_pending_tasks,
)


class TestCleanupLocalFiles:
    def test_cleanup_expired_tasks(self, db_session):
        old = datetime.utcnow() - timedelta(days=35)
        fresh = datetime.utcnow() - timedelta(days=1)
        for i, (status, updated) in enumerate(
            [
                (TaskStatus.PENDING, old),
                (TaskStatus.COMPLETED, old),
                (TaskStatus.FAILED, old),
                (TaskStatus.PENDING, fresh),
                (TaskStatus.COMPLETED, fresh),
                (TaskStatus.FAILED, fresh),
            ]
        ):
            db_session.add(
                Task(
                    id=f"local-{i}",
                    project_id="proj-01",
                    external_code="",
                    scene="indoor",
                    status=status.value,
                    updated_at=updated,
                )
            )
        db_session.commit()

        called = []

        def fake_storage(tid):
            called.append(tid)

        with patch("backend.worker.tasks.cleanup._cleanup_storage", side_effect=fake_storage):
            _cleanup_local_files()

        assert set(called) == {"local-0", "local-1", "local-2"}  # only old ones

    def test_cleanup_skips_processing(self, db_session):
        task = Task(
            id="local-10",
            project_id="proj-01",
            external_code="",
            scene="indoor",
            status=TaskStatus.PROCESSING.value,
            updated_at=datetime.utcnow() - timedelta(days=35),
        )
        db_session.add(task)
        db_session.commit()

        called = []
        with patch(
            "backend.worker.tasks.cleanup._cleanup_storage",
            side_effect=lambda tid: called.append(tid),
        ):
            _cleanup_local_files()

        assert "local-10" not in called  # processing 任务不会被清理


class TestCleanupStorage:
    def test_cleanup_local_task_dir(self):
        with tempfile.TemporaryDirectory() as td:
            task_dir = os.path.join(td, "test-101")
            os.makedirs(task_dir)
            open(os.path.join(task_dir, "video.mp4"), "w").close()

            with patch("backend.worker.tasks.cleanup.TASK_OUTPUT_DIR", td):
                with patch("backend.worker.tasks.cleanup.storage.list_objects", return_value=[]):
                    _cleanup_storage("test-101")

            assert not os.path.exists(task_dir)

    def test_cleanup_alg2_dir(self):
        with tempfile.TemporaryDirectory() as td:
            alg2_dir = os.path.join(td, "dist_so", "UserData", "test_task_id_tasks_test-102")
            os.makedirs(alg2_dir)
            open(os.path.join(alg2_dir, "recon_result.ply"), "w").close()

            with patch("backend.worker.tasks.cleanup.storage.list_objects", return_value=[]):
                with patch("backend.worker.tasks.cleanup.settings.alg_host_data_dir", td):
                    _cleanup_storage("test-102")

            assert not os.path.exists(alg2_dir)

    def test_cleanup_minio_objects(self):
        with tempfile.TemporaryDirectory() as td:
            task_dir = os.path.join(td, "tasks", "test-103")
            os.makedirs(task_dir)

            mock_objects = ["tasks/test-103/video.mp4", "tasks/test-103/output/model.ply"]
            deleted = []

            def fake_delete(obj):
                deleted.append(obj)

            with patch("backend.worker.tasks.cleanup.TASK_OUTPUT_DIR", td):
                with patch(
                    "backend.worker.tasks.cleanup.storage.list_objects", return_value=mock_objects
                ):
                    with patch(
                        "backend.worker.tasks.cleanup.storage.delete_object",
                        side_effect=fake_delete,
                    ):
                        _cleanup_storage("test-103")

            assert set(deleted) == set(mock_objects)

    def test_cleanup_skip_nonexistent(self):
        with patch("backend.worker.tasks.cleanup.storage.list_objects", return_value=[]):
            with patch("backend.worker.tasks.cleanup.TASK_OUTPUT_DIR", "/nonexistent"):
                _cleanup_storage("test-999")  # should not crash


class TestCleanupPending:
    def test_cleanup_expired_pending(self, db_session):
        task = Task(
            id="test-cleanup-001",
            project_id="proj-01",
            external_code="EXPIRED",
            scene="indoor",
            status=TaskStatus.PENDING.value,
            created_at=datetime.utcnow() - timedelta(hours=25),
        )
        db_session.add(task)
        db_session.commit()

        cleanup_pending_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-001").first()
        assert remaining is None

    def test_keep_fresh_pending(self, db_session):
        task = Task(
            id="test-cleanup-002",
            project_id="proj-01",
            external_code="FRESH",
            scene="indoor",
            status=TaskStatus.PENDING.value,
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(task)
        db_session.commit()

        cleanup_pending_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-002").first()
        assert remaining is not None
        assert remaining.status == "pending"

    def test_skip_non_pending(self, db_session):
        task = Task(
            id="test-cleanup-003",
            project_id="proj-01",
            external_code="PROCESSING",
            scene="indoor",
            status=TaskStatus.PROCESSING.value,
            created_at=datetime.utcnow() - timedelta(hours=25),
        )
        db_session.add(task)
        db_session.commit()

        cleanup_pending_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-003").first()
        assert remaining is not None


class TestCleanupCompleted:
    def test_cleanup_expired_completed(self, db_session):
        task = Task(
            id="test-cleanup-004",
            project_id="proj-01",
            external_code="OLD-DONE",
            scene="indoor",
            status=TaskStatus.COMPLETED.value,
            updated_at=datetime.utcnow() - timedelta(days=8),
        )
        db_session.add(task)
        db_session.commit()

        cleanup_completed_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-004").first()
        assert remaining is None

    def test_keep_fresh_completed(self, db_session):
        task = Task(
            id="test-cleanup-005",
            project_id="proj-01",
            external_code="FRESH-DONE",
            scene="indoor",
            status=TaskStatus.COMPLETED.value,
        )
        db_session.add(task)
        db_session.commit()

        cleanup_completed_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-005").first()
        assert remaining is not None

    def test_cleanup_expired_failed(self, db_session):
        task = Task(
            id="test-cleanup-006",
            project_id="proj-01",
            external_code="OLD-FAILED",
            scene="indoor",
            status=TaskStatus.FAILED.value,
            updated_at=datetime.utcnow() - timedelta(days=8),
        )
        db_session.add(task)
        db_session.commit()

        cleanup_completed_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-006").first()
        assert remaining is None

    def test_keep_fresh_failed(self, db_session):
        task = Task(
            id="test-cleanup-007",
            project_id="proj-01",
            external_code="FRESH-FAILED",
            scene="indoor",
            status=TaskStatus.FAILED.value,
        )
        db_session.add(task)
        db_session.commit()

        cleanup_completed_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-007").first()
        assert remaining is not None
