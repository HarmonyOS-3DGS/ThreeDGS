"""Tests for train_gs task."""
import pytest
from unittest.mock import patch
from backend.worker.tasks.train_gs import train_gaussian_splatting


class TestTrain:
    def test_train_returns_model_path(self):
        with patch("backend.worker.tasks.train_gs.time.sleep"):
            result = train_gaussian_splatting.run(
                {"project_id": "test-id", "colmap_dir": "/tmp/colmap"},
                iterations=100,
            )
        assert "model_path" in result
        assert "test-id" in result["model_path"]

    def test_train_generates_ply(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            with patch("backend.worker.tasks.train_gs.time.sleep"):
                result = train_gaussian_splatting.run(
                    {"project_id": "test-id", "colmap_dir": td},
                    iterations=100,
                )
            assert os.path.exists(result["model_path"])
            with open(result["model_path"]) as f:
                content = f.read()
            assert "ply" in content
