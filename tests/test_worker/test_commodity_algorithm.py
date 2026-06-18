"""Tests for commodity_algorithm task."""

import os
import tempfile
import time
from unittest.mock import MagicMock, patch

from backend.worker.tasks.shared import find_newest_ply


class TestFindNewestPly:
    def test_finds_ply_in_subdir(self):
        with tempfile.TemporaryDirectory() as td:
            subdir = os.path.join(td, "UserData", "test_task_id_tasks_001")
            os.makedirs(subdir, exist_ok=True)
            ply1 = os.path.join(subdir, "recon_result.ply")
            with open(ply1, "w") as f:
                f.write("old")
            time.sleep(0.01)
            ply2 = os.path.join(td, "nested", "recon_result.ply")
            os.makedirs(os.path.dirname(ply2), exist_ok=True)
            with open(ply2, "w") as f:
                f.write("new")
            result = find_newest_ply(td, "recon_result.ply")
            assert result == ply2

    def test_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            result = find_newest_ply(td, "recon_result.ply")
            assert result is None

    def test_returns_none_when_dir_missing(self):
        result = find_newest_ply("/nonexistent/path", "recon_result.ply")
        assert result is None


class TestCommodityAlgorithmTask:
    def test_docker_success(self):
        with (
            patch("backend.worker.tasks.commodity_algorithm.docker.from_env") as mock_docker,
            patch("backend.worker.tasks.commodity_algorithm.find_newest_ply") as mock_find,
            patch("backend.worker.tasks.commodity_algorithm.TaskRepository.update_progress"),
        ):
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = []
            mock_docker.return_value.containers.run.return_value = mock_container
            mock_find.return_value = "/tmp/test.ply"

            from backend.worker.tasks.commodity_algorithm import run_commodity_algorithm

            result = run_commodity_algorithm.run("test-id", "/tmp/test.mp4")
            assert result["task_id"] == "test-id"
            assert result["model_path"] == "/tmp/test.ply"
            mock_container.wait.assert_called_once()
            mock_container.remove.assert_called_once()
            mock_container.logs.assert_called_once_with(stream=True, follow=True)

    def test_docker_failure(self):
        with (
            patch("backend.worker.tasks.commodity_algorithm.docker.from_env") as mock_docker,
            patch(
                "backend.worker.tasks.commodity_algorithm.TaskRepository.update_progress"
            ) as mock_up,
        ):
            mock_docker.return_value.containers.run.side_effect = Exception("crash")

            from backend.worker.tasks.commodity_algorithm import run_commodity_algorithm

            result = run_commodity_algorithm.run("test-id", "/tmp/test.mp4")
            assert "error" in result
            calls = mock_up.call_args_list
            failed_call = [c for c in calls if c[1].get("status") == "failed"]
            assert len(failed_call) == 1

    def test_ply_not_found_after_success(self):
        with (
            patch("backend.worker.tasks.commodity_algorithm.docker.from_env") as mock_docker,
            patch("backend.worker.tasks.commodity_algorithm.find_newest_ply") as mock_find,
            patch("backend.worker.tasks.commodity_algorithm.TaskRepository.update_progress"),
        ):
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = []
            mock_docker.return_value.containers.run.return_value = mock_container
            mock_find.return_value = None

            from backend.worker.tasks.commodity_algorithm import run_commodity_algorithm

            result = run_commodity_algorithm.run("test-id", "/tmp/test.mp4")
            assert "error" in result
            mock_container.wait.assert_called_once()
            mock_container.remove.assert_called_once()
            mock_container.logs.assert_called_once_with(stream=True, follow=True)

    def test_exact_ply_path_priority(self):
        """验证精确路径优先于递归搜索。"""
        with tempfile.TemporaryDirectory() as td:
            exact_dir = os.path.join(td, "UserData", "test_task_id_tasks_exact-test")

            os.makedirs(exact_dir, exist_ok=True)
            exact_ply = os.path.join(exact_dir, "recon_result.ply")
            with open(exact_ply, "w") as f:
                f.write("exact")

            # find_newest_ply 应该返回 exact_ply
            result = find_newest_ply(os.path.join(td, "UserData"), "recon_result.ply")
            assert result == exact_ply
