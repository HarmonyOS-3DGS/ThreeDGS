"""Tests for file_utils: ensure_input_video, find_newest_ply."""

import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.worker.tasks.file_utils import ensure_input_video, find_newest_ply


class TestFindNewestPly:
    def test_finds_ply_in_subdir(self):
        with tempfile.TemporaryDirectory() as td:
            subdir = os.path.join(td, "nested", "subdir")
            os.makedirs(subdir, exist_ok=True)
            ply1 = os.path.join(subdir, "result.ply")
            with open(ply1, "w") as f:
                f.write("old")
            time.sleep(0.01)
            ply2 = os.path.join(td, "result.ply")
            with open(ply2, "w") as f:
                f.write("new")
            result = find_newest_ply(td, "result.ply")
            assert result == ply2

    def test_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            result = find_newest_ply(td, "nonexistent.ply")
            assert result is None

    def test_returns_none_when_dir_missing(self):
        result = find_newest_ply("/nonexistent/path", "result.ply")
        assert result is None


class TestEnsureInputVideo:
    def test_already_exists(self):
        with tempfile.TemporaryDirectory() as td:
            task_id = "test-001"
            video_dir = os.path.join(td, "tasks", task_id)
            os.makedirs(video_dir, exist_ok=True)
            existing = os.path.join(video_dir, "video.mp4")
            with open(existing, "w") as f:
                f.write("existing")

            with (
                patch("backend.worker.tasks.file_utils.task_output_path") as mock_path,
                patch("backend.core.storage.storage") as mock_storage,
            ):
                mock_path.return_value = video_dir
                result = ensure_input_video(task_id)
                assert result == existing
                mock_storage.download_file.assert_not_called()

    def test_download_from_storage(self):
        with tempfile.TemporaryDirectory() as td:
            task_id = "test-002"
            video_dir = os.path.join(td, "tasks", task_id)
            os.makedirs(video_dir, exist_ok=True)

            mock_file = MagicMock()
            mock_file.fileName = "video.mp4"
            mock_file.fileUrl = "tasks/test-002/video.mp4"
            mock_file.fileRole = "source_video"

            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_query.filter.return_value = mock_filter
            mock_filter.first.return_value = mock_file

            mock_session = MagicMock()
            mock_session.query.return_value = mock_query

            with (
                patch("backend.worker.tasks.file_utils.task_output_path") as mock_path,
                patch("backend.core.database.SessionLocal") as mock_session_local,
                patch("backend.core.storage.storage") as mock_storage,
                patch("backend.worker.tasks.file_utils.os.path.isfile", return_value=True),
            ):
                mock_path.return_value = video_dir
                mock_session_local.return_value = mock_session

                result = ensure_input_video(task_id)
                assert result == os.path.join(video_dir, "video.mp4")
                mock_storage.download_file.assert_called_once_with(
                    "tasks/test-002/video.mp4",
                    os.path.join(video_dir, "video.mp4"),
                )
                mock_session.close.assert_called_once()

    def test_no_db_record(self):
        with tempfile.TemporaryDirectory() as td:
            task_id = "test-003"
            video_dir = os.path.join(td, "tasks", task_id)
            os.makedirs(video_dir, exist_ok=True)

            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_query.filter.return_value = mock_filter
            mock_filter.first.return_value = None

            mock_session = MagicMock()
            mock_session.query.return_value = mock_query

            with (
                patch("backend.worker.tasks.file_utils.task_output_path") as mock_path,
                patch("backend.core.database.SessionLocal") as mock_session_local,
            ):
                mock_path.return_value = video_dir
                mock_session_local.return_value = mock_session

                with pytest.raises(FileNotFoundError, match=r"no files in DB"):
                    ensure_input_video(task_id)
                mock_session.close.assert_called_once()

    def test_download_retries_exhausted(self):
        with tempfile.TemporaryDirectory() as td:
            task_id = "test-004"
            video_dir = os.path.join(td, "tasks", task_id)
            os.makedirs(video_dir, exist_ok=True)

            mock_file = MagicMock()
            mock_file.fileName = "video.mp4"
            mock_file.fileUrl = "tasks/test-004/video.mp4"
            mock_file.fileRole = "source_video"

            mock_filter = MagicMock()
            mock_filter.first.return_value = mock_file

            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value = mock_filter

            with (
                patch("backend.worker.tasks.file_utils.task_output_path") as mock_path,
                patch("backend.core.database.SessionLocal") as mock_session_local,
                patch("backend.core.storage.storage") as mock_storage,
                patch("backend.worker.tasks.file_utils.time.sleep"),
            ):
                mock_path.return_value = video_dir
                mock_session_local.return_value = mock_session
                mock_storage.download_file.side_effect = OSError("connection refused")

                with pytest.raises(FileNotFoundError, match=r"download failed after 3 retries"):
                    ensure_input_video(task_id)

                assert mock_storage.download_file.call_count == 3
