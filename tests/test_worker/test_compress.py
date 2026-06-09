"""Tests for compress task."""
import pytest
from unittest.mock import patch
from backend.worker.tasks.compress import compress_result


class TestCompress:
    def test_compress_returns_paths(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            ply = os.path.join(td, "model.ply")
            with open(ply, "w") as f:
                f.write("ply\n")
            with patch("backend.worker.tasks.compress.time.sleep"):
                result = compress_result.run(
                    {"task_id": "test-id", "model_path": ply}
                )
        assert "compressed_spz" in result
        assert "compressed_sog" in result

    def test_compress_updates_status(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            ply = os.path.join(td, "model.ply")
            with open(ply, "w") as f:
                f.write("ply\n")
            with patch("backend.worker.tasks.compress.time.sleep"):
                with patch("backend.worker.tasks.shared.TaskRepository.update_progress") as mock_update:
                    with patch("backend.worker.tasks.compress.TaskRepository.add_output_file"):
                        compress_result.run({"task_id": "test-id", "model_path": ply})
                        # 验证最终状态更新为 completed
                        complete_calls = [c for c in mock_update.call_args_list
                                          if c[1].get("status") == "completed"]
                        assert len(complete_calls) == 1

    def test_compress_writes_output_taskfiles(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            ply = os.path.join(td, "model.ply")
            with open(ply, "w") as f:
                f.write("ply\n")
            with patch("backend.worker.tasks.compress.time.sleep"):
                with patch("backend.worker.tasks.shared.TaskRepository.update_progress"):
                    with patch("backend.worker.tasks.compress.TaskRepository.add_output_file") as mock_add:
                        compress_result.run({"task_id": "test-id", "model_path": ply})
                        assert mock_add.call_count == 2
                        for call in mock_add.call_args_list:
                            assert call[0][0] == "test-id"
