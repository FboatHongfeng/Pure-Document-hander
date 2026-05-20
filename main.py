"""Pure 入口

命令行用法（供右键菜单调用）:
  Pure.exe --convert "文件路径"
  Pure.exe --compress "文件路径"
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.logger import init_logging, get_logger

init_logging()
logger = get_logger("main")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from app.main_window import MainWindow


def parse_args():
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg in ("--convert", "--compress"):
            file_path = args[i + 1] if i + 1 < len(args) else None
            return arg[2:], file_path
    return None, None


def main():
    logger.info("Pure 启动")

    app = QApplication(sys.argv)
    app.setApplicationName("Pure")
    app.setStyle("Fusion")

    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    # 加载保存的主题设置
    try:
        import json
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "resources", "user_settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                s = json.load(f)
            saved_theme = s.get("theme", "light")
            from app.utils.theme import theme
            theme().set_theme(saved_theme)
    except Exception:
        pass

    action, file_path = parse_args()
    if action:
        logger.info(f"命令行调用: --{action} {file_path}")

    try:
        window = MainWindow(open_action=action, open_file=file_path)
        window.show()
        logger.info("主窗口已显示")
        sys.exit(app.exec())
    except Exception as e:
        logger.exception("启动失败")
        raise


if __name__ == "__main__":
    main()
