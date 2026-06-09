"""Tests for cleanup tasks."""

from datetime import datetime, timedelta

from backend.core.database import Task, TaskStatus
from backend.worker.tasks.cleanup import cleanup_completed_tasks, cleanup_pending_tasks


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
            completed_at=datetime.utcnow() - timedelta(days=8),
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
            completed_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(task)
        db_session.commit()

        cleanup_completed_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-005").first()
        assert remaining is not None

    def test_skip_none_completed(self, db_session):
        task = Task(
            id="test-cleanup-006",
            project_id="proj-01",
            external_code="FAILED",
            scene="indoor",
            status=TaskStatus.FAILED.value,
            completed_at=datetime.utcnow() - timedelta(days=8),
        )
        db_session.add(task)
        db_session.commit()

        cleanup_completed_tasks.run()

        remaining = db_session.query(Task).filter(Task.id == "test-cleanup-006").first()
        assert remaining is not None
