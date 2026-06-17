#!/usr/bin/env python3
"""一键本地启动脚本（API + Worker 同进程线程模式，memory broker 共享）。"""

import logging
import os
import sys
import threading
import time

logger = logging.getLogger(__name__)

# 强制使用本地配置
os.environ.setdefault("DATABASE_URL", "sqlite:///./3dgs.db")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("USE_LOCAL_STORAGE", "true")
os.environ.setdefault("LOCAL_STORAGE_DIR", "./local_storage")
os.environ.setdefault("SERVICE_ACCOUNTS", "dev-admin:sk-debug")
os.environ.setdefault("JWT_SECRET_KEY", "dev-jwt-secret-not-for-production")

# 创建本地存储目录
os.makedirs("local_storage", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

# 初始化数据库
logger.info("[1/3] Initializing database...")
from backend.core.database import init_db  # noqa: E402

init_db()
logger.info("  Database initialized")

# 启动 Celery Worker 线程
logger.info("[2/3] Starting Celery Worker...")
from backend.worker.celery_app import app as celery_app  # noqa: E402


def run_worker():
    # 避免 Celery 重定向 stdout，导致 print 被日志系统劫持
    celery_app.conf.worker_redirect_stdouts = False
    worker = celery_app.Worker(
        hostname="local_worker@localhost",
        pool="solo",
        concurrency=1,
        loglevel="info",
        broker_connection_retry_on_startup=True,
        worker_hijack_root_logger=False,
    )
    worker.start()


def run_cleanup_scheduler():
    """本地模式下用简单线程替代 Celery Beat，定期清理过期任务。"""
    from backend.worker.tasks.cleanup import cleanup_completed_tasks, cleanup_pending_tasks

    while True:
        time.sleep(1800)  # 30 分钟
        try:
            cleanup_pending_tasks.run()
            cleanup_completed_tasks.run()
        except Exception as e:
            logger.warning("[cleanup] cleanup failed: %s", e)


worker_thread = threading.Thread(target=run_worker, daemon=True)
worker_thread.start()

# 启动本地定时清理线程（替代 Celery Beat）
cleanup_thread = threading.Thread(target=run_cleanup_scheduler, daemon=True)
cleanup_thread.start()

time.sleep(2)
logger.info("  Worker started")

# 启动 FastAPI 服务
logger.info("[3/3] Starting FastAPI...")
import uvicorn  # noqa: E402

from backend.api.main import app as fastapi_app  # noqa: E402
from backend.core.logging import LOG_CONFIG  # noqa: E402

api_server = None


def run_api():
    global api_server
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
        log_config=LOG_CONFIG,
    )
    api_server = uvicorn.Server(config)
    api_server.run()


api_thread = threading.Thread(target=run_api, daemon=True)
api_thread.start()

# 等待 API 启动
ready = False
for _ in range(30):
    try:
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:8000/docs", timeout=1) as r:
            if r.status == 200:
                ready = True
                break
    except Exception:
        pass
    time.sleep(0.5)

if not ready:
    logger.error("  API startup failed")
    sys.exit(1)

logger.info("========================================")
logger.info(" Service started! Addresses:")
logger.info("  - Frontend:  http://localhost:8000/index.html")
logger.info("  - API docs:  http://localhost:8000/docs")
logger.info("  - Task list: http://localhost:8000/status.html")
logger.info("========================================")
logger.info("Press Ctrl+C or Enter to stop")

# 主线程保持运行，等待退出信号
stop_event = threading.Event()


def wait_for_exit():
    """跨平台等待退出信号（Ctrl+C 或 Enter）。"""
    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop_event.set()


# 启动一个监听 Enter 键的线程（Windows 兼容，无 stdin 时静默忽略）
def wait_enter():
    try:
        input()
        stop_event.set()
    except (EOFError, KeyboardInterrupt):
        pass


enter_thread = threading.Thread(target=wait_enter, daemon=True)
enter_thread.start()

wait_for_exit()

logger.info("Stopping service...")
if api_server:
    api_server.should_exit = True
api_thread.join(timeout=5)
logger.info("Service stopped")
sys.exit(0)
