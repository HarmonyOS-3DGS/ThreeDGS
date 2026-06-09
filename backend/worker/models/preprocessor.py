"""预处理 Stub — 帧提取与 COLMAP SfM 空壳实现。"""

import os


class Preprocessor:
    """模拟 FFmpeg 帧提取 + COLMAP SfM 的 Stub 预处理器。"""

    @staticmethod
    def extract_frames(video_path: str, output_dir: str, fps: int = 5) -> str:
        """模拟 FFmpeg 帧提取，生成 dummy 帧文件。"""
        os.makedirs(output_dir, exist_ok=True)
        # Stub: 生成 dummy 帧文件
        for i in range(10):
            dummy = os.path.join(output_dir, f"frame_{i:04d}.jpg")
            with open(dummy, "wb") as f:
                f.write(b"DUMMY_JPEG_DATA")
        return output_dir

    @staticmethod
    def run_colmap(image_dir: str, output_dir: str) -> str:
        """模拟 COLMAP SfM，生成 dummy 输出文件。"""
        os.makedirs(output_dir, exist_ok=True)
        sparse_dir = os.path.join(output_dir, "sparse", "0")
        os.makedirs(sparse_dir, exist_ok=True)

        for fname in ["cameras.txt", "images.txt", "points3D.txt"]:
            with open(os.path.join(sparse_dir, fname), "w") as f:
                f.write(f"# Dummy {fname}\n")
        return output_dir
