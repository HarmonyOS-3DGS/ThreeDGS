"""MinIO 对象存储客户端封装。"""

import logging
import time
from datetime import timedelta
from io import BytesIO
from urllib.request import Request, urlopen

from minio import Minio
from minio.error import S3Error

from backend.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_BACKOFF = [1, 2, 4, 8]  # 秒


class MinioStorageClient:
    """MinIO 客户端封装，提供对象存储的增删查操作。"""

    def __init__(self):
        self._client = None
        self._presign_client = None
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

    @property
    def presign_client(self):
        """用于生成预签名 URL 的客户端。若配置了公网端点，使用公网端点签名。

        AWS Signature V4 的签名包含 Host 头，事后替换 hostname 会导致签名不匹配。
        此处直接使用正确的 endpoint 生成签名，确保浏览器可直连 MinIO。
        """
        if self._presign_client is not None:
            return self._presign_client
        public = getattr(settings, "minio_public_endpoint", "")
        endpoint = public or settings.minio_endpoint
        if endpoint == settings.minio_endpoint:
            self._presign_client = self.client
        else:
            self._presign_client = Minio(
                endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )
        return self._presign_client

    def _ensure_bucket(self):
        """确保目标存储桶存在并配置 CORS 跨域访问。首次连接 MinIO 可能未就绪，带退避重试。"""
        last_err = None
        for delay in _RETRY_BACKOFF:
            try:
                if not self.client.bucket_exists(self.bucket):
                    self.client.make_bucket(self.bucket)
                    logger.info("MinIO bucket created: %s", self.bucket)
                self._configure_cors()
                return
            except Exception as e:
                last_err = e
                logger.warning("MinIO not ready, retry in %ds: %s", delay, e)
                time.sleep(delay)
        raise RuntimeError(f"MinIO unavailable after {len(_RETRY_BACKOFF)} retries") from last_err

    def _configure_cors(self):
        """通过 MinIO API 配置 CORS，允许浏览器跨域上传/下载。"""
        cors_xml = (
            '<CORSConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            "<CORSRule>"
            "<AllowedOrigin>*</AllowedOrigin>"
            "<AllowedMethod>GET</AllowedMethod>"
            "<AllowedMethod>PUT</AllowedMethod>"
            "<AllowedMethod>POST</AllowedMethod>"
            "<AllowedMethod>DELETE</AllowedMethod>"
            "<AllowedMethod>HEAD</AllowedMethod>"
            "<AllowedHeader>*</AllowedHeader>"
            "<ExposeHeader>ETag</ExposeHeader>"
            "<ExposeHeader>Content-Type</ExposeHeader>"
            "<MaxAgeSeconds>3600</MaxAgeSeconds>"
            "</CORSRule>"
            "</CORSConfiguration>"
        )
        try:
            # 通过 MinIO 内部 HTTP 客户端发送 PUT 请求配置 CORS
            url = f"{self.client._base_url}/{self.bucket}?cors"
            headers = {"Content-Type": "application/xml"}
            region = self.client._region_map.get("")
            signed_headers = self.client._build_headers(
                "PUT", region, url, headers, cors_xml.encode(), None, None
            )
            req = Request(url, data=cors_xml.encode(), headers=signed_headers, method="PUT")
            urlopen(req)
            logger.info("MinIO CORS configured: ALLOW * GET/PUT/POST/DELETE/HEAD")
        except Exception as e:
            logger.warning("Failed to configure MinIO CORS: %s", e)
            logger.warning(
                "Please configure manually: mc admin config set local api cors_allow_origin='*'"
            )

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
        return self.presign_client.presigned_get_object(
            self.bucket, object_name, expires=timedelta(seconds=expires)
        )

    def get_presigned_put_url(self, object_name: str, expires: int = 3600) -> str:
        """生成对象的预签名 PUT URL（上传用）。"""
        return self.presign_client.presigned_put_object(
            self.bucket, object_name, expires=timedelta(seconds=expires)
        )

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
