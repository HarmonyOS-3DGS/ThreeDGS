"""Tests for finalize_outputs task."""

from unittest.mock import patch

from backend.core.config import settings


class TestFinalizeOutputs:
    def test_model_path_from_prev_result(self):
        with patch("backend.worker.tasks.finalize.TaskRepository"):
            with patch("backend.worker.tasks.finalize.shutil") as mock_shutil:
                with patch("backend.worker.tasks.finalize.compress_model") as mock_compress:
                    from backend.worker.tasks.finalize import finalize_outputs

                    settings.output_types = ["raw_model"]
                    result = finalize_outputs.run(
                        {"task_id": "test-id", "model_path": "/tmp/model.ply"}
                    )
                    assert result["task_id"] == "test-id"
                    assert "outputs" in result
                    mock_shutil.copy2.assert_called_once()
                    mock_compress.assert_not_called()

    def test_compress_formats(self):
        with patch("backend.worker.tasks.finalize.TaskRepository"):
            with patch(
                "backend.worker.tasks.finalize.compress_model",
                return_value={"spz": "/tmp/model.spz", "sog": "/tmp/model.sog"},
            ) as mock_compress:
                from backend.worker.tasks.finalize import finalize_outputs

                settings.output_types = ["spz", "sog"]
                result = finalize_outputs.run(
                    {"task_id": "test-id", "model_path": "/tmp/model.ply"}
                )
                assert "spz" in result["outputs"]
                assert "sog" in result["outputs"]
                mock_compress.assert_called_once()

    def test_all_formats(self):
        with patch("backend.worker.tasks.finalize.TaskRepository"):
            with patch("backend.worker.tasks.finalize.shutil") as mock_shutil:
                with patch(
                    "backend.worker.tasks.finalize.compress_model",
                    return_value={"spz": "/tmp/model.spz", "sog": "/tmp/model.sog"},
                ) as mock_compress:
                    from backend.worker.tasks.finalize import finalize_outputs

                    settings.output_types = ["raw_model", "spz", "sog"]
                    result = finalize_outputs.run(
                        {"task_id": "test-id", "model_path": "/tmp/model.ply"}
                    )
                    assert "raw_model" in result["outputs"]
                    assert "spz" in result["outputs"]
                    assert "sog" in result["outputs"]
                    mock_shutil.copy2.assert_called_once()
                    mock_compress.assert_called_once()

    def test_missing_model_path_raises_error(self):
        import pytest

        with patch("backend.worker.tasks.finalize.TaskRepository"):
            from backend.worker.tasks.finalize import finalize_outputs

            with pytest.raises(ValueError, match="缺少 model_path"):
                finalize_outputs.run({"task_id": "test-id"})

    def test_no_output_types_skips_everything(self):
        with patch("backend.worker.tasks.finalize.TaskRepository"):
            with patch("backend.worker.tasks.finalize.shutil") as mock_shutil:
                with patch("backend.worker.tasks.finalize.compress_model") as mock_compress:
                    from backend.worker.tasks.finalize import finalize_outputs

                    settings.output_types = []
                    result = finalize_outputs.run(
                        {"task_id": "test-id", "model_path": "/tmp/model.ply"}
                    )
                    assert result["outputs"] == {}
                    mock_shutil.copy2.assert_not_called()
                    mock_compress.assert_not_called()
