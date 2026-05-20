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

## 从源码运行

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/Pure.git
cd Pure

# 2. 安装依赖
pip install -r requirements.txt

# 3. （可选）安装 FFmpeg
# 下载地址: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
# 解压后将 ffmpeg.exe 和 ffprobe.exe 放到 Pure/ffmpeg/bin/ 目录下
# 或者将 FFmpeg 添加到系统 PATH 环境变量

# 4. 运行
python main.py
```

## 打包为 EXE

```bash
pip install pyinstaller
python build.py
# 输出的 EXE 在 dist/Pure.exe
```

## 项目结构

```
Pure/
├── main.py                    # 入口
├── app/
│   ├── main_window.py         # 主窗口
│   ├── pages/                 # 各功能页面
│   │   ├── convert.py         # 文件转换
│   │   ├── compress.py        # 文件压缩
│   │   ├── disk_space.py      # 磁盘空间
│   │   ├── junk_scan.py       # 垃圾扫描
│   │   ├── settings.py        # 设置
│   │   └── donate.py          # 用爱发电
│   ├── services/              # 核心服务
│   │   ├── converter.py       # 转换引擎
│   │   ├── compressor.py      # 压缩引擎
│   │   ├── disk_scanner.py    # 磁盘扫描
│   │   ├── dependency.py      # 依赖检测
│   │   └── shell_integration.py # 右键菜单
│   ├── widgets/               # UI 组件
│   └── utils/                 # 工具函数
├── resources/
│   ├── i18n/zh_CN.json        # 文本配置
│   └── *.png                  # 图片资源
└── requirements.txt
```

## 技术栈

- Python 3.12
- PySide6 (Qt GUI)
- python-docx / python-pptx / PyMuPDF / pdf2docx / pikepdf
- FFmpeg (视频音频处理)
- Pillow (图片处理)

## 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 修改界面文本
# 编辑 resources/i18n/zh_CN.json

# 添加新转换器
# 1. 在 app/services/converter.py 中实现 ConverterInterface
# 2. 调用 _register() 注册
# 3. 界面自动适配
```

## License

MIT

## 作者

HongFeng — 成都大学计算机协会
