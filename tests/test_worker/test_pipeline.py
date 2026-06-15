"""Tests for pipeline orchestration."""

from unittest.mock import patch

from backend.core.config import settings
from backend.worker.tasks.pipeline import submit_training_pipeline


class TestPipeline:
    def test_pipeline_chain(self):
        with patch("backend.worker.tasks.pipeline.chain") as mock_chain:
            mock_task = mock_chain.return_value.apply_async.return_value
            mock_task.id = "task-123"
            result = submit_training_pipeline("task-1", "/tmp/vid.mp4")
            assert result.id == "task-123"
            mock_chain.assert_called_once()

    def test_alg_disabled_chain_length(self):
        with patch("backend.worker.tasks.pipeline.chain") as mock_chain:
            settings.alg_enabled = False
            settings.output_types = ["raw_model"]
            submit_training_pipeline("task-1", "/tmp/vid.mp4")
            args, _ = mock_chain.call_args
            assert len(args) == 4

    def test_alg_enabled_chain_length(self):
        with patch("backend.worker.tasks.pipeline.chain") as mock_chain:
            settings.alg_enabled = True
            settings.output_types = ["raw_model"]
            submit_training_pipeline("task-1", "/tmp/vid.mp4")
            args, _ = mock_chain.call_args
            assert len(args) == 2

    def test_no_output_skips_finalize(self):
        with patch("backend.worker.tasks.pipeline.chain") as mock_chain:
            settings.alg_enabled = False
            settings.output_types = []
            submit_training_pipeline("task-1", "/tmp/vid.mp4")
            args, _ = mock_chain.call_args
            assert len(args) == 3
