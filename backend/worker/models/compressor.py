"""压缩 Stub — PLY 到 SPZ/SOG 格式转换空壳实现。"""

import os


class Compressor:
    """模拟格式转换与压缩的 Stub 压缩器。"""

    @staticmethod
    def compress_ply_to_spz(ply_path: str, output_dir: str) -> str:
        """模拟 PLY 到 SPZ 压缩转换。"""
        os.makedirs(output_dir, exist_ok=True)
        spz_path = os.path.join(output_dir, "model.spz")
        with open(spz_path, "wb") as f:
            f.write(b"SPZ_STUB_DATA")
        return spz_path

    @staticmethod
    def compress_ply_to_sog(ply_path: str, output_dir: str) -> str:
        """模拟 PLY 到 SOG 压缩转换。"""
        os.makedirs(output_dir, exist_ok=True)
        sog_path = os.path.join(output_dir, "model.sog")
        with open(sog_path, "wb") as f:
            f.write(b"SOG_STUB_DATA")
        return sog_path
