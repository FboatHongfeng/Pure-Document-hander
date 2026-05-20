"""外部依赖管理器 — 检测和管理 FFmpeg、LibreOffice 等"""
import os
import sys
import subprocess
import shutil
from pathlib import Path


def _get_bundled_dir() -> str:
    """获取内置依赖目录（打包后与exe同目录）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_ffmpeg() -> str | None:
    """查找FFmpeg路径：先查内置目录，再查PATH"""
    bundled = os.path.join(_get_bundled_dir(), "ffmpeg", "bin", "ffmpeg.exe")
    if os.path.exists(bundled):
        return bundled
    # PATH 搜索
    path = shutil.which("ffmpeg")
    if path:
        return path
    return None


def find_ffprobe() -> str | None:
    """查找ffprobe路径"""
    bundled = os.path.join(_get_bundled_dir(), "ffmpeg", "bin", "ffprobe.exe")
    if os.path.exists(bundled):
        return bundled
    path = shutil.which("ffprobe")
    if path:
        return path
    return None


def find_libreoffice() -> str | None:
    """查找LibreOffice可执行文件"""
    # 常见安装位置
    paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    path = shutil.which("soffice")
    if path:
        return path
    return None


def check_ffmpeg_available() -> bool:
    """检测FFmpeg是否可用"""
    exe = find_ffmpeg()
    if not exe:
        return False
    try:
        subprocess.run([exe, "-version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def check_libreoffice_available() -> bool:
    """检测LibreOffice是否可用"""
    exe = find_libreoffice()
    if not exe:
        return False
    try:
        subprocess.run([exe, "--version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def get_ffmpeg_info() -> dict:
    """获取FFmpeg信息"""
    exe = find_ffmpeg()
    if not exe:
        return {"available": False}
    try:
        result = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=10)
        return {
            "available": True,
            "path": exe,
            "version": result.stdout.split("\n")[0] if result.stdout else "unknown",
        }
    except Exception:
        return {"available": False}


def get_libreoffice_info() -> dict:
    """获取LibreOffice信息"""
    exe = find_libreoffice()
    if not exe:
        return {"available": False}
    return {"available": True, "path": exe}
