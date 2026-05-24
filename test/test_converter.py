"""转换引擎测试"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.converter import (
    is_conversion_supported,
    get_target_formats,
    convert_file,
)


class TestConversionSupport:
    def test_docx_to_pdf(self):
        assert is_conversion_supported(".docx", ".pdf")

    def test_docx_to_docx(self):
        assert not is_conversion_supported(".docx", ".docx")

    def test_mp4_to_mp4_not_supported(self):
        assert not is_conversion_supported(".mp4", ".mp4")

    def test_unsupported_conversion(self):
        assert not is_conversion_supported(".xyz", ".pdf")


class TestTargetFormats:
    def test_docx_targets(self):
        targets = get_target_formats(".docx")
        assert ".pdf" in targets
        assert ".docx" not in targets  # 排除同类

    def test_unknown_format(self):
        assert get_target_formats(".xyz") == []


class TestConvertFile:
    def test_unsupported_format(self):
        ok, err = convert_file("/tmp/test.xyz", "/tmp/out.pdf")
        assert not ok
        assert "不支持" in err

    def test_cancel_event_accepted(self, tmp_path):
        """验证 cancel_event kwarg 被接受"""
        import threading
        import json
        # 创建一个简单 JSON 文件测试
        src = tmp_path / "test.json"
        src.write_text("{}")
        event = threading.Event()
        event.set()
        ok, err = convert_file(
            str(src), str(tmp_path / "out.json"),
            cancel_event=event,
        )
        assert not ok  # JSON→JSON 不被支持
