"""文件类型校验 — 通过魔数（文件头签名）检测真实 MIME 类型。"""

# 已知文件签名: (offset, magic_bytes, mime_type)
# 使用 list 而非 dict，因为 (0, b"RIFF") 对应多种格式（AVI + WEBP）
_SIGNATURES: list[tuple[int, bytes, str]] = [
    # 视频
    (4, b"ftyp",                "video/mp4"),
    (0, b"\x00\x00\x00\x1cftyp", "video/mp4"),
    (0, b"RIFF",                "video/x-msvideo"),  # AVI, 需配合 offset 8 二次校验
    (0, b"\x1aE\xdf\xa3",       "video/x-matroska"), # MKV
    # 图片
    (0, b"\xff\xd8\xff",        "image/jpeg"),
    (0, b"\x89PNG\r\n\x1a\n",   "image/png"),
    (0, b"GIF87a",              "image/gif"),
    (0, b"GIF89a",              "image/gif"),
    (0, b"RIFF",                "image/webp"),       # 需 offset 8 二次校验为 "WEBP"
]

# RIFF 容器需二次校验偏移 8 的子类型
_RIFF_SUBTYPES: dict[str, bytes] = {
    "video/x-msvideo": b"AVI ",
    "image/webp":      b"WEBP",
}


def detect_mime(content: bytes) -> str | None:
    """通过文件头魔数检测真实 MIME 类型，未识别返回 None。"""
    if len(content) < 12:
        return None
    for offset, magic, mime in _SIGNATURES:
        if content[offset:offset + len(magic)] == magic:
            # RIFF 容器格式需要二次校验子类型
            if expected := _RIFF_SUBTYPES.get(mime):
                if content[8:12] != expected:
                    continue
            return mime
    return None
