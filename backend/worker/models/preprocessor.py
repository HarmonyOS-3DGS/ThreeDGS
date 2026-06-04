"""Preprocessor stub for frame extraction and COLMAP."""
import os
import shutil


class Preprocessor:
    """Stub preprocessor that simulates FFmpeg frame extraction and COLMAP SfM."""

    @staticmethod
    def extract_frames(video_path: str, output_dir: str, fps: int = 5) -> str:
        """Simulate FFmpeg frame extraction by copying a sample image."""
        os.makedirs(output_dir, exist_ok=True)
        # Stub: create dummy frame files
        for i in range(10):
            dummy = os.path.join(output_dir, f"frame_{i:04d}.jpg")
            with open(dummy, "wb") as f:
                f.write(b"DUMMY_JPEG_DATA")
        return output_dir

    @staticmethod
    def run_colmap(image_dir: str, output_dir: str) -> str:
        """Simulate COLMAP SfM by creating dummy output files."""
        os.makedirs(output_dir, exist_ok=True)
        sparse_dir = os.path.join(output_dir, "sparse", "0")
        os.makedirs(sparse_dir, exist_ok=True)

        for fname in ["cameras.txt", "images.txt", "points3D.txt"]:
            with open(os.path.join(sparse_dir, fname), "w") as f:
                f.write(f"# Dummy {fname}\n")
        return output_dir
