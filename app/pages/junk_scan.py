"""垃圾文件扫描页 — 主题感知"""
import os
import subprocess
import string
from ctypes import windll

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QProgressBar, QFileDialog, QSizePolicy, QMenu,
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QAction, QCursor

from app.services.disk_scanner import (
    find_junk_files, analyze_cross_disk_software, scan_large_files,
)
from app.utils.i18n import t
from app.utils.file_utils import format_size
from app.utils.theme import theme
from app.utils.logger import get_logger

logger = get_logger("junk_scan")


class JunkWorker(QThread):
    progress = Signal(str)
    finished = Signal(list, int, dict)  # junk_items, total_size, file_categories

    def __init__(self, drives: list[str], parent=None):
        super().__init__(parent)
        self.drives = drives

    def run(self):
        self.progress.emit("正在扫描垃圾文件...")
        junk = find_junk_files(self.drives, progress_cb=lambda s: self.progress.emit(s))
        junk = analyze_cross_disk_software(junk)
        self.progress.emit("正在分析大文件分类...")
        categories = scan_large_files(self.drives, progress_cb=lambda s: self.progress.emit(s))
        self.finished.emit(junk, sum(j.size for j in junk), categories)


class JunkScanPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        theme().changed.connect(self._refresh_style)

    def _build_ui(self):
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._title = QLabel("垃圾文件扫描")
        layout.addWidget(self._title)

        self._sys_hint = QLabel("系统盘 — 已自动跳过 Windows/Program Files 等系统目录")
        self._sys_hint.setStyleSheet("font-size:12px; color:#c07830; border:none; padding:2px 0;")
        self._sys_hint.setVisible(False)
        layout.addWidget(self._sys_hint)

        self._desc = QLabel(
            "扫描可能无用的临时文件、缓存、录屏、软件残留等。\n"
            "结果仅供参考，请清理前手动确认。"
        )
        self._desc.setWordWrap(True)
        layout.addWidget(self._desc)

        ctrl = QHBoxLayout()
        self.scan_btn = QPushButton("扫描全部磁盘")
        self.scan_btn.clicked.connect(lambda: self._start_scan(None))
        ctrl.addWidget(self.scan_btn)

        self._stop_btn = QPushButton("终止扫描")
        self._stop_btn.clicked.connect(self._stop_scan)
        self._stop_btn.setVisible(False)
        ctrl.addWidget(self._stop_btn)

        self._browse_btn = QPushButton("选择目录...")
        self._browse_btn.clicked.connect(self._browse_and_scan)
        ctrl.addWidget(self._browse_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self.result_area = QScrollArea()
        self.result_area.setWidgetResizable(True)
        self.result_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_widget = QWidget()
        self.result_layout = QVBoxLayout(self.result_widget)
        self.result_layout.setSpacing(8)
        self.result_area.setWidget(self.result_widget)
        self.result_area.setVisible(False)
        layout.addWidget(self.result_area, 1)

        self._refresh_style("light")

    def _browse_and_scan(self):
        path = QFileDialog.getExistingDirectory(self, "选择要扫描的目录")
        if path:
            self._start_scan([path])

    def _start_scan(self, drives: list[str] | None):
        self.scan_btn.setVisible(False)
        self._stop_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self._clear_results()

        # 系统盘提示
        is_sys = drives is None or any(d.rstrip("\\/") in ("C:", "C") for d in drives)
        self._sys_hint.setVisible(is_sys)
        if drives is None:
            drives = []
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    p = f"{letter}:\\"
                    if os.path.exists(p):
                        drives.append(p)
                bitmask >>= 1

        self.worker = JunkWorker(drives)
        self.worker.progress.connect(self._status.setText)
        self.worker.finished.connect(self._show_result)
        self.worker.start()

    def _stop_scan(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(1000)
            self._status.setText("扫描已终止")
        self._scan_finished()

    def _scan_finished(self):
        self.progress_bar.setVisible(False)
        self.scan_btn.setVisible(True)
        self._stop_btn.setVisible(False)

    def _on_progress(self, msg: str):
        self._status.setText(msg)

    def _clear_results(self):
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_result(self, junk_items, total_size, file_categories=None):
        self._scan_finished()
        self.result_area.setVisible(True)
        self._clear_results()
        p = theme().palette

        total_all = sum(j.size for j in junk_items)
        if file_categories:
            for items in file_categories.values():
                total_all += sum(i.size for i in items)

        if not junk_items and not any(file_categories.values() if file_categories else []):
            no = QLabel("未发现垃圾文件或大文件")
            no.setStyleSheet(f"font-size:16px; color:{p.text_muted}; padding:40px;")
            no.setAlignment(Qt.AlignCenter)
            self.result_layout.addWidget(no)
            self._status.setText("扫描完成")
            return

        # 汇总
        summary = QLabel(f"预计可释放 {format_size(total_all)}")
        summary.setStyleSheet(
            f"font-size:15px; font-weight:bold; color:{p.text_primary}; padding:8px 0;")
        self.result_layout.addWidget(summary)

        warning = QLabel(t("disk_analyzer", "junk_warning"))
        warning.setStyleSheet(f"font-size:12px; color:{p.danger_text}; padding-bottom:8px;")
        warning.setWordWrap(True)
        self.result_layout.addWidget(warning)

        def _add_item(path, label_text, is_header=False):
            if is_header:
                sp = QLabel("")
                sp.setFixedHeight(4)
                self.result_layout.addWidget(sp)
                h = QLabel(f"  {label_text}")
                h.setStyleSheet(f"font-size:13px; font-weight:bold; color:{p.text_primary}; border:none; padding:4px 0;")
                self.result_layout.addWidget(h)
            else:
                w = QFrame()
                w.setStyleSheet("QFrame { background:transparent; border:none; padding:5px 8px; border-radius:6px; }")
                if path:
                    w.setContextMenuPolicy(Qt.CustomContextMenu)
                    w.customContextMenuRequested.connect(
                        lambda pos, p=path: self._show_file_menu(pos, p, w))
                r = QHBoxLayout(w); r.setContentsMargins(0,0,0,0)
                l = QLabel(f"  {label_text}")
                l.setStyleSheet(f"font-size:12px; color:{p.text_secondary}; border:none;")
                l.setWordWrap(True); l.setCursor(Qt.PointingHandCursor)
                l.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                r.addWidget(l)
                w.enterEvent = lambda e, w=w, l=l: (
                    w.setStyleSheet(f"QFrame {{ background:{p.accent}; border:none; padding:5px 8px; border-radius:6px; }}"),
                    l.setStyleSheet(f"font-size:12px; color:{p.accent_text}; border:none;"))
                w.leaveEvent = lambda e, w=w, l=l: (
                    w.setStyleSheet("QFrame { background:transparent; border:none; padding:5px 8px; border-radius:6px; }"),
                    l.setStyleSheet(f"font-size:12px; color:{p.text_secondary}; border:none;"))
                self.result_layout.addWidget(w)

        # 按分类分组显示（保持类别完整）
        if file_categories:
            cats_order = ["视频", "文档", "压缩包", "图片", "音频", "程序"]
            for cat in cats_order:
                items = file_categories.get(cat, [])
                if not items:
                    continue
                cat_sz = sum(i.size for i in items)
                _add_item("", f"{cat}文件 · {len(items)}个 · 共{format_size(cat_sz)}", True)
                for item in sorted(items, key=lambda x: x.size, reverse=True)[:8]:
                    _add_item(item.path,
                              f"{os.path.basename(item.path)}  ({format_size(item.size)})")

        # 垃圾文件
        if junk_items:
            _add_item("", f"可疑垃圾 · {len(junk_items)}个 · 共{format_size(total_size)}", True)
            for item in sorted(junk_items, key=lambda x: x.size, reverse=True)[:50]:
                _add_item(item.path,
                          f"[{item.reason}] {os.path.basename(item.path)}  ({format_size(item.size)})")

        self._status.setText(f"扫描完成 | 右键可打开文件位置")

    def _show_file_menu(self, pos, path: str, parent):
        p = theme().palette
        menu = QMenu(parent)
        menu.setStyleSheet(f"""
            QMenu {{
                background:{p.bg_card}; border:1px solid {p.border_card};
                border-radius:8px; padding:4px;
                color:{p.text_primary}; font-size:13px;
            }}
            QMenu::item {{
                padding:6px 24px;
                border-radius:4px;
            }}
            QMenu::item:selected {{
                background:{p.accent}; color:{p.accent_text};
            }}
        """)
        act_open = QAction("打开文件位置", parent)
        act_open.triggered.connect(lambda: (
            subprocess.Popen(['explorer', '/select,' + os.path.abspath(path)])
        ))
        menu.addAction(act_open)
        act_dir = QAction("打开所在文件夹", parent)
        act_dir.triggered.connect(lambda: (
            os.startfile(os.path.dirname(os.path.abspath(path)))
        ))
        menu.addAction(act_dir)
        menu.exec(QCursor.pos())

    def _refresh_style(self, _):
        p = theme().palette

        self.setStyleSheet(f"background-color: {p.bg_main};")
        self._title.setStyleSheet(
            f"font-size:22px; font-weight:bold; color:{p.text_primary}; border:none;")
        self._sys_hint.setStyleSheet(
            f"font-size:12px; color:#c07830; border:none; padding:2px 0;")
        self._desc.setStyleSheet(
            f"font-size:13px; color:{p.text_secondary}; border:none;")
        self._status.setStyleSheet(
            f"font-size:13px; color:{p.text_secondary}; border:none;")

        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; border-radius: 4px; background: {p.progress_bg}; }}
            QProgressBar::chunk {{ border-radius: 4px; background: {p.accent}; }}
        """)

        self._browse_btn.setStyleSheet(f"""
            QPushButton {{
                background:{p.bg_input}; border:1px solid {p.border_card};
                border-radius:8px; padding:8px 16px;
                color:{p.text_primary}; font-size:13px;
            }}
            QPushButton:hover {{ background:{p.bg_hover}; }}
        """)
        self.scan_btn.setStyleSheet(f"""
            QPushButton {{
                background:{p.accent}; border:none; border-radius:8px;
                padding:10px 20px; color:{p.accent_text};
                font-size:14px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{p.accent_hover}; }}
        """)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background:#d63031; border:none; border-radius:8px;
                padding:10px 20px; color:#ffffff;
                font-size:14px; font-weight:bold;
            }}
            QPushButton:hover {{ background:#e84141; }}
        """)
