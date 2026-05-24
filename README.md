# Pure — 免费多功能文件工具

**Pure** 是一个 Windows 桌面工具，提供文件格式转换、压缩、磁盘空间分析和垃圾清理功能。

## 功能

- **文件格式转换** — Word/PDF/PPT/Excel/图片互转
- **文件压缩** — 视频/音频/PDF/PPT 压缩，支持自定义目标大小
- **磁盘空间分析** — 可视化 treemap，快速了解磁盘占用
- **垃圾文件扫描** — 检测缓存、临时文件、录屏、NVIDIA 缓存等

## 系统要求

- Windows 10/11 64 位
- Python 3.12+
- 可选：Microsoft Office（用于最佳转换质量）
- 可选：FFmpeg（用于视频/音频压缩）

## 下载

[![GitHub Release](https://img.shields.io/badge/Download-v1.1.0-blue)](https://github.com/FboatHongfeng/Pure-Document-hander/releases/download/v1.1.0/Pure.exe)

前往 [Releases](https://github.com/FboatHongfeng/Pure-Document-hander/releases) 下载最新版 `Pure.exe`（单文件，约 170 MB，内嵌 FFmpeg，开箱即用）。

## 从源码运行

```bash
# 1. 克隆仓库
git clone https://github.com/FboatHongfeng/Pure-Document-hander.git
cd Pure-Document-hander

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python main.py
```

## 打包为 EXE

```bash
pip install pyinstaller
python build.py
# 输出的 EXE 在 dist/Pure.exe
```

## 技术栈

- Python 3.12 + PySide6 (Qt GUI)
- python-docx / python-pptx / PyMuPDF / pdf2docx / pikepdf
- FFmpeg + Pillow

## License

MIT

## 作者

HongFeng — 成都大学计算机协会
