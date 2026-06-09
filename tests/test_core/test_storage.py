"""Tests for MinIO storage client (mocked)."""

from unittest.mock import MagicMock, patch

from backend.core.minio_storage import MinioStorageClient


class TestStorageClient:
    def test_upload_file(self):
        with patch("backend.core.minio_storage.Minio") as MockMinio:
            mock_client = MagicMock()
            MockMinio.return_value = mock_client
            mock_client.bucket_exists.return_value = True

            storage = MinioStorageClient()
            result = storage.upload_file("test/object.txt", "/tmp/test.txt")
            assert result == "gaussian/test/object.txt"
            mock_client.fput_object.assert_called_once_with(
                "gaussian", "test/object.txt", "/tmp/test.txt"
            )

    def test_download_file(self):
        with patch("backend.core.minio_storage.Minio") as MockMinio:
            mock_client = MagicMock()
            MockMinio.return_value = mock_client
            mock_client.bucket_exists.return_value = True

            storage = MinioStorageClient()
            result = storage.download_file("test/object.txt", "/tmp/out.txt")
            assert result == "/tmp/out.txt"
            mock_client.fget_object.assert_called_once_with(
                "gaussian", "test/object.txt", "/tmp/out.txt"
            )

    def test_get_presigned_url(self):
        with patch("backend.core.minio_storage.Minio") as MockMinio:
            mock_client = MagicMock()
            MockMinio.return_value = mock_client
            mock_client.bucket_exists.return_value = True
            mock_client.presigned_get_object.return_value = "http://minio/presigned"

            storage = MinioStorageClient()
            result = storage.get_presigned_url("test/object.txt")
            assert result == "http://minio/presigned"

    def test_delete_object(self):
        with patch("backend.core.minio_storage.Minio") as MockMinio:
            mock_client = MagicMock()
            MockMinio.return_value = mock_client
            mock_client.bucket_exists.return_value = True

            storage = MinioStorageClient()
            storage.delete_object("test/object.txt")
            mock_client.remove_object.assert_called_once_with("gaussian", "test/object.txt")
