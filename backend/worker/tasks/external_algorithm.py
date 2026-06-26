"""外部算法一体化任务 — 通过 Docker SDK 执行并收集 PLY 结果。"""

import logging
import os
import threading

import docker

from backend.core.config import settings
from backend.core.path_utils import task_output_path
from backend.core.repository import TaskRepository
from backend.worker.celery_app import app
from backend.worker.tasks.file_utils import ensure_input_video, find_newest_ply
from backend.worker.tasks.finalize import run_finalize

logger = logging.getLogger(__name__)


@app.task(bind=True, time_limit=settings.alg_max_seconds)
def run_external_algorithm(self, task_id: str, video_path: str, scene: str = ""):
    """通过 Docker SDK 执行外部算法镜像，等待退出，收集 PLY 结果。"""
    host_data = settings.alg_host_data_dir
    container_data = "/data"
    container_input = f"{container_data}/tasks/{task_id}"
    container_output = f"{container_data}/tasks/{task_id}/{settings.alg_output_dir}"

    local_output = task_output_path(task_id, settings.alg_output_dir)
    os.makedirs(local_output, exist_ok=True)

    docker_cmd = [
        "python",
        settings.alg_script,
        "--input_dir",
        container_input,
        "--output_dir",
        container_output,
        "--with_mask",
        "true",
    ]
    if scene == "outdoor":
        docker_cmd += ["--is_outdoor", "true"]

    volumes = {host_data: {"bind": container_data, "mode": "rw"}}
    logger.info("alg start task=%s image=%s cmd=%s", task_id, settings.alg_image, docker_cmd)

    TaskRepository.update_progress(task_id, "training", 5)

    stop_timer = threading.Event()

    def poll_progress():
        while not stop_timer.is_set():
            TaskRepository.update_progress(
                task_id, "training", 0, expected_seconds=settings.alg_expected_seconds
            )
            stop_timer.wait(10)

    timer = threading.Thread(target=poll_progress, daemon=True)
    timer.start()

    try:
        ensure_input_video(task_id)
        client = docker.from_env()
        container = client.containers.run(
            image=settings.alg_image,
            command=docker_cmd,
            volumes=volumes,
            detach=True,
            stdin_open=False,
            tty=False,
            privileged=True,
            shm_size="8g",
            network_mode="host",
            device_requests=[
                docker.types.DeviceRequest(
                    count=-1, capabilities=[["compute", "utility", "graphics"]]
                )
            ],
            environment={
                "NVIDIA_DRIVER_CAPABILITIES": "compute,utility,graphics",
                "NVIDIA_VISIBLE_DEVICES": "all",
            },
        )

        logs_lines: list[str] = []

        def stream_logs():
            for line in container.logs(stream=True, follow=True):
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    logger.info("alg: %s", text)
                    logs_lines.append(text)

        log_thread = threading.Thread(target=stream_logs, daemon=True)
        log_thread.start()

        result = container.wait()
        exit_code = result.get("StatusCode", 0)
        log_thread.join(timeout=5)
        logs = "\n".join(logs_lines)

        try:
            container.remove()
        except Exception:
            pass

    except docker.errors.ContainerError as e:
        exit_code = e.exit_status
        logs = str(e)
    except Exception as e:
        exit_code = -1
        logs = str(e)
    finally:
        stop_timer.set()
        timer.join(timeout=2)

    if exit_code != 0:
        error_msg = logs[-500:] if logs else f"exit_code={exit_code}"
        logger.error("alg failed task=%s rc=%d: %s", task_id, exit_code, error_msg)
        TaskRepository.update_progress(task_id, "training", 50, status="failed", error=error_msg)
        return {"task_id": task_id, "error": error_msg[:200]}

    TaskRepository.update_progress(task_id, "training", 95)

    search_dir = os.path.join(local_output, settings.alg_ply_subdir.strip("/"))
    ply_path = (
        find_newest_ply(search_dir, settings.alg_ply_name)
        if os.path.isdir(search_dir)
        else find_newest_ply(local_output, settings.alg_ply_name)
    )
    if not ply_path:
        logger.error("alg PLY not found task=%s dir=%s", task_id, local_output)
        TaskRepository.update_progress(
            task_id, "training", 95, status="failed", error="PLY file not found"
        )
        return {"task_id": task_id, "error": "PLY not found"}

    logger.info("alg found PLY: %s", ply_path)
    try:
        outputs = run_finalize(task_id, ply_path)
        TaskRepository.update_progress(task_id, "completed", 100, status="completed")
        logger.info("alg done task=%s outputs=%s", task_id, outputs)
        return {"task_id": task_id, "outputs": outputs}
    except Exception as e:
        error_msg = f"finalize failed: {e}"
        logger.error("alg finalize failed task=%s: %s", task_id, error_msg)
        TaskRepository.update_progress(task_id, "training", 95, status="failed", error=error_msg)
        return {"task_id": task_id, "error": error_msg[:200]}
