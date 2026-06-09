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
                with patch("backend.worker.tasks.shared.SessionLocal") as MockSession:
                    with patch("backend.worker.tasks.compress.SessionLocal") as MockCompressSession:
                        mock_db = MockSession.return_value
                        mock_task = mock_db.query.return_value.filter.return_value.first.return_value
                        compress_result.run({"task_id": "test-id", "model_path": ply})
                        assert mock_task.status == "completed"
                        assert mock_task.progress == 100

    def test_compress_writes_output_taskfiles(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            ply = os.path.join(td, "model.ply")
            with open(ply, "w") as f:
                f.write("ply\n")
            with patch("backend.worker.tasks.compress.time.sleep"):
                with patch("backend.worker.tasks.shared.SessionLocal"):
                    with patch("backend.worker.tasks.compress.SessionLocal") as MockDB:
                        mock_session = MockDB.return_value
                        compress_result.run({"task_id": "test-id", "model_path": ply})
                        # 验证 TaskFile 被创建了两次（spz + sog），fileRole 为 compressed_model
                        calls = mock_session.add.call_args_list
                        assert len(calls) == 2
                        for call in calls:
                            tf = call[0][0]
                            assert tf.fileRole == "compressed_model"
                            assert tf.task_id == "test-id"
