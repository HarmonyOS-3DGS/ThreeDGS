"""Tests for pipeline orchestration."""

from unittest.mock import patch

from backend.worker.tasks.pipeline import submit_training_pipeline


class TestPipeline:
    def test_pipeline_chain(self):
        with patch("backend.worker.tasks.pipeline.chain") as mock_chain:
            mock_task = mock_chain.return_value.apply_async.return_value
            mock_task.id = "task-123"
            result = submit_training_pipeline("task-1", "/tmp/vid.mp4")
            assert result.id == "task-123"
            mock_chain.assert_called_once()
