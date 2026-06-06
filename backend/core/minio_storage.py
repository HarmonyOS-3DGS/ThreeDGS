"""MinIO storage client wrapper."""
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from backend.core.config import settings


class MinioStorageClient:
    """Wrapper around MinIO client for object storage operations."""

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
        """Ensure the target bucket exists."""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_file(self, object_name: str, file_path: str) -> str:
        """Upload a file to MinIO and return the object path."""
        self.client.fput_object(self.bucket, object_name, file_path)
        return f"{self.bucket}/{object_name}"

    def download_file(self, object_name: str, file_path: str) -> str:
        """Download a file from MinIO to a local path."""
        self.client.fget_object(self.bucket, object_name, file_path)
        return file_path

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """Generate a presigned URL for accessing an object."""
        return self.client.presigned_get_object(self.bucket, object_name, expires=expires)

    def delete_object(self, object_name: str) -> None:
        """Delete an object from MinIO."""
        self.client.remove_object(self.bucket, object_name)

    def put_object(self, object_name: str, data: bytes) -> str:
        """Upload bytes directly to MinIO."""
        self.client.put_object(
            self.bucket, object_name, BytesIO(data), len(data)
        )
        return f"{self.bucket}/{object_name}"

    def list_objects(self, prefix: str = "") -> list[str]:
        """List all objects with the given prefix."""
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
