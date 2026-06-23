"""commodity 场景专用外部算法 — 通过 Docker SDK 执行并收集 PLY 结果。

与算法 1 共用宿主根目录 /data/3dgs 和 volume 映射 -v /data/3dgs:/data。
视频文件由 ensure_input_video 下载到 /data/3dgs/tasks/{task_id}/，容器内可见。
"""

import logging
import os
import threading
import time

import docker

from backend.core.config import settings
from backend.core.repository import TaskRepository
from backend.worker.celery_app import app
from backend.worker.tasks.file_utils import ensure_input_video, find_newest_ply

logger = logging.getLogger(__name__)


@app.task(bind=True, time_limit=settings.alg2_max_seconds)
def run_commodity_algorithm(self, task_id: str, video_path: str):
    """通过 Docker SDK 执行 commodity 算法镜像，等待退出，收集 PLY 结果。"""
    ensure_input_video(task_id)
    host_data = settings.alg_host_data_dir
    container_data = "/data"
    container_input = f"{container_data}/tasks/{task_id}"

    docker_cmd = [
        "bash",
        "-c",
        f"python -m pip uninstall xformers -y && "
        f"cd {settings.alg2_work_dir} && "
        f"python {settings.alg2_script} "
        f"-d {container_input} "
        f"{settings.alg2_extra_args}",
    ]

    volumes = {host_data: {"bind": container_data, "mode": "rw"}}
    logger.info("alg2 start task=%s image=%s cmd=%s", task_id, settings.alg2_image, docker_cmd)

    TaskRepository.update_progress(
        task_id,
        "training",
        5,
        expected_seconds=settings.alg2_expected_seconds,
    )

    stop_timer = threading.Event()
    start_time = time.time()

    def poll_progress():
        while not stop_timer.is_set():
            elapsed = time.time() - start_time
            pct = min(90, int(5 + elapsed * 85 / max(1, settings.alg2_expected_seconds)))
            TaskRepository.update_progress(
                task_id,
                "training",
                pct,
                expected_seconds=settings.alg2_expected_seconds,
            )
            stop_timer.wait(10)

    timer = threading.Thread(target=poll_progress, daemon=True)
    timer.start()

    try:
        client = docker.from_env()
        container = client.containers.run(
            image=settings.alg2_image,
            command=docker_cmd,
            volumes=volumes,
            detach=True,
            stdin_open=True,
            tty=True,
            privileged=True,
            shm_size=settings.alg2_shm_size,
            network_mode="host",
            user="root",
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
            buf = b""
            for chunk in container.logs(stream=True, follow=True):
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").rstrip()
                    if text:
                        logger.info("alg2: %s", text)
                        logs_lines.append(text)
            if buf:
                text = buf.decode("utf-8", errors="replace").rstrip()
                if text:
                    logger.info("alg2: %s", text)
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
        logger.error("alg2 failed task=%s rc=%d: %s", task_id, exit_code, error_msg)
        TaskRepository.update_progress(
            task_id,
            "training",
            50,
            status="failed",
            error=error_msg,
            expected_seconds=settings.alg2_expected_seconds,
        )
        return {"task_id": task_id, "error": error_msg[:200]}

    TaskRepository.update_progress(
        task_id,
        "training",
        95,
        expected_seconds=settings.alg2_expected_seconds,
    )

    # 宿主机输出路径: /data/3dgs/dist_so/UserData/test_task_id_tasks_{id}/recon_result.ply
    host_userdata = os.path.join(host_data, settings.alg2_ply_userdata_rel)
    exact_subdir = f"{settings.alg2_ply_subdir_prefix}{task_id}"
    exact_ply = os.path.join(host_userdata, exact_subdir, settings.alg2_ply_name)
    ply_path = exact_ply if os.path.isfile(exact_ply) else None
    if not ply_path:
        ply_path = find_newest_ply(host_userdata, settings.alg2_ply_name)
    if not ply_path:
        logger.error("alg2 PLY not found task=%s dir=%s", task_id, host_userdata)
        TaskRepository.update_progress(
            task_id,
            "training",
            95,
            status="failed",
            error="PLY file not found",
            expected_seconds=settings.alg2_expected_seconds,
        )
        return {"task_id": task_id, "error": "PLY not found"}

    logger.info("alg2 found PLY: %s", ply_path)
    return {"task_id": task_id, "model_path": ply_path}
