"""Tests for pipeline orchestration."""

from unittest.mock import MagicMock, patch

from backend.core.config import settings
from backend.worker.tasks.pipeline import submit_training_pipeline


def _make_mock_task(scene: str = "indoor"):
    """创建一个 mock Task 对象，模拟 DB 查询返回。"""
    return MagicMock(scene=scene)


class TestPipeline:
    def test_pipeline_chain(self):
        with (
            patch("backend.worker.tasks.pipeline.chain") as mock_chain,
            patch("backend.core.database.SessionLocal") as mock_db,
        ):
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = (
                _make_mock_task("indoor")
            )
            mock_task = mock_chain.return_value.apply_async.return_value
            mock_task.id = "task-123"
            result = submit_training_pipeline("task-1", "/tmp/vid.mp4")
            assert result.id == "task-123"
            mock_chain.assert_called_once()

    def test_alg_disabled_chain_length(self):
        with (
            patch("backend.worker.tasks.pipeline.chain") as mock_chain,
            patch("backend.core.database.SessionLocal") as mock_db,
        ):
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = (
                _make_mock_task("indoor")
            )
            settings.alg_enabled = False
            settings.output_types = ["raw_model"]
            submit_training_pipeline("task-1", "/tmp/vid.mp4")
            args, _ = mock_chain.call_args
            assert len(args) == 4

    def test_alg_enabled_chain_length(self):
        with (
            patch("backend.worker.tasks.pipeline.chain") as mock_chain,
            patch("backend.core.database.SessionLocal") as mock_db,
        ):
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = (
                _make_mock_task("indoor")
            )
            settings.alg_enabled = True
            settings.output_types = ["raw_model"]
            submit_training_pipeline("task-1", "/tmp/vid.mp4")
            args, _ = mock_chain.call_args
            assert len(args) == 1  # 只有算法任务，finalize 已内联

    def test_no_output_skips_finalize(self):
        with (
            patch("backend.worker.tasks.pipeline.chain") as mock_chain,
            patch("backend.core.database.SessionLocal") as mock_db,
        ):
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = (
                _make_mock_task("indoor")
            )
            settings.alg_enabled = False
            settings.output_types = []
            submit_training_pipeline("task-1", "/tmp/vid.mp4")
            args, _ = mock_chain.call_args
            assert len(args) == 3

    def test_commodity_routing(self):
        """commodity 场景 → chain 含 run_commodity_algorithm（无 finalize_outputs）。"""
        with (
            patch("backend.worker.tasks.pipeline.chain") as mock_chain,
            patch("backend.core.database.SessionLocal") as mock_db,
        ):
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = (
                _make_mock_task("commodity")
            )
            settings.alg_enabled = True
            settings.output_types = ["raw_model"]
            submit_training_pipeline("task-1", "/tmp/vid.mp4")
            args, _ = mock_chain.call_args
            assert len(args) == 1  # 只有算法任务
            task_name = args[0].name
            assert "commodity_algorithm" in task_name

    def test_indoor_routing(self):
        """indoor 场景 → chain 含 run_external_algorithm（无 finalize_outputs）。"""
        with (
            patch("backend.worker.tasks.pipeline.chain") as mock_chain,
            patch("backend.core.database.SessionLocal") as mock_db,
        ):
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = (
                _make_mock_task("indoor")
            )
            settings.alg_enabled = True
            settings.output_types = ["raw_model"]
            submit_training_pipeline("task-1", "/tmp/vid.mp4")
            args, _ = mock_chain.call_args
            assert len(args) == 1  # 只有算法任务
            task_name = args[0].name
            assert "external_algorithm" in task_name
