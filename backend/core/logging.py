"""统一日志配置 — 单个 dictConfig，通过框架原生 log_config 机制注入。"""

import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

_LOG_FILE = os.getenv("LOG_FILE", "logs/3dgs.log")
_LOG_DIR = os.path.dirname(_LOG_FILE)

if _LOG_DIR:
    os.makedirs(_LOG_DIR, exist_ok=True)


class _TimestampedFileHandler(RotatingFileHandler):
    """滚动日志，备份文件格式: 3dgs-2026-06-15-1.log"""

    def rotation_filename(self, default_name: str) -> str:
        base, ext = os.path.splitext(self.baseFilename)
        now = datetime.now().strftime("%Y-%m-%d")
        idx = 1
        while os.path.exists(f"{base}-{now}-{idx}{ext}"):
            idx += 1
        return f"{base}-{now}-{idx}{ext}"


LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "backend.core.logging._TimestampedFileHandler",
            "formatter": "default",
            "filename": _LOG_FILE,
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 100,
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}
