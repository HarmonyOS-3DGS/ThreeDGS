"""文件类型校验 — 通过魔数（文件头签名）检测真实 MIME 类型。

工作原理：
  1. 读取文件前 12+ 字节
  2. 在 _SIGNATURES 中按 (offset, magic) 匹配
  3. RIFF 容器（AVI/WEBP）额外校验 offset 8 的子类型标识
  4. 未识别返回 None → 调用方 soft-pass（不阻碍上传）

为何用 list[tuple] 而非 dict：
  (0, b"RIFF") 同时匹配 AVI 和 WEBP，dict 会 key 冲突。
  list 允许同一签名对应多种类型，结合 _RIFF_SUBTYPES 二次鉴别。
"""

# (offset, magic_bytes, mime_type)
_SIGNATURES: list[tuple[int, bytes, str]] = [
    # 视频
    (4, b"ftyp", "video/mp4"),
    (0, b"\x00\x00\x00\x1cftyp", "video/mp4"),
    (0, b"RIFF", "video/x-msvideo"),  # AVI, 需配合 offset 8 二次校验
    (0, b"\x1aE\xdf\xa3", "video/x-matroska"),  # MKV
    # 图片
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
    (0, b"RIFF", "image/webp"),  # 需 offset 8 二次校验为 "WEBP"
]

# RIFF 容器需二次校验偏移 8 的子类型
_RIFF_SUBTYPES: dict[str, bytes] = {
    "video/x-msvideo": b"AVI ",
    "image/webp": b"WEBP",
}


def detect_mime(content: bytes) -> str | None:
    """通过文件头魔数检测真实 MIME 类型，未识别返回 None。"""
    if len(content) < 12:
        return None
    for offset, magic, mime in _SIGNATURES:
        if content[offset : offset + len(magic)] == magic:
            # RIFF 容器格式需要二次校验子类型
            if expected := _RIFF_SUBTYPES.get(mime):
                if content[8:12] != expected:
                    continue
            return mime
    return None
