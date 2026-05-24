"""Pure 构建脚本

用法:
  python build.py              # 默认: onedir 目录模式（包含FFmpeg）
  python build.py --onefile    # 单EXE模式（包含FFmpeg，功能完整）
  python build.py --installer  # 创建NSIS安装器（包含FFmpeg）
"""
import os
import sys
import shutil
import subprocess
import zipfile
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
FFMPEG_DIR = PROJECT_ROOT / "ffmpeg"
RESOURCES_DIR = PROJECT_ROOT / "resources"


def download_ffmpeg() -> bool:
    """下载 FFmpeg Windows 便携版 (精简版 ~40MB)"""
    import time
    if FFMPEG_DIR.exists() and (FFMPEG_DIR / "bin" / "ffmpeg.exe").exists():
        print("[OK] FFmpeg 已存在")
        return True

    print("[...] 下载 FFmpeg (约40MB)...")
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    zip_path = PROJECT_ROOT / f"ffmpeg_{int(time.time())}.zip"
    try:
        urllib.request.urlretrieve(url, zip_path)
        print("[...] 解压 FFmpeg...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            root_dirs = {n.split("/")[0] for n in zf.namelist()}
            zf.extractall(PROJECT_ROOT)

        # 重命名解压出的目录
        for d in PROJECT_ROOT.iterdir():
            if d.is_dir() and d.name.startswith("ffmpeg-"):
                if FFMPEG_DIR.exists():
                    shutil.rmtree(FFMPEG_DIR)
                shutil.move(str(d), str(FFMPEG_DIR))
                print("[OK] FFmpeg 下载完成")
                return True

        print("[FAIL] 无法找到解压后的FFmpeg目录")
        return False
    except Exception as e:
        print(f"[FAIL] 下载失败: {e}")
        return False
    finally:
        try:
            if zip_path.exists():
                zip_path.unlink()
        except Exception:
            pass


def get_ffmpeg_binaries() -> list[tuple[str, str]]:
    """返回 (源路径, 目标相对路径) 列表，用于 PyInstaller --add-binary"""
    if not FFMPEG_DIR.exists():
        return []
    binaries = []
    bin_dir = FFMPEG_DIR / "bin"
    if bin_dir.exists():
        for exe in bin_dir.glob("*.exe"):
            binaries.append((str(exe), f"ffmpeg/bin"))
        for dll in bin_dir.glob("*.dll"):
            binaries.append((str(dll), f"ffmpeg/bin"))
    return binaries


def build_onedir():
    """目录模式构建 — 包含FFmpeg，用户拿到的是文件夹"""
    print("\n=== 构建模式: onedir (推荐) ===\n")

    if not download_ffmpeg():
        print("[!] FFmpeg缺失，视频/音频功能将不可用")

    add_data = [
        str(RESOURCES_DIR) + os.pathsep + "resources",
    ]

    add_binaries = get_ffmpeg_binaries()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Pure",
        "--onedir",
        "--windowed",
        "--clean",
        "--noconfirm",
    ]

    for src, dst in add_binaries:
        cmd += ["--add-binary", f"{src}{os.pathsep}{dst}"]

    for data in add_data:
        cmd += ["--add-data", data]

    cmd += [
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=reportlab",
        "--hidden-import=docx",
        "--hidden-import=pptx",
        "--hidden-import=PIL",
        "--hidden-import=pdf2docx",
        "--hidden-import=pikepdf",
        "--hidden-import=py7zr",
        "--hidden-import=patoolib",
        "--hidden-import=send2trash",
        "--hidden-import=ffmpeg",
        str(PROJECT_ROOT / "main.py"),
    ]

    subprocess.run(cmd, check=True)
    print(f"\n[OK] 构建完成: {PROJECT_ROOT / 'dist' / 'Pure'}")

    # 复制FFmpeg到输出目录（PyInstaller不会自动复制add-binary到正确位置）
    dist_ffmpeg = PROJECT_ROOT / "dist" / "Pure" / "ffmpeg"
    if FFMPEG_DIR.exists() and not dist_ffmpeg.exists():
        shutil.copytree(str(FFMPEG_DIR), str(dist_ffmpeg))
        print(f"[OK] FFmpeg 已复制到输出目录")


def build_onefile():
    """单EXE模式 — 包含FFmpeg，功能完整"""
    print("\n=== 构建模式: onefile (单EXE，功能完整) ===\n")

    if not download_ffmpeg():
        print("[!] FFmpeg缺失，视频/音频功能将不可用")

    add_data = [
        str(RESOURCES_DIR) + os.pathsep + "resources",
    ]

    add_binaries = get_ffmpeg_binaries()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Pure",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
    ]

    for src, dst in add_binaries:
        cmd += ["--add-binary", f"{src}{os.pathsep}{dst}"]

    for data in add_data:
        cmd += ["--add-data", data]

    cmd += [
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=reportlab",
        "--hidden-import=docx",
        "--hidden-import=pptx",
        "--hidden-import=PIL",
        "--hidden-import=pdf2docx",
        "--hidden-import=pikepdf",
        "--hidden-import=py7zr",
        "--hidden-import=patoolib",
        "--hidden-import=send2trash",
        str(PROJECT_ROOT / "main.py"),
    ]

    subprocess.run(cmd, check=True)
    print(f"\n[OK] 构建完成: {PROJECT_ROOT / 'dist' / 'Pure.exe'}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "onedir"

    # 安装PyInstaller
    try:
        import PyInstaller
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    if mode == "--onefile":
        build_onefile()
    elif mode == "--installer":
        print("Installer 模式: 先构建 onedir，再用 NSIS 打包...")
        build_onedir()
        print("\n请安装 NSIS (https://nsis.sourceforge.io) 后手动创建安装包。")
        print(f"安装目录: {PROJECT_ROOT / 'dist' / 'Pure'}")
    else:
        build_onedir()


if __name__ == "__main__":
    main()
