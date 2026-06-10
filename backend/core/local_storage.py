"""本地文件系统存储实现（MinIO 不可用时的回退方案）。"""

import shutil
from pathlib import Path

from backend.core.config import settings


class LocalStorageClient:
    """MinIO StorageClient 的本地文件系统替代实现。"""

    def __init__(self):
        self.base_dir = Path(getattr(settings, "local_storage_dir", "./local_storage"))
        self.bucket = getattr(settings, "minio_bucket", "gaussian")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, object_name: str) -> Path:
        """解析对象名到本地路径。"""
        return self.base_dir / self.bucket / object_name

    def upload_file(self, object_name: str, file_path: str) -> str:
        dest = self._resolve(object_name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest)
        return str(dest)

    def download_file(self, object_name: str, file_path: str) -> str:
        src = self._resolve(object_name)
        shutil.copy2(src, file_path)
        return file_path

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        raise NotImplementedError("本地存储不支持预签名 URL，请使用 FileResponse 直接读取文件")

    def get_presigned_put_url(self, object_name: str, expires: int = 3600) -> str:
        raise NotImplementedError("本地存储不支持预签名 URL，请使用本地上传端点")

    def delete_object(self, object_name: str) -> None:
        path = self._resolve(object_name)
        if path.exists():
            path.unlink()

    def put_object(self, object_name: str, data: bytes) -> str:
        """直接写入 bytes 到本地文件。"""
        dest = self._resolve(object_name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return str(dest)

    def list_objects(self, prefix: str = "") -> list[str]:
        """列出指定前缀目录下的所有文件（返回相对对象名）。"""
        prefix_path = self._resolve(prefix)
        if not prefix_path.exists():
            return []
        results = []
        if prefix_path.is_file():
            return [prefix]
        for p in prefix_path.rglob("*"):
            if p.is_file():
                # 计算相对于 bucket 根目录的对象名
                rel = p.relative_to(self.base_dir / self.bucket)
                results.append(str(rel).replace("\\", "/"))
        return results

    def object_exists(self, object_name: str) -> bool:
        return self._resolve(object_name).exists()

    def get_object_size(self, object_name: str) -> int:
        path = self._resolve(object_name)
        return path.stat().st_size if path.exists() else 0
