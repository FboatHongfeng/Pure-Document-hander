"""文件工具函数测试"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.file_utils import get_extension, format_size, get_file_size


class TestGetExtension:
    def test_lowercase(self):
        assert get_extension("file.mp4") == ".mp4"

    def test_uppercase(self):
        assert get_extension("FILE.MP4") == ".mp4"

    def test_mixed_case(self):
        assert get_extension("File.Pdf") == ".pdf"

    def test_chinese_filename(self):
        assert get_extension("视频文件.mp4") == ".mp4"

    def test_no_extension(self):
        assert get_extension("noext") == ""

    def test_double_extension(self):
        assert get_extension("archive.tar.gz") == ".gz"


class TestFormatSize:
    def test_bytes(self):
        assert format_size(500) == "500 B"

    def test_kb(self):
        assert "KB" in format_size(2048)

    def test_mb(self):
        assert "MB" in format_size(5 * 1024 * 1024)

    def test_gb(self):
        assert "GB" in format_size(3 * 1024 * 1024 * 1024)

    def test_zero(self):
        assert format_size(0) == "0 B"


class TestGetFileSize:
    def test_returns_int(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"x" * 100)
        sz = get_file_size(str(f))
        assert sz == 100
        assert isinstance(sz, int)

    def test_nonexistent(self):
        assert get_file_size("/nonexistent/file.bin") == 0
