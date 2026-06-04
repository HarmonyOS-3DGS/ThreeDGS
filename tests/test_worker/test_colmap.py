"""Tests for colmap_sfm task."""
import pytest
from unittest.mock import patch
from backend.worker.tasks.colmap_sfm import run_colmap


class TestColmap:
    def test_run_colmap_returns_paths(self):
        with patch("backend.worker.tasks.colmap_sfm.time.sleep"):
            result = run_colmap.run({"project_id": "test-id", "frames_dir": "/tmp/frames"})
        assert result["project_id"] == "test-id"
        assert "colmap_dir" in result

    def test_run_colmap_creates_files(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            with patch("backend.worker.tasks.colmap_sfm.time.sleep"):
                result = run_colmap.run({"project_id": "test-id", "frames_dir": td})
            colmap_dir = result["colmap_dir"]
            assert os.path.exists(os.path.join(colmap_dir, "sparse", "0", "cameras.txt"))
