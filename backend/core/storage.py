"""存储客户端 — MinIO / 本地文件系统双模切换。

设计要点：
  - _LazyStorage 代理：延迟到首次调用时才创建客户端，避免 import 阶段就实例化 MinIO 连接
  - get_storage(): 工厂函数，每次调用返回新实例（后续可改为单例）
  - 切换方式：USE_LOCAL_STORAGE=true 或环境变量控制
"""

import os

from backend.core.config import settings


class _LazyStorage:
    """延迟代理 — 首次属性访问时才调用 get_storage() 创建实际客户端。

    好处：不放 import 阶段导入 MinIO 模块，API 启动不需要 MinIO 可达。
    """

    def __getattr__(self, name):
        return getattr(get_storage(), name)


def get_storage():
    """工厂函数 — 根据配置返回 LocalStorageClient 或 MinioStorageClient。"""
    use_local = getattr(settings, "use_local_storage", False) or os.getenv(
        "USE_LOCAL_STORAGE", ""
    ).lower() in ("true", "1", "yes")
    if use_local:
        from backend.core.local_storage import LocalStorageClient

        return LocalStorageClient()
    else:
        from backend.core.minio_storage import MinioStorageClient

        return MinioStorageClient()


# 模块级单例代理 — 所有调用方通过 storage.xxx() 使用
storage = _LazyStorage()
