"""API 入口 — 注入统一日志配置到 uvicorn，替代原生 uvicorn CLI。"""

import uvicorn

from backend.core.logging import LOG_CONFIG

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        log_config=LOG_CONFIG,
    )
