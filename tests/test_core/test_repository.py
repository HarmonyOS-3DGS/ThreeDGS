"""Tests for TaskRepository."""

import os
import tempfile

from backend.core.database import SessionLocal, TaskFile
from backend.core.repository import TaskRepository


class TestAddOutputFile:
    def test_default_role_is_raw_model(self):
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test.ply")
            with open(fpath, "w") as f:
                f.write("test")
            tf = TaskRepository.add_output_file("test-id", fpath, "application/octet-stream")
            assert tf is not None
            assert tf.fileRole == "raw_model"
            _cleanup(tf)

    def test_custom_role(self):
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test.spz")
            with open(fpath, "w") as f:
                f.write("test")
            tf = TaskRepository.add_output_file(
                "test-id", fpath, "application/octet-stream", file_role="compressed_model"
            )
            assert tf is not None
            assert tf.fileRole == "compressed_model"
            _cleanup(tf)

    def test_storage_url_stored(self):
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test.ply")
            with open(fpath, "w") as f:
                f.write("test")
            tf = TaskRepository.add_output_file(
                "test-id", fpath, "application/octet-stream", storage_url="s3://bucket/key.ply"
            )
            assert tf is not None
            assert tf.fileUrl == "s3://bucket/key.ply"
            _cleanup(tf)


class TestFindFileByName:
    def test_default_role_is_raw_model(self):
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test.ply")
            with open(fpath, "w") as f:
                f.write("test")
            tf = TaskRepository.add_output_file("test-id-2", fpath, "application/octet-stream")
            assert tf is not None
            db = SessionLocal()
            try:
                result = TaskRepository(db).find_file_by_name("test-id-2", "test.ply")
                assert result is not None
                assert result.fileRole == "raw_model"
            finally:
                db.close()
            _cleanup(tf)


def _cleanup(tf: TaskFile):
    db = SessionLocal()
    try:
        db.delete(tf)
        db.commit()
    finally:
        db.close()
