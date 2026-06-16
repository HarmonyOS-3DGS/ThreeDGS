"""压缩引擎 — 纯函数，无 Celery/DB 依赖。"""

import os

from backend.worker.models.compressor import Compressor as StubCompressor

_COMPRESSORS = {
    "spz": StubCompressor.compress_ply_to_spz,
    "sog": StubCompressor.compress_ply_to_sog,
}


def compress_model(
    model_path: str,
    output_dir: str,
    formats: list[str],
) -> dict[str, str]:
    """将模型压缩为指定格式，返回 {format: output_path}。"""
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"model file not found: {model_path}")

    results: dict[str, str] = {}
    for fmt in formats:
        fn = _COMPRESSORS.get(fmt)
        if fn:
            path = fn(model_path, output_dir)
            results[fmt] = path
    return results
