"""Tests for LocalStorageClient."""

import os
import tempfile
from pathlib import Path

from backend.core.local_storage import LocalStorageClient


class TestLocalStorage:
    def test_upload_file(self):
        with tempfile.TemporaryDirectory() as td:
            client = LocalStorageClient()
            client.base_dir = Path(td)

            src = os.path.join(td, "src.txt")
            with open(src, "w") as f:
                f.write("hello")

            dest = client.upload_file("tasks/abc/src.txt", src)
            assert os.path.isfile(dest)

    def test_put_object(self):
        with tempfile.TemporaryDirectory() as td:
            client = LocalStorageClient()
            client.base_dir = Path(td)

            dest = client.put_object("tasks/abc/data.txt", b"hello")
            assert os.path.isfile(dest)
            with open(dest) as f:
                assert f.read() == "hello"

    def test_get_presigned_url_raises(self):
        client = LocalStorageClient()
        try:
            client.get_presigned_url("x")
            assert False, "should raise"
        except NotImplementedError:
            pass

    def test_get_presigned_put_url_raises(self):
        client = LocalStorageClient()
        try:
            client.get_presigned_put_url("x")
            assert False, "should raise"
        except NotImplementedError:
            pass

    def test_object_exists(self):
        with tempfile.TemporaryDirectory() as td:
            client = LocalStorageClient()
            client.base_dir = Path(td)
            client.put_object("test.txt", b"data")
            assert client.object_exists("test.txt")
            assert not client.object_exists("missing.txt")
