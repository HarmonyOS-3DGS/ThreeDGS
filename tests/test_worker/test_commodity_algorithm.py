"""Tests for commodity_algorithm task."""

from unittest.mock import MagicMock, patch


class TestCommodityAlgorithmTask:
    def test_docker_success(self):
        with (
            patch("backend.worker.tasks.commodity_algorithm.docker.from_env") as mock_docker,
            patch("backend.worker.tasks.commodity_algorithm.find_newest_ply") as mock_find,
            patch("backend.worker.tasks.commodity_algorithm.TaskRepository.update_progress"),
            patch("backend.worker.tasks.commodity_algorithm.ensure_input_video"),
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
            patch("backend.worker.tasks.commodity_algorithm.ensure_input_video"),
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
            patch("backend.worker.tasks.commodity_algorithm.ensure_input_video"),
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
