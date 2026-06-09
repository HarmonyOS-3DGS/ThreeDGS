"""Tests for extract_frames task."""

from unittest.mock import patch

from backend.worker.tasks.extract_frames import extract_frames


class TestExtractFrames:
    def test_extract_frames_returns_paths(self):
        with patch("backend.worker.tasks.extract_frames.time.sleep"):
            result = extract_frames.run("test-id", "/tmp/test.mp4", fps=5)
        assert result["task_id"] == "test-id"
        assert "frames_dir" in result
        assert "tasks" in result["frames_dir"]

    def test_extract_frames_updates_progress(self):
        with patch("backend.worker.tasks.extract_frames.time.sleep"):
            with patch(
                "backend.worker.tasks.extract_frames.TaskRepository.update_progress"
            ) as mock_update:
                extract_frames.run("test-id", "/tmp/test.mp4")
                assert mock_update.call_count >= 2
                # 第一次调用: stage=extracting, progress=10
                assert mock_update.call_args_list[0][0] == ("test-id", "extracting", 10)
