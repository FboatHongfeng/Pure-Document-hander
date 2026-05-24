"""主窗口"""
import os
import sys

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QVBoxLayout, QApplication, QMessageBox
from PySide6.QtCore import Qt

from app.widgets.sidebar import Sidebar
from app.pages.convert import ConvertPage
from app.pages.compress import CompressPage
from app.pages.disk_space import DiskSpacePage
from app.pages.junk_scan import JunkScanPage
from app.pages.settings import SettingsPage
from app.pages.donate import DonatePage
from app.utils.theme import theme
from app.utils.logger import get_logger

logger = get_logger("main_window")


class MainWindow(QMainWindow):

    def __init__(self, open_action: str | None = None, open_file: str | None = None):
        super().__init__()
        self.setWindowTitle("Pure")
        self.setMinimumSize(960, 640)
        self.resize(1100, 720)

        # App icon (兼容 PyInstaller onefile/onedir)
        from PySide6.QtGui import QIcon
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        icon_path = os.path.join(base, "resources", "pure.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            QApplication.instance().setWindowIcon(QIcon(icon_path))

        self.setStyleSheet(f"QMainWindow {{ background: {theme().palette.bg_main}; }}")

        central = QWidget()
        central.setAutoFillBackground(True)
        central.setStyleSheet(f"background-color: {theme().palette.bg_main};")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._switch_page)
        main_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setAutoFillBackground(True)
        self.stack.setStyleSheet(f"background-color: {theme().palette.bg_main};")

        self.pages = [
            ConvertPage(),      # 0
            CompressPage(),     # 1
            DiskSpacePage(),    # 2
            JunkScanPage(),     # 3
            SettingsPage(),     # 4
            DonatePage(),       # 5
        ]

        for page in self.pages:
            self.stack.addWidget(page)

        main_layout.addWidget(self.stack, 1)

        # 命令行参数处理
        start_index = 0
        if open_action == "convert" and open_file and os.path.exists(open_file):
            start_index = 0
            self.pages[0]._on_file_selected(open_file)
            self.pages[0].drop_zone.set_text(f"已选择: {os.path.basename(open_file)}")
            self.sidebar.buttons[0].setChecked(True)
        elif open_action == "compress" and open_file and os.path.exists(open_file):
            start_index = 1
            self.pages[1]._on_file_selected(open_file)
            self.pages[1].drop_zone.set_text(f"已选择: {os.path.basename(open_file)}")
            self.sidebar.buttons[1].setChecked(True)

        self.stack.setCurrentIndex(start_index)

        theme().changed.connect(self._on_theme_changed)
        logger.info("主窗口初始化完成")

    def _on_theme_changed(self, _):
        p = theme().palette
        self.setStyleSheet(f"QMainWindow {{ background: {p.bg_main}; }}")
        self.centralWidget().setStyleSheet(f"background-color: {p.bg_main};")
        self.stack.setStyleSheet(f"background-color: {p.bg_main};")

    def _switch_page(self, index: int):
        if 0 <= index < len(self.pages):
            # 离开设置页时检查未保存更改
            current = self.stack.currentIndex()
            if current == 4 and index != 4:
                settings_page = self.pages[4]
                settings_page.maybe_save()  # 有修改会弹窗，没有则直接通过
            self.stack.setCurrentIndex(index)

    def closeEvent(self, event):
        """窗口关闭时清理所有后台线程"""
        for page in self.pages:
            # 停止压缩/转换 worker
            for attr in ("_w", "_worker"):
                w = getattr(page, attr, None)
                if w and w.isRunning():
                    w.terminate()
                    w.wait(1000)
            # 停止磁盘扫描线程
            for attr in ("_thread", "_drill_thread"):
                t = getattr(page, attr, None)
                if t and t.isRunning():
                    t.terminate()
                    t.wait(1000)
            # 停止垃圾扫描线程
            jw = getattr(page, "worker", None)
            if jw and jw.isRunning():
                jw.terminate()
                jw.wait(1000)
        # 断开主题信号
        try:
            theme().changed.disconnect()
        except Exception:
            pass
        # 遍历所有子控件 deleteLater
        for page in self.pages:
            page.deleteLater()
        super().closeEvent(event)
