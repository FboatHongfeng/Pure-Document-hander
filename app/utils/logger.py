"""日志系统 — 输出到文件，带时间戳"""
import os
import logging
import datetime
from pathlib import Path


_log_initialized = False
_log_path: str = ""


def _get_log_dir() -> str:
    """日志目录：优先项目目录下，其次用户目录"""
    candidates = []
    try:
        import sys
        if getattr(sys, "frozen", False):
            candidates.append(os.path.join(os.path.dirname(sys.executable), "logs"))
        else:
            base = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            candidates.append(os.path.join(base, "logs"))
    except Exception:
        pass
    candidates.append(os.path.join(os.path.expanduser("~"), ".pure", "logs"))
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except OSError:
            continue
    return ""


def init_logging() -> str:
    """初始化日志系统，返回日志文件路径"""
    global _log_initialized, _log_path
    if _log_initialized:
        return _log_path

    log_dir = _get_log_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d")
    _log_path = os.path.join(log_dir, f"pure_{timestamp}.log")

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(_log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    root = logging.getLogger("pure")
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    _log_initialized = True
    root.info(f"=== Pure 日志启动 === 路径: {_log_path}")
    return _log_path


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger"""
    if not _log_initialized:
        init_logging()
    return logging.getLogger(f"pure.{name}")


def get_log_path() -> str:
    """返回当前日志文件路径"""
    if not _log_initialized:
        init_logging()
    return _log_path
