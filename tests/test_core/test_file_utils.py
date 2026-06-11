"""Tests for file_utils — magic bytes detection."""

from backend.core.file_utils import detect_mime


class TestDetectMime:
    def test_detect_mp4(self):
        # ftyp at offset 4
        data = b"\x00\x00\x00\x1cftypmp42"
        assert detect_mime(data) == "video/mp4"

    def test_detect_mp4_alt(self):
        data = b"\x00\x00\x00\x1cftypisom"
        assert detect_mime(data) == "video/mp4"

    def test_detect_avi(self):
        # RIFF container with AVI subtype at offset 8
        data = b"RIFF\x00\x00\x00\x00AVI \x00\x00"
        assert detect_mime(data) == "video/x-msvideo"

    def test_detect_mkv(self):
        data = b"\x1aE\xdf\xa3" + b"\x00" * 8
        assert detect_mime(data) == "video/x-matroska"

    def test_detect_jpeg(self):
        data = b"\xff\xd8\xff" + b"\x00" * 9
        assert detect_mime(data) == "image/jpeg"

    def test_detect_png(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4
        assert detect_mime(data) == "image/png"

    def test_detect_gif87a(self):
        data = b"GIF87a" + b"\x00" * 6
        assert detect_mime(data) == "image/gif"

    def test_detect_gif89a(self):
        data = b"GIF89a" + b"\x00" * 6
        assert detect_mime(data) == "image/gif"

    def test_detect_webp(self):
        # RIFF container with WEBP subtype
        data = b"RIFF\x00\x00\x00\x00WEBP\x00\x00"
        assert detect_mime(data) == "image/webp"

    def test_unknown_format(self):
        data = b"\x00" * 12
        assert detect_mime(data) is None

    def test_short_data(self):
        assert detect_mime(b"\x00" * 5) is None

    def test_mp4_with_wide_box(self):
        data = b"\x00\x00\x00\x1cftypmp42"
        assert detect_mime(data) == "video/mp4"
