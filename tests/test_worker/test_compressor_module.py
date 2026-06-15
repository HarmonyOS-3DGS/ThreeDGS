"""Tests for Compressor pure function module."""

import os
import tempfile

from backend.worker.compressor import compress_model


class TestCompressModel:
    def test_spz_format(self):
        with tempfile.TemporaryDirectory() as td:
            ply_path = os.path.join(td, "model.ply")
            with open(ply_path, "w") as f:
                f.write("ply\nformat ascii 1.0\nend_header\n0 0 0\n")
            output_dir = os.path.join(td, "out")
            result = compress_model(ply_path, output_dir, ["spz"])
            assert "spz" in result
            assert os.path.isfile(result["spz"])
            assert result["spz"].endswith(".spz")

    def test_sog_format(self):
        with tempfile.TemporaryDirectory() as td:
            ply_path = os.path.join(td, "model.ply")
            with open(ply_path, "w") as f:
                f.write("ply\nformat ascii 1.0\nend_header\n0 0 0\n")
            output_dir = os.path.join(td, "out")
            result = compress_model(ply_path, output_dir, ["sog"])
            assert "sog" in result
            assert os.path.isfile(result["sog"])
            assert result["sog"].endswith(".sog")

    def test_both_formats(self):
        with tempfile.TemporaryDirectory() as td:
            ply_path = os.path.join(td, "model.ply")
            with open(ply_path, "w") as f:
                f.write("ply\nformat ascii 1.0\nend_header\n0 0 0\n")
            output_dir = os.path.join(td, "out")
            result = compress_model(ply_path, output_dir, ["spz", "sog"])
            assert "spz" in result
            assert "sog" in result
            assert len(result) == 2

    def test_empty_formats(self):
        with tempfile.TemporaryDirectory() as td:
            ply_path = os.path.join(td, "model.ply")
            with open(ply_path, "w") as f:
                f.write("ply\nformat ascii 1.0\nend_header\n0 0 0\n")
            output_dir = os.path.join(td, "out")
            result = compress_model(ply_path, output_dir, [])
            assert result == {}

    def test_missing_input_raises_error(self):
        import pytest

        with tempfile.TemporaryDirectory() as td:
            ply_path = os.path.join(td, "nonexistent.ply")
            output_dir = os.path.join(td, "out")
            with pytest.raises(FileNotFoundError):
                compress_model(ply_path, output_dir, ["spz"])
