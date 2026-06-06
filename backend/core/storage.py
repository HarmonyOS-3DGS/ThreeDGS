"""Storage client - uses MinIO if available, falls back to local filesystem."""
import os

from backend.core.config import settings
from backend.core.interfaces import StorageClient


class _LazyStorage:
    """Lazy proxy that defers storage client creation until first use."""

    def __getattr__(self, name):
        return getattr(get_storage(), name)


def get_storage():
    """Factory - returns MinIO or local storage client."""
    use_local = getattr(settings, "use_local_storage", False) or os.getenv("USE_LOCAL_STORAGE", "").lower() in ("true", "1", "yes")
    if use_local:
        from backend.core.local_storage import LocalStorageClient
        return LocalStorageClient()
    else:
        from backend.core.minio_storage import MinioStorageClient
        return MinioStorageClient()


# Keep backward compatibility - lazy proxy
storage = _LazyStorage()
