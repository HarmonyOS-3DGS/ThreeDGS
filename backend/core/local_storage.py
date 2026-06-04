"""Local filesystem storage fallback (when MinIO is unavailable)."""
import os
import shutil
from pathlib import Path

from backend.core.config import settings


class LocalStorageClient:
    """Drop-in replacement for MinIO StorageClient using local filesystem."""

    def __init__(self):
        self.base_dir = Path(getattr(settings, "local_storage_dir", "./local_storage"))
        self.bucket = getattr(settings, "minio_bucket", "gaussian")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload_file(self, object_name: str, file_path: str) -> str:
        dest = self.base_dir / self.bucket / object_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest)
        return str(dest)

    def download_file(self, object_name: str, file_path: str) -> str:
        src = self.base_dir / self.bucket / object_name
        shutil.copy2(src, file_path)
        return file_path

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        # Local files return file:// URL
        path = self.base_dir / self.bucket / object_name
        return path.as_uri()

    def delete_object(self, object_name: str) -> None:
        path = self.base_dir / self.bucket / object_name
        if path.exists():
            path.unlink()
