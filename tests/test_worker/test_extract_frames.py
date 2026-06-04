"""Tests for extract_frames task."""
import pytest
from unittest.mock import patch
from backend.worker.tasks.extract_frames import extract_frames


class TestExtractFrames:
    def test_extract_frames_returns_paths(self):
        with patch("backend.worker.tasks.extract_frames.time.sleep"):
            result = extract_frames.run("test-id", "/tmp/test.mp4", fps=5)
        assert result["task_id"] == "test-id"
        assert "frames_dir" in result
        assert "/tmp/test-id/frames" in result["frames_dir"]

    def test_extract_frames_updates_progress(self):
        with patch("backend.worker.tasks.extract_frames.time.sleep"):
            with patch("backend.worker.tasks.extract_frames.SessionLocal") as MockSession:
                mock_db = MockSession.return_value
                mock_task = mock_db.query.return_value.filter.return_value.first.return_value
                extract_frames.run("test-id", "/tmp/test.mp4")
                assert mock_task.current_stage == "extracting"
                assert mock_task.progress == 25
