"""磁盘分析服务 — 快速扫描 + 垃圾检测 + 白名单保护"""
import os
import re
import shutil
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from app.utils.file_utils import (
    get_extension, format_size, is_system_file,
    SYSTEM_WHITELIST_EXT,
)
from app.utils.logger import get_logger

logger = get_logger("disk_scanner")


@dataclass
class DiskOverview:
    drive: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    category_sizes: dict[str, int] = field(default_factory=dict)
    file_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class JunkItem:
    path: str
    size: int
    reason: str
    confidence: float


@dataclass
class ScanResult:
    overviews: list[DiskOverview] = field(default_factory=list)
    junk_files: list[JunkItem] = field(default_factory=list)
    total_junk_size: int = 0


# 分类映射
EXT_CATEGORY_MAP = {
    ".doc": "documents", ".docx": "documents", ".pdf": "documents",
    ".xls": "documents", ".xlsx": "documents", ".ppt": "documents",
    ".pptx": "documents", ".txt": "documents", ".md": "documents",
    ".csv": "documents", ".odt": "documents",
    ".mp4": "videos", ".avi": "videos", ".mkv": "videos",
    ".mov": "videos", ".wmv": "videos", ".flv": "videos",
    ".webm": "videos", ".m4v": "videos", ".mts": "videos",
    ".mp3": "audio", ".wav": "audio", ".flac": "audio",
    ".aac": "audio", ".ogg": "audio", ".wma": "audio", ".m4a": "audio",
    ".jpg": "images", ".jpeg": "images", ".png": "images",
    ".gif": "images", ".bmp": "images", ".svg": "images",
    ".webp": "images", ".ico": "images", ".tiff": "images",
    ".zip": "archives", ".rar": "archives", ".7z": "archives",
    ".tar": "archives", ".gz": "archives", ".bz2": "archives",
    ".exe": "programs", ".msi": "programs", ".dll": "programs",
    ".apk": "programs",
}

# 跳过目录（加速）
SKIP_DIRS = {
    "$Recycle.Bin", "System Volume Information", "Config.Msi",
    "MSOCache", "node_modules", ".git", "__pycache__",
    "Windows", "Program Files", "Program Files (x86)",
    "Python312", "Python311",
}

# 垃圾文件模式 (正则, 软件来源说明, 置信度)
JUNK_PATTERNS = [
    # ── 游戏录屏 ──
    (r".*\\Videos\\Captures\\.*\.mp4$", "Xbox Game Bar 自动游戏录屏", 0.85),
    (r".*\\Recordings\\.*\.(mp4|avi|flv)$", "屏幕录制软件生成的录像", 0.80),
    # ── NVIDIA 显卡缓存 ──
    (r".*\\.nvph$", "NVIDIA GeForce Experience 着色器缓存", 0.85),
    (r".*\\NVIDIA.*\\cache\\.*", "NVIDIA 驱动程序缓存", 0.80),
    (r".*\\AppData\\Local\\NVIDIA\\.*\\Cache\\.*", "NVIDIA GeForce Experience 缓存", 0.80),
    (r".*\\AppData\\LocalLow\\NVIDIA\\.*", "NVIDIA 旧版驱动残留缓存", 0.80),
    # ── AMD 显卡缓存 ──
    (r".*\\AMD.*\\cache\\.*", "AMD 驱动程序缓存", 0.80),
    (r".*\\AppData\\Local\\AMD\\.*", "AMD Adrenalin 软件缓存", 0.80),
    # ── 浏览器缓存 ──
    (r".*\\AppData\\Local\\Google\\Chrome.*\\Cache\\.*", "Chrome 浏览器缓存", 0.75),
    (r".*\\AppData\\Local\\Microsoft\\Edge.*\\Cache\\.*", "Edge 浏览器缓存", 0.75),
    (r".*\\AppData\\Local\\Mozilla\\Firefox.*\\cache2\\.*", "Firefox 浏览器缓存", 0.75),
    (r".*\\AppData\\Roaming\\Tencent\\QQBrowser.*\\Cache\\.*", "QQ浏览器缓存", 0.75),
    (r".*\\INetCache\\.*", "IE 浏览器缓存", 0.70),
    (r".*\\AppData\\Local\\Microsoft\\Windows\\INetCache\\.*", "IE 浏览器缓存 (系统目录)", 0.70),
    # ── 下载残留 ──
    (r".*\\Downloads\\.*\.crdownload$", "Chrome 未完成的下载", 0.90),
    (r".*\\Downloads\\.*\.part$", "Firefox 未完成的下载", 0.85),
    # ── 即时通讯 ──
    (r".*\\AppData\\Roaming\\Tencent\\QQ.*\\image\\.*", "QQ 聊天图片缓存", 0.75),
    (r".*\\AppData\\Roaming\\Tencent\\WeChat.*\\Cache\\.*", "微信 (WeChat) 缓存", 0.75),
    (r".*\\AppData\\Roaming\\Tencent\\WeChat.*\\File\\.*", "微信 (WeChat) 接收的文件", 0.60),
    (r".*\\Documents\\WeChat Files\\.*\\File\\.*", "微信 (WeChat) 下载文件", 0.55),
    # ── 办公与开发 ──
    (r".*~\\.tmp$", "Microsoft Office 临时编辑文件", 0.85),
    (r".*\\AppData\\Roaming\\Microsoft\\Office\\Recent\\.*", "Office 最近文档记录", 0.50),
    (r".*\\.log\\.\d+$", "软件运行旧日志", 0.85),
    (r".*\\.log$", "软件运行日志", 0.50),
    (r".*node_modules\\.*", "Node.js 模块缓存 (node_modules)", 0.40),
    (r".*\\.pyc$", "Python 编译缓存 (.pyc)", 0.70),
    (r".*__pycache__\\.*", "Python 模块缓存 (__pycache__)", 0.70),
    (r".*\\AppData\\Roaming\\Code\\Cache\\.*", "VS Code 编辑器缓存", 0.75),
    (r".*\\AppData\\Roaming\\Code\\CachedData\\.*", "VS Code 代码提示缓存", 0.75),
    # ── 系统 ──
    (r".*\\.tmp$", "Windows 临时文件", 0.90),
    (r".*\\AppData\\Local\\Temp\\.*", "Windows 系统临时目录", 0.70),
    (r".*\\CrashDumps\\.*\\.dmp$", "Windows 程序崩溃转储", 0.95),
    (r".*\\AppData\\Local\\CrashDumps\\.*", "Windows 程序崩溃转储目录", 0.95),
    (r".*\\.mdmp$", "Windows 内存转储文件", 0.95),
    (r".*\\Thumbnails\\.*", "Windows 资源管理器缩略图缓存", 0.75),
    (r".*\\Windows\\SoftwareDistribution\\Download\\.*", "Windows Update 更新下载缓存", 0.75),
    (r".*\\Windows\\Prefetch\\.*", "Windows 预读取缓存 (Prefetch)", 0.60),
    (r".*\\Windows\\Temp\\.*", "Windows 系统临时文件", 0.70),
    # ── 安装残留 ──
    (r".*\\AppData\\Local\\Package Cache\\.*", "Visual Studio 安装包缓存", 0.75),
    (r".*\\AppData\\Local\\Microsoft\\VisualStudio.*\\ComponentModelCache\\.*", "Visual Studio 组件缓存", 0.80),
    (r".*\\AppData\\Local\\SquirrelTemp\\.*", "Squirrel 安装器临时文件 (Teams/Discord等)", 0.80),
    # ── 备份 ──
    (r".*\\.bak$", "软件自动备份文件", 0.60),
    (r".*\\.old$", "软件升级旧版本残留", 0.65),
    # ── 回收站 ──
    (r".*\\\$RECYCLE\.BIN\\.*", "Windows 回收站文件", 0.40),
]

KNOWN_SOFTWARE_PATTERNS = {
    "Adobe": [r"Adobe", r"Photoshop", r"Premiere"],
    "Microsoft Office": [r"Microsoft Office", r"Office\d+"],
    "Steam": [r"Steam", r"steamapps"],
    "Epic": [r"Epic Games"],
    "Tencent": [r"Tencent", r"QQ", r"WeChat"],
    "WPS": [r"WPS", r"Kingsoft"],
}


def _classify(ext: str) -> str:
    return EXT_CATEGORY_MAP.get(ext, "other")


def _scan_directory(path: str, depth: int, max_depth: int,
                    progress_cb: Callable[[str], None] | None = None) -> dict:
    """快速扫描目录 — 使用 scandir 代替 walk"""
    stats = defaultdict(lambda: {"size": 0, "count": 0})
    if depth > max_depth:
        return stats

    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if progress_cb and depth <= 1:
                    progress_cb(f"扫描: {entry.name[:40]}")
                try:
                    if entry.is_file(follow_symlinks=False):
                        ext = get_extension(entry.name)
                        cat = _classify(ext)
                        size = entry.stat(follow_symlinks=False).st_size
                        stats[cat]["size"] += size
                        stats[cat]["count"] += 1
                    elif entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS and not entry.name.startswith("."):
                            sub = _scan_directory(entry.path, depth + 1, max_depth, progress_cb)
                            for cat, v in sub.items():
                                stats[cat]["size"] += v["size"]
                                stats[cat]["count"] += v["count"]
                except OSError:
                    continue
    except (PermissionError, OSError):
        pass

    return stats


def scan_drive(drive: str, max_depth: int = 2,
               progress_cb: Callable[[str], None] | None = None) -> DiskOverview:
    usage = shutil.disk_usage(drive)
    overview = DiskOverview(
        drive=drive,
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
    )
    if progress_cb:
        progress_cb(f"正在扫描 {drive} ...")
    stats = _scan_directory(drive, 0, max_depth, progress_cb)
    for cat, v in stats.items():
        overview.category_sizes[cat] = v["size"]
        overview.file_counts[cat] = v["count"]

    logger.info(f"磁盘扫描完成: {drive}, 类别: {len(stats)}")
    return overview


def scan_all_drives(max_depth: int = 2,
                    progress_cb: Callable[[str], None] | None = None) -> ScanResult:
    """并行扫描所有磁盘"""
    import string
    from ctypes import windll

    drives = []
    bitmask = windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            path = f"{letter}:\\"
            if os.path.exists(path):
                drives.append(path)
        bitmask >>= 1

    result = ScanResult()

    if progress_cb:
        progress_cb(f"发现 {len(drives)} 个磁盘，开始并行扫描...")

    with ThreadPoolExecutor(max_workers=min(len(drives), 4)) as executor:
        futures = {executor.submit(scan_drive, d, max_depth): d for d in drives}
        for i, future in enumerate(as_completed(futures)):
            try:
                overview = future.result()
                result.overviews.append(overview)
                if progress_cb:
                    progress_cb(f"磁盘扫描: {i+1}/{len(drives)} 完成")
            except Exception as e:
                logger.error(f"扫描磁盘失败: {e}")

    return result


# 垃圾扫描专用的跳过列表（比空间分析更宽松，能扫到更多垃圾）
JUNK_SKIP = {"$Recycle.Bin", "System Volume Information",
             "node_modules", ".git", "__pycache__", ".vscode"}

EXTRA_JUNK_ROOTS = [
    "%USERPROFILE%\\AppData\\Local\\Temp",
    "%USERPROFILE%\\AppData\\Local\\Microsoft\\Windows\\INetCache",
    "%USERPROFILE%\\AppData\\Roaming\\Tencent",
    "%USERPROFILE%\\Documents\\WeChat Files",
    "%PROGRAMDATA%\\NVIDIA Corporation",
    "%PROGRAMDATA%\\Package Cache",
    "%LOCALAPPDATA%\\NVIDIA",
    "%LOCALAPPDATA%\\CrashDumps",
    "%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\Cache",
    "%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\Default\\Cache",
]


def find_junk_files(drives: list[str] | None = None,
                    progress_cb: Callable[[str], None] | None = None) -> list[JunkItem]:
    """搜索垃圾文件 — 深度扫描用户目录和常见缓存位置"""
    if drives is None:
        drives = ["C:\\"]

    junk_items: list[JunkItem] = []
    user_profile = os.environ.get("USERPROFILE", "C:\\Users")
    compiled = [(re.compile(p, re.IGNORECASE), reason, conf)
                for p, reason, conf in JUNK_PATTERNS]

    for drive in drives:
        # 扫描根路径
        if drive == "C:\\" and os.path.exists(user_profile):
            scan_roots = [user_profile]
            # 添加常见垃圾聚集目录
            for p in EXTRA_JUNK_ROOTS:
                expanded = os.path.expandvars(p)
                if os.path.exists(expanded):
                    scan_roots.append(expanded)
        else:
            scan_roots = [drive]

        for root in scan_roots:
            if not os.path.exists(root):
                continue
            if progress_cb:
                progress_cb(f"分析: {os.path.basename(root)}")
            for dirpath, dirnames, filenames in os.walk(root):
                # 用更宽松的跳过规则
                dirnames[:] = [d for d in dirnames
                               if d not in JUNK_SKIP and not d.startswith(".")]
                for filename in filenames:
                    full_path = os.path.join(dirpath, filename)
                    if is_system_file(full_path):
                        continue
                    for pattern, reason, confidence in compiled:
                        if pattern.match(full_path):
                            try:
                                size = os.path.getsize(full_path)
                            except OSError:
                                size = 0
                            if size > 0:
                                junk_items.append(JunkItem(
                                    path=full_path, size=size,
                                    reason=reason, confidence=confidence,
                                ))
                            break
                    # 限制总数避免内存爆炸
                    if len(junk_items) > 5000:
                        break
                if len(junk_items) > 5000:
                    break

    if progress_cb:
        progress_cb(f"垃圾分析完成: {len(junk_items)} 个可疑文件")
    logger.info(f"垃圾扫描: {len(junk_items)} 项")
    return junk_items


# 大文件分类映射
FILE_CATEGORIES = {
    "视频": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mts"},
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".svg"},
    "音频": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"},
    "文档": {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".txt", ".csv", ".md"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "程序": {".exe", ".msi", ".dll", ".apk"},
}


def scan_large_files(drives: list[str] | None = None,
                     min_size: int = 10 * 1024 * 1024,
                     progress_cb=None) -> dict[str, list[JunkItem]]:
    """按类型扫描大文件（>10MB），返回分类字典"""
    if drives is None:
        drives = ["C:\\"]
    result: dict[str, list[JunkItem]] = {cat: [] for cat in FILE_CATEGORIES}
    user_profile = os.environ.get("USERPROFILE", "C:\\Users")

    for drive in drives:
        scan_roots = [user_profile] if drive == "C:\\" else [drive]
        for root in scan_roots:
            if not os.path.exists(root):
                continue
            if progress_cb:
                progress_cb(f"扫描大文件: {os.path.basename(root)}")
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames
                               if d not in JUNK_SKIP and not d.startswith(".")]
                for fn in filenames:
                    fp = os.path.join(dirpath, fn)
                    try:
                        sz = os.path.getsize(fp)
                    except OSError:
                        continue
                    if sz < min_size:
                        continue
                    if is_system_file(fp):
                        continue
                    ext = os.path.splitext(fn)[1].lower()
                    for cat, exts in FILE_CATEGORIES.items():
                        if ext in exts:
                            result[cat].append(JunkItem(
                                path=fp, size=sz,
                                reason=f"{cat}文件 ({ext})",
                                confidence=0.9))
                            break
                if progress_cb:
                    progress_cb(f"大文件: {os.path.basename(dirpath)}")
    return result


def analyze_cross_disk_software(junk_files: list[JunkItem]) -> list[JunkItem]:
    """排除已知软件的跨磁盘文件"""
    filtered = []
    for item in junk_files:
        is_software = False
        for sw_name, patterns in KNOWN_SOFTWARE_PATTERNS.items():
            for p in patterns:
                if re.search(p, item.path, re.IGNORECASE):
                    is_software = True
                    break
            if is_software:
                break
        if is_software and item.confidence < 0.7:
            continue
        if is_software:
            item.confidence -= 0.3
        filtered.append(item)
    return filtered
