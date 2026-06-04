"""Compressor stub for PLY to SPZ/SOG conversion."""
import os


class Compressor:
    """Stub compressor that simulates format conversion and compression."""

    @staticmethod
    def compress_ply_to_spz(ply_path: str, output_dir: str) -> str:
        """Simulate PLY to SPZ compression."""
        os.makedirs(output_dir, exist_ok=True)
        spz_path = os.path.join(output_dir, "model.spz")
        with open(spz_path, "wb") as f:
            f.write(b"SPZ_STUB_DATA")
        return spz_path

    @staticmethod
    def compress_ply_to_sog(ply_path: str, output_dir: str) -> str:
        """Simulate PLY to SOG compression."""
        os.makedirs(output_dir, exist_ok=True)
        sog_path = os.path.join(output_dir, "model.sog")
        with open(sog_path, "wb") as f:
            f.write(b"SOG_STUB_DATA")
        return sog_path
