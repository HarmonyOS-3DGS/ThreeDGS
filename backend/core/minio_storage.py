"""MinIO 对象存储客户端封装。"""

from io import BytesIO

from minio import Minio
from minio.error import S3Error

from backend.core.config import settings


class MinioStorageClient:
    """MinIO 客户端封装，提供对象存储的增删查操作。"""

    def __init__(self):
        self._client = None
        self.bucket = settings.minio_bucket

    @property
    def client(self):
        if self._client is None:
            self._client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )
            self._ensure_bucket()
        return self._client

    def _ensure_bucket(self):
        """确保目标存储桶存在并配置 CORS。"""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        # 每次启动确保 CORS 配置允许浏览器跨域访问
        try:
            self.client.set_bucket_cors(
                self.bucket,
                {
                    "CORSRules": [
                        {
                            "AllowedOrigins": ["*"],
                            "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
                            "AllowedHeaders": ["*"],
                            "ExposeHeaders": ["ETag", "Content-Type"],
                            "MaxAgeSeconds": 3600,
                        }
                    ]
                },
            )
        except Exception:
            pass

    def upload_file(self, object_name: str, file_path: str) -> str:
        """上传本地文件到 MinIO，返回对象路径。"""
        self.client.fput_object(self.bucket, object_name, file_path)
        return f"{self.bucket}/{object_name}"

    def download_file(self, object_name: str, file_path: str) -> str:
        """从 MinIO 下载文件到本地路径。"""
        self.client.fget_object(self.bucket, object_name, file_path)
        return file_path

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """生成对象的预签名 GET URL（下载用）。"""
        url = self.client.presigned_get_object(self.bucket, object_name, expires=expires)
        return self._replace_endpoint(url)

    def get_presigned_put_url(self, object_name: str, expires: int = 3600) -> str:
        """生成对象的预签名 PUT URL（上传用）。"""
        url = self.client.presigned_put_object(self.bucket, object_name, expires=expires)
        return self._replace_endpoint(url)

    def _replace_endpoint(self, url: str) -> str:
        """如果配置了 minio_public_endpoint，替换为外部可访问地址。"""
        public = getattr(settings, "minio_public_endpoint", "")
        if public and settings.minio_endpoint in url:
            return url.replace(settings.minio_endpoint, public)
        return url

    def delete_object(self, object_name: str) -> None:
        """从 MinIO 删除对象。"""
        self.client.remove_object(self.bucket, object_name)

    def put_object(self, object_name: str, data: bytes) -> str:
        """直接上传 bytes 到 MinIO。"""
        self.client.put_object(self.bucket, object_name, BytesIO(data), len(data))
        return f"{self.bucket}/{object_name}"

    def list_objects(self, prefix: str = "") -> list[str]:
        """列出指定前缀下的所有对象。"""
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]

    def object_exists(self, object_name: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False

    def get_object_size(self, object_name: str) -> int:
        try:
            stat = self.client.stat_object(self.bucket, object_name)
            return stat.size
        except S3Error:
            return 0
