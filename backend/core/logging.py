"""统一日志配置 — 控制台 + 滚动文件输出，确保 API 和 Worker 日志格式一致。"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

_LOG_FILE = os.getenv("LOG_FILE", "logs/3dgs.log")
_LOG_DIR = os.path.dirname(_LOG_FILE)

_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


class _TimestampedFileHandler(RotatingFileHandler):
    """滚动日志，备份文件格式: 3dgs-2026-06-15-1.log"""

    def rotation_filename(self, default_name: str) -> str:
        base, ext = os.path.splitext(self.baseFilename)
        now = datetime.now().strftime("%Y-%m-%d")
        idx = 1
        while os.path.exists(f"{base}-{now}-{idx}{ext}"):
            idx += 1
        return f"{base}-{now}-{idx}{ext}"


def setup_logging():
    """配置根日志器：控制台输出 + 滚动文件输出。

    幂等设计：根日志器已有 handler 时跳过，防止重复配置。
    """
    if logging.getLogger().hasHandlers():
        return

    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
    ]

    if _LOG_DIR:
        os.makedirs(_LOG_DIR, exist_ok=True)
        handlers.append(
            _TimestampedFileHandler(
                _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=100, encoding="utf-8"
            )
        )

    logging.basicConfig(
        level=logging.INFO,
        format=_FORMAT,
        datefmt=_DATE_FMT,
        handlers=handlers,
    )
