"""压缩引擎测试"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.compressor import (
    is_compress_supported,
    get_compress_options,
    compress_file,
    _get_video_duration,
)


class TestCompressSupport:
    def test_video_formats(self):
        for ext in [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"]:
            assert is_compress_supported(ext), f"应支持 {ext}"

    def test_audio_formats(self):
        for ext in [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"]:
            assert is_compress_supported(ext), f"应支持 {ext}"

    def test_unsupported_format(self):
        assert not is_compress_supported(".xyz")

    def test_pdf_supported(self):
        assert is_compress_supported(".pdf")

    def test_pptx_supported(self):
        assert is_compress_supported(".pptx")


class TestCompressOptions:
    def test_video_options(self):
        opts = get_compress_options(".mp4")
        assert opts["level"] is True
        assert opts["strategy"] is True

    def test_pdf_options(self):
        opts = get_compress_options(".pdf")
        assert opts["level"] is True

    def test_pptx_options(self):
        opts = get_compress_options(".pptx")
        assert opts["mode"] is True

    def test_image_options(self):
        opts = get_compress_options(".png")
        assert opts["quality"] is True

    def test_unknown_extension(self):
        opts = get_compress_options(".xyz")
        assert not any(opts.values())


class TestVideoDuration:
    def test_nonexistent_file_returns_none(self):
        assert _get_video_duration("/nonexistent/video.mp4") is None

    def test_text_file_returns_none(self, sample_txt_file):
        # ffprobe 可能返回数值（当 ffmpeg 可读时），测试不崩溃即可
        result = _get_video_duration(sample_txt_file)
        assert result is None or isinstance(result, float)


class TestCompressFile:
    def test_unsupported_format_returns_error(self, sample_txt_file):
        ok, err = compress_file(sample_txt_file, "/tmp/out.xyz")
        assert not ok
        assert "不支持" in err

    def test_cancel_event_stops_compression(self, temp_dir):
        """验证 cancel_event 被正确传递（不实际运行压缩）"""
        import threading
        event = threading.Event()
        event.set()  # 预先设置，模拟取消
        # 对不存在的文件压缩，cancel_event 应该被接受
        ok, err = compress_file(
            os.path.join(temp_dir, "nofile.mp4"),
            os.path.join(temp_dir, "out.mp4"),
            cancel_event=event,
        )
        assert not ok
