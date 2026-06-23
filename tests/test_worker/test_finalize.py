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

            with pytest.raises(ValueError, match="missing model_path"):
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


class TestRunFinalize:
    """run_finalize 纯函数直接测试。"""

    def test_raw_model(self):
        with patch("backend.worker.tasks.finalize.TaskRepository"):
            with patch("backend.worker.tasks.finalize.shutil") as mock_shutil:
                with patch("backend.worker.tasks.finalize.compress_model") as mock_compress:
                    from backend.worker.tasks.finalize import run_finalize

                    settings.output_types = ["raw_model"]
                    result = run_finalize("test-id", "/tmp/model.ply")
                    assert "raw_model" in result
                    mock_shutil.copy2.assert_called_once()
                    mock_compress.assert_not_called()

    def test_compress_formats(self):
        with patch("backend.worker.tasks.finalize.TaskRepository"):
            with patch(
                "backend.worker.tasks.finalize.compress_model",
                return_value={"spz": "/tmp/model.spz"},
            ) as mock_compress:
                from backend.worker.tasks.finalize import run_finalize

                settings.output_types = ["spz"]
                result = run_finalize("test-id", "/tmp/model.ply")
                assert "spz" in result
                mock_compress.assert_called_once()

    def test_all_formats(self):
        with patch("backend.worker.tasks.finalize.TaskRepository"):
            with patch("backend.worker.tasks.finalize.shutil") as mock_shutil:
                with patch(
                    "backend.worker.tasks.finalize.compress_model",
                    return_value={"spz": "/tmp/model.spz", "sog": "/tmp/model.sog"},
                ) as mock_compress:
                    from backend.worker.tasks.finalize import run_finalize

                    settings.output_types = ["raw_model", "spz", "sog"]
                    result = run_finalize("test-id", "/tmp/model.ply")
                    assert "raw_model" in result
                    assert "spz" in result
                    assert "sog" in result
                    mock_shutil.copy2.assert_called_once()
                    mock_compress.assert_called_once()

    def test_empty_output_types(self):
        with patch("backend.worker.tasks.finalize.TaskRepository"):
            with patch("backend.worker.tasks.finalize.shutil") as mock_shutil:
                with patch("backend.worker.tasks.finalize.compress_model") as mock_compress:
                    from backend.worker.tasks.finalize import run_finalize

                    settings.output_types = []
                    result = run_finalize("test-id", "/tmp/model.ply")
                    assert result == {}
                    mock_shutil.copy2.assert_not_called()
                    mock_compress.assert_not_called()

    def test_does_not_update_status(self):
        """run_finalize 不应调 update_progress（状态由调用方负责）。"""
        with patch("backend.worker.tasks.finalize.TaskRepository") as mock_repo:
            with patch("backend.worker.tasks.finalize.shutil"):
                with patch("backend.worker.tasks.finalize.compress_model"):
                    from backend.worker.tasks.finalize import run_finalize

                    settings.output_types = ["raw_model"]
                    run_finalize("test-id", "/tmp/model.ply")
                    status_calls = [
                        c
                        for c in mock_repo.update_progress.call_args_list
                        if c[1].get("status") in ("completed", "failed")
                    ]
                    assert len(status_calls) == 0
