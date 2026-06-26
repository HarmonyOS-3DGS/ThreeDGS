"""Tests for external_algorithm task."""

from unittest.mock import MagicMock, patch


class TestExternalAlgorithmTask:
    def test_docker_success(self):
        with patch("backend.worker.tasks.external_algorithm.docker.from_env") as mock_docker:
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = []
            mock_docker.return_value.containers.run.return_value = mock_container
            with patch("backend.worker.tasks.external_algorithm.find_newest_ply") as mock_find:
                mock_find.return_value = "/tmp/test.ply"
                with (
                    patch("backend.worker.tasks.external_algorithm.TaskRepository.update_progress"),
                    patch("backend.worker.tasks.external_algorithm.ensure_input_video"),
                    patch(
                        "backend.worker.tasks.external_algorithm.run_finalize",
                        return_value={"raw_model": "/tmp/model.ply"},
                    ),
                ):
                    from backend.worker.tasks.external_algorithm import run_external_algorithm

                    result = run_external_algorithm.run("test-id", "/tmp/test.mp4")
                    assert result["task_id"] == "test-id"
                    assert "outputs" in result
                    assert result["outputs"]["raw_model"] == "/tmp/model.ply"
                    mock_container.wait.assert_called_once()
                    mock_container.remove.assert_called_once()
                    mock_container.logs.assert_called_once_with(stream=True, follow=True)

    def test_docker_failure(self):
        with patch("backend.worker.tasks.external_algorithm.docker.from_env") as mock_docker:
            mock_docker.return_value.containers.run.side_effect = Exception("crash")
            with (
                patch(
                    "backend.worker.tasks.external_algorithm.TaskRepository.update_progress"
                ) as mock_up,
                patch("backend.worker.tasks.external_algorithm.ensure_input_video"),
            ):
                from backend.worker.tasks.external_algorithm import run_external_algorithm

                result = run_external_algorithm.run("test-id", "/tmp/test.mp4")
                assert "error" in result
                calls = mock_up.call_args_list
                failed_call = [c for c in calls if c[1].get("status") == "failed"]
                assert len(failed_call) == 1

    def test_ensure_input_video_failure(self):
        with patch("backend.worker.tasks.external_algorithm.docker.from_env"):
            with patch(
                "backend.worker.tasks.external_algorithm.TaskRepository.update_progress"
            ) as mock_up:
                with patch(
                    "backend.worker.tasks.external_algorithm.ensure_input_video",
                    side_effect=FileNotFoundError("file not found"),
                ):
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
            with patch("backend.worker.tasks.external_algorithm.find_newest_ply") as mock_find:
                mock_find.return_value = None
                with (
                    patch("backend.worker.tasks.external_algorithm.TaskRepository.update_progress"),
                    patch("backend.worker.tasks.external_algorithm.ensure_input_video"),
                ):
                    from backend.worker.tasks.external_algorithm import run_external_algorithm

                    result = run_external_algorithm.run("test-id", "/tmp/test.mp4")
                    assert "error" in result
                    mock_container.wait.assert_called_once()
                    mock_container.remove.assert_called_once()
                    mock_container.logs.assert_called_once_with(stream=True, follow=True)

    def test_docker_cmd_always_has_with_mask(self):
        with patch("backend.worker.tasks.external_algorithm.docker.from_env") as mock_docker:
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = []
            mock_docker.return_value.containers.run.return_value = mock_container
            with patch("backend.worker.tasks.external_algorithm.find_newest_ply") as mock_find:
                mock_find.return_value = "/tmp/test.ply"
                with (
                    patch("backend.worker.tasks.external_algorithm.TaskRepository.update_progress"),
                    patch("backend.worker.tasks.external_algorithm.ensure_input_video"),
                    patch(
                        "backend.worker.tasks.external_algorithm.run_finalize",
                        return_value={"raw_model": "/tmp/model.ply"},
                    ),
                ):
                    from backend.worker.tasks.external_algorithm import run_external_algorithm

                    run_external_algorithm.run("test-id", "/tmp/test.mp4")
                    call_args = mock_docker.return_value.containers.run.call_args
                    cmd = call_args[1]["command"]
                    assert "--with_mask" in cmd
                    mask_idx = cmd.index("--with_mask")
                    assert cmd[mask_idx + 1] == "true"

    def test_docker_cmd_outdoor_has_is_outdoor(self):
        with patch("backend.worker.tasks.external_algorithm.docker.from_env") as mock_docker:
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = []
            mock_docker.return_value.containers.run.return_value = mock_container
            with patch("backend.worker.tasks.external_algorithm.find_newest_ply") as mock_find:
                mock_find.return_value = "/tmp/test.ply"
                with (
                    patch("backend.worker.tasks.external_algorithm.TaskRepository.update_progress"),
                    patch("backend.worker.tasks.external_algorithm.ensure_input_video"),
                    patch(
                        "backend.worker.tasks.external_algorithm.run_finalize",
                        return_value={"raw_model": "/tmp/model.ply"},
                    ),
                ):
                    from backend.worker.tasks.external_algorithm import run_external_algorithm

                    # Default scene (empty) → no --is_outdoor
                    run_external_algorithm.run("test-id", "/tmp/test.mp4")
                    cmd_default = mock_docker.return_value.containers.run.call_args[1]["command"]
                    assert "--is_outdoor" not in cmd_default

                    # Outdoor scene → has --is_outdoor true
                    run_external_algorithm.run("test-id", "/tmp/test.mp4", scene="outdoor")
                    cmd_outdoor = mock_docker.return_value.containers.run.call_args[1]["command"]
                    assert "--is_outdoor" in cmd_outdoor
                    outdoor_idx = cmd_outdoor.index("--is_outdoor")
                    assert cmd_outdoor[outdoor_idx + 1] == "true"

                    # Indoor scene → no --is_outdoor (same behavior as default)
                    run_external_algorithm.run("test-id", "/tmp/test.mp4", scene="indoor")
                    cmd_indoor = mock_docker.return_value.containers.run.call_args[1]["command"]
                    assert "--is_outdoor" not in cmd_indoor
