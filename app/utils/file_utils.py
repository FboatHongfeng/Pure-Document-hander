"""文件工具"""
import os
import shutil
from pathlib import Path


def get_file_size(path: str) -> int:
    """获取文件大小（字节）"""
    return os.path.getsize(path)


def get_dir_size(path: str) -> int:
    """递归获取目录总大小"""
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def format_size(size_bytes: int) -> str:
    """将字节转为可读字符串，自动选择合适的单位"""
    if not size_bytes or size_bytes <= 0:
        return "0 B"
    size_bytes = int(size_bytes)
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024**2:.1f} MB"
    elif size_bytes < 1024 ** 4:
        return f"{size_bytes / 1024**3:.2f} GB"
    else:
        return f"{size_bytes / 1024**4:.2f} TB"


def get_default_output_dir(category: str = "output") -> str:
    """获取默认输出目录（软件无论装在哪都能用）"""
    import os
    base = os.path.join(os.path.expanduser("~"), "Documents", "Pure", category)
    os.makedirs(base, exist_ok=True)
    return base


def get_extension(path: str) -> str:
    """返回小写扩展名，包含点号"""
    return Path(path).suffix.lower()


def safe_filename(path: str) -> str:
    """返回安全的输出文件名（避免覆盖）"""
    base, ext = os.path.splitext(path)
    if not os.path.exists(path):
        return path
    i = 1
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"


def ensure_dir(path: str) -> None:
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def is_office_file(path: str) -> bool:
    """判断是否为Office文件"""
    return get_extension(path) in (".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls")


def move_to_trash(path: str) -> None:
    """安全移动到回收站"""
    import send2trash
    send2trash.send2trash(path)


# 系统文件白名单 — 磁盘分析时不会标记为垃圾
SYSTEM_WHITELIST_EXT = {
    ".sys", ".dll", ".drv", ".inf", ".cat", ".msi",
    ".bin", ".efi", ".pdb", ".ocx", ".ax", ".cpl",
    ".mui", ".fon", ".ttf", ".otf",
}

# 系统目录白名单
SYSTEM_WHITELIST_DIRS = {
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "C:\\ProgramData\\Microsoft",
}

# 已知软件文件模式 — 跨磁盘检测时使用
KNOWN_SOFTWARE_PATTERNS = {
    "Adobe": [r"Adobe", r"Photoshop", r"Premiere"],
    "Microsoft Office": [r"Microsoft Office", r"Office\d+"],
    "Steam Games": [r"Steam", r"steamapps"],
    "Epic Games": [r"Epic Games"],
    "Tencent": [r"Tencent", r"QQ", r"WeChat"],
    "WPS": [r"WPS", r"Kingsoft"],
}


def is_system_file(path: str) -> bool:
    """判断是否为系统文件（白名单快速检查）"""
    ext = get_extension(path)
    if ext in SYSTEM_WHITELIST_EXT:
        return True
    normalized = os.path.normpath(path)
    for sys_dir in SYSTEM_WHITELIST_DIRS:
        if normalized.startswith(os.path.normpath(sys_dir)):
            return True
    return False
