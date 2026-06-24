"""Tests for TaskRepository."""

import os
import tempfile
from datetime import datetime, timedelta

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
    @pytest.fixture(autouse=True)
    def _clean_tasks(self, db_session):
        db_session.query(Task).delete()
        db_session.commit()

    def _make_task(self, db_session, **kwargs):
        defaults = dict(
            project_id="proj-queue", external_code="t", scene="indoor", status="processing"
        )
        if "processing_started_at" not in kwargs:
            kwargs["processing_started_at"] = datetime.utcnow()
        task = Task(**{**defaults, **kwargs})
        db_session.add(task)
        db_session.commit()
        return task

    def _make_ahead(self, db_session, **kwargs):
        """创建 ahead 任务，processing_started_at 设为稍早于当前时间。"""
        defaults = dict(processing_started_at=datetime.utcnow() - timedelta(seconds=10))
        return self._make_task(db_session, **{**defaults, **kwargs})

    def test_no_tasks_ahead_returns_own_time(self, db_session):
        task = self._make_task(db_session)
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert abs(remaining - 100) <= 1

    def test_pending_ahead_not_counted(self, db_session):
        self._make_ahead(db_session, external_code="p-ahead", status="pending")
        task = self._make_task(db_session)
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert abs(remaining - 100) <= 1

    def test_processing_ahead_adds_queue(self, db_session):
        self._make_ahead(db_session, id="ahead-1", external_code="ahead")
        task = self._make_task(db_session, id="self-1", external_code="self")
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining > 100

    def test_worker_count_reduces_queue(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.worker_count", 3)
        self._make_ahead(db_session, id="ahead-1", external_code="ahead")
        task = self._make_task(db_session, id="self-1", external_code="self")
        r3 = TaskRepository.estimate_queue_wait(db_session, task, es=100)

        monkeypatch.setattr("backend.core.config.settings.worker_count", 1)
        r1 = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert r1 > r3

    def test_stale_processing_not_counted(self, db_session):
        ahead = Task(
            project_id="proj-queue",
            external_code="stale",
            scene="indoor",
            status="processing",
            processing_started_at=datetime(2020, 1, 1),
            updated_at=datetime(2020, 1, 1),
        )
        db_session.add(ahead)
        db_session.commit()
        task = self._make_task(db_session)
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert abs(remaining - 100) <= 1

    def test_multiple_ahead_water_pipe(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.worker_count", 2)
        for i in range(4):
            self._make_ahead(db_session, id=f"ahead-{i}", external_code=f"a{i}")
        task = self._make_task(db_session, id="self", external_code="self")
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100)
        assert remaining > 0

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


class TestExpectedDurationForScene:
    def test_stub_mode_returns_15(self, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.alg_enabled", False)
        assert TaskRepository._expected_duration_for_scene("indoor") == 15
        assert TaskRepository._expected_duration_for_scene("commodity") == 15
        assert TaskRepository._expected_duration_for_scene("outdoor") == 15

    def test_alg_commodity_returns_alg2(self, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.alg_enabled", True)
        monkeypatch.setattr("backend.core.config.settings.alg_expected_seconds", 960)
        monkeypatch.setattr("backend.core.config.settings.alg2_expected_seconds", 360)
        assert TaskRepository._expected_duration_for_scene("commodity") == 360

    def test_alg_other_scenes_returns_alg1(self, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.alg_enabled", True)
        monkeypatch.setattr("backend.core.config.settings.alg_expected_seconds", 960)
        monkeypatch.setattr("backend.core.config.settings.alg2_expected_seconds", 360)
        assert TaskRepository._expected_duration_for_scene("indoor") == 960
        assert TaskRepository._expected_duration_for_scene("outdoor") == 960


class TestQueueWaitIncludeQueue:
    @pytest.fixture(autouse=True)
    def _clean_tasks(self, db_session):
        db_session.query(Task).delete()
        db_session.commit()

    def _make_task(self, db_session, **kwargs):
        defaults = dict(
            project_id="proj-queue", external_code="t", scene="indoor", status="processing"
        )
        now = datetime.utcnow()
        task = Task(**{**defaults, "processing_started_at": now, **kwargs})
        db_session.add(task)
        db_session.commit()
        return task

    def test_include_queue_true_adds_queue(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.worker_count", 1)
        self._make_task(
            db_session, id="ahead", external_code="ahead", created_at=datetime(2020, 1, 1)
        )
        task = self._make_task(
            db_session, id="self", external_code="self", created_at=datetime(2020, 1, 2)
        )
        with_queue = TaskRepository.estimate_queue_wait(db_session, task, es=100, include_queue=True)
        without_queue = TaskRepository.estimate_queue_wait(
            db_session, task, es=100, include_queue=False
        )
        assert with_queue > without_queue

    def test_include_queue_false_returns_own_only(self, db_session):
        task = self._make_task(db_session)
        remaining = TaskRepository.estimate_queue_wait(db_session, task, es=100, include_queue=False)
        assert abs(remaining - 100) <= 1


class TestUpdateProgress:
    @pytest.fixture(autouse=True)
    def _clean_tasks(self, db_session):
        db_session.query(Task).delete()
        db_session.commit()

    def _create_task(self, db_session, **kwargs):
        defaults = dict(
            id="test-update-progress",
            project_id="proj-update",
            external_code="upd",
            scene="indoor",
            status="processing",
            current_stage="initializing",
            progress=0,
            remaining_time=0,
        )
        task = Task(**{**defaults, **kwargs})
        db_session.add(task)
        db_session.commit()
        return task

    def _read_task(self, db_session):
        return db_session.query(Task).filter(Task.id == "test-update-progress").first()

    def test_completed_sets_100(self, db_session):
        self._create_task(db_session, processing_started_at=datetime.utcnow())
        TaskRepository.update_progress("test-update-progress", "completed", 90, status="completed")
        task = self._read_task(db_session)
        assert task.progress == 100
        assert task.remaining_time == 0
        assert task.status == "completed"
        assert task.completed_at is not None

    def test_failed_keeps_explicit_progress(self, db_session):
        self._create_task(db_session, processing_started_at=datetime.utcnow())
        TaskRepository.update_progress("test-update-progress", "failed", 50, status="failed", error="oops")
        task = self._read_task(db_session)
        assert task.progress == 50
        assert task.status == "failed"
        assert task.error_message == "oops"

    def test_time_based_progress(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.alg_enabled", True)
        monkeypatch.setattr("backend.core.config.settings.alg_expected_seconds", 360)
        started_at = datetime.utcnow() - timedelta(seconds=30)
        self._create_task(db_session, processing_started_at=started_at, scene="indoor")
        TaskRepository.update_progress("test-update-progress", "training", 0)
        task = self._read_task(db_session)
        assert task.current_stage == "training"
        assert 0 < task.progress < 99
        assert task.remaining_time > 0

    def test_explicit_progress_acts_as_floor(self, db_session):
        started_at = datetime.utcnow() - timedelta(seconds=2)
        self._create_task(db_session, processing_started_at=started_at, progress=80)
        # Pass explicit progress=80, time-based will be low (~2s elapsed)
        TaskRepository.update_progress("test-update-progress", "training", 80)
        task = self._read_task(db_session)
        assert task.progress >= 80

    def test_monotonic_progress_never_decreases(self, db_session):
        started_at = datetime.utcnow() - timedelta(seconds=10)
        self._create_task(db_session, processing_started_at=started_at, progress=50)
        # First call stabilizes at some value
        TaskRepository.update_progress("test-update-progress", "training", 0)
        task_after_first = self._read_task(db_session)
        first_progress = task_after_first.progress

        # Second call immediately after should not reduce progress
        TaskRepository.update_progress("test-update-progress", "training", 0)
        task_after_second = self._read_task(db_session)
        assert task_after_second.progress >= first_progress

    def test_expected_seconds_used_when_passed(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.alg_enabled", True)
        monkeypatch.setattr("backend.core.config.settings.alg_expected_seconds", 9999)
        started_at = datetime.utcnow() - timedelta(seconds=10)
        self._create_task(db_session, processing_started_at=started_at, scene="indoor")
        # Pass expected_seconds=100 explicitly
        TaskRepository.update_progress(
            "test-update-progress", "training", 0, expected_seconds=100
        )
        task = self._read_task(db_session)
        # remaining would be ~90 if es=100 was used, not 9989
        assert task.remaining_time < 200

    def test_commodity_scene_auto_detects_es(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.alg_enabled", True)
        monkeypatch.setattr("backend.core.config.settings.alg_expected_seconds", 960)
        monkeypatch.setattr("backend.core.config.settings.alg2_expected_seconds", 360)
        started_at = datetime.utcnow() - timedelta(seconds=10)
        self._create_task(db_session, processing_started_at=started_at, scene="commodity")
        # No expected_seconds passed → should use _expected_duration_for_scene → 360
        TaskRepository.update_progress("test-update-progress", "training", 0)
        task = self._read_task(db_session)
        # remaining would be ~350 if 360 was used, not 950
        assert task.remaining_time < 600

    def test_processing_started_at_none_falls_back(self, db_session):
        self._create_task(db_session, processing_started_at=None)
        TaskRepository.update_progress("test-update-progress", "training", 42)
        task = self._read_task(db_session)
        assert task.progress >= 42


def _cleanup(tf: TaskFile):
    db = SessionLocal()
    try:
        db.delete(tf)
        db.commit()
    finally:
        db.close()
