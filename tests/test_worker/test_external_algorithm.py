"""Tests for external_algorithm task."""

import os
import tempfile
import time
from unittest.mock import MagicMock, patch

from backend.worker.tasks.external_algorithm import _find_newest_ply


class TestFindNewestPly:
    def test_finds_ply_in_subdir(self):
        with tempfile.TemporaryDirectory() as td:
            subdir = os.path.join(
                td, "gaussian_splatting", "out", "train", "grid_0_0", "point_cloud"
            )
            os.makedirs(subdir, exist_ok=True)
            ply1 = os.path.join(subdir, "point_cloud.ply")
            with open(ply1, "w") as f:
                f.write("old")
            time.sleep(0.01)
            ply2 = os.path.join(td, "nested", "point_cloud.ply")
            os.makedirs(os.path.dirname(ply2), exist_ok=True)
            with open(ply2, "w") as f:
                f.write("new")
            result = _find_newest_ply(td, "point_cloud.ply")
            assert result == ply2

    def test_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            result = _find_newest_ply(td, "point_cloud.ply")
            assert result is None

    def test_returns_none_when_dir_missing(self):
        result = _find_newest_ply("/nonexistent/path", "point_cloud.ply")
        assert result is None


class TestExternalAlgorithmTask:
    def test_docker_success(self):
        with patch("backend.worker.tasks.external_algorithm.docker.from_env") as mock_docker:
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = []
            mock_docker.return_value.containers.run.return_value = mock_container
            with patch("backend.worker.tasks.external_algorithm._find_newest_ply") as mock_find:
                mock_find.return_value = "/tmp/test.ply"
                with patch(
                    "backend.worker.tasks.external_algorithm.TaskRepository.update_progress"
                ):
                    from backend.worker.tasks.external_algorithm import run_external_algorithm

                    result = run_external_algorithm.run("test-id", "/tmp/test.mp4")
                    assert result["task_id"] == "test-id"
                    assert result["model_path"] == "/tmp/test.ply"
                    mock_container.wait.assert_called_once()
                    mock_container.remove.assert_called_once()
                    mock_container.logs.assert_called_once_with(stream=True, follow=True)

    def test_docker_failure(self):
        with patch("backend.worker.tasks.external_algorithm.docker.from_env") as mock_docker:
            mock_docker.return_value.containers.run.side_effect = Exception("crash")
            with patch(
                "backend.worker.tasks.external_algorithm.TaskRepository.update_progress"
            ) as mock_up:
                from backend.worker.tasks.external_algorithm import run_external_algorithm

                result = run_external_algorithm.run("test-id", "/tmp/test.mp4")
                assert "error" in result
                calls = mock_up.call_args_list
                failed_call = [c for c in calls if c[1].get("status") == "failed"]
                assert len(failed_call) == 1

    def test_ply_not_found_after_success(self):
        with patch("backend.worker.tasks.external_algorithm.docker.from_env") as mock_docker:
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = []
            mock_docker.return_value.containers.run.return_value = mock_container
            with patch("backend.worker.tasks.external_algorithm._find_newest_ply") as mock_find:
                mock_find.return_value = None
                with patch(
                    "backend.worker.tasks.external_algorithm.TaskRepository.update_progress"
                ):
                    from backend.worker.tasks.external_algorithm import run_external_algorithm

                    result = run_external_algorithm.run("test-id", "/tmp/test.mp4")
                    assert "error" in result
                    mock_container.wait.assert_called_once()
                    mock_container.remove.assert_called_once()
                    mock_container.logs.assert_called_once_with(stream=True, follow=True)
