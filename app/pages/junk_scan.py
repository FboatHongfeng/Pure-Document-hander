"""垃圾文件扫描页 — 主题感知"""
import os
import subprocess
import string
from collections import defaultdict
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

# ── 垃圾文件分类映射 ──
JUNK_CATEGORY_MAP = {
    "浏览器缓存": ["Chrome", "Edge", "Firefox", "QQBrowser", "IE 浏览器", "INetCache"],
    "临时文件": ["临时文件", "临时编辑", "Windows 系统临时", "系统临时"],
    "系统缓存": ["Prefetch", "Thumbnails", "预读取", "缩略图缓存", "Windows Update"],
    "软件残留": ["NVIDIA", "AMD", "VS Code", "__pycache__", "node_modules",
              "Python", "Office 最近", "着色器"],
    "聊天文件": ["QQ", "微信", "WeChat"],
    "下载残留": [".crdownload", ".part", "未完成的下载"],
    "备份文件": ["备份文件", ".bak", "旧版本残留", "备份"],
    "崩溃转储": ["崩溃转储", "CrashDumps", ".dmp", ".mdmp", "内存转储", "Windows 程序崩溃"],
    "录屏文件": ["Xbox", "录屏", "Recordings", "Captures"],
    "安装残留": ["Package Cache", "SquirrelTemp", "VisualStudio", "Visual Studio",
              "安装包缓存", "安装器临时"],
    "日志文件": ["日志", ".log"],
    "回收站": ["回收站", "RECYCLE"],
}


def _classify_junk_item(reason: str) -> str:
    """根据 reason 字段将垃圾项归类"""
    for category, keywords in JUNK_CATEGORY_MAP.items():
        for kw in keywords:
            if kw.lower() in reason.lower():
                return category
    return "其他"


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

        self._user_btn = QPushButton("扫描用户目录")
        self._user_btn.clicked.connect(self._scan_user)
        ctrl.addWidget(self._user_btn)

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

    def _scan_user(self):
        user = os.environ.get("USERPROFILE", "")
        if user and os.path.exists(user):
            self._start_scan([user])
        else:
            self._status.setText("无法获取用户目录")

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

        # Debug: trace the total_size parameter vs re-computed sum
        recomputed = sum(j.size for j in junk_items)
        logger.info(
            f"_show_result: junk_items={len(junk_items)}, "
            f"signal_total_size={total_size} ({format_size(total_size)}), "
            f"recomputed_sum={recomputed} ({format_size(recomputed)})"
        )
        if len(junk_items) > 0 and recomputed == 0:
            sample_sizes = [j.size for j in junk_items[:10]]
            logger.warning(f"  WARNING: {len(junk_items)} items but recomputed sum is 0! "
                           f"First 10 sizes: {sample_sizes}")

        total_all = recomputed
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

        # 按分类分组显示（保持类别完整）— 每类最多显示 100 条
        if file_categories:
            cats_order = ["视频", "文档", "压缩包", "图片", "音频", "程序"]
            for cat in cats_order:
                items = file_categories.get(cat, [])
                if not items:
                    continue
                cat_sz = sum(i.size for i in items)
                _add_item("", f"{cat}文件 · {len(items)}个 · 共{format_size(cat_sz)}", True)
                display_items = sorted(items, key=lambda x: x.size, reverse=True)[:100]
                for item in display_items:
                    _add_item(item.path,
                              f"{os.path.basename(item.path)}  ({format_size(item.size)})")
                if len(items) > 100:
                    _add_item(
                        None,
                        f"  ... 还有 {len(items) - 100} 个大文件未显示（已限制显示数量）"
                    )

        # 垃圾文件 — 按类别分组显示
        JUNK_CAP_PER_CATEGORY = 200
        JUNK_CAP_TOTAL = 2000
        if junk_items:
            # 归类
            categorized: dict[str, list] = defaultdict(list)
            for item in junk_items:
                cat = _classify_junk_item(item.reason)
                categorized[cat].append(item)

            # 类别摘要
            junk_cat_order = [
                "浏览器缓存", "临时文件", "系统缓存", "软件残留",
                "聊天文件", "下载残留", "备份文件", "崩溃转储",
                "录屏文件", "安装残留", "日志文件", "回收站", "其他",
            ]
            cat_info: dict[str, dict] = {}
            for cat, items in categorized.items():
                sorted_items = sorted(items, key=lambda x: x.size, reverse=True)
                cat_info[cat] = {
                    "items": sorted_items,
                    "count": len(items),
                    "total_size": sum(j.size for j in items),
                }

            total_displayed = 0
            for cat in junk_cat_order:
                if cat not in cat_info:
                    continue
                info = cat_info[cat]
                _add_item(
                    "",
                    f"  {cat} · {info['count']}个 · 共{format_size(info['total_size'])}",
                    True,
                )
                # 每类最多显示 JUNK_CAP_PER_CATEGORY 条
                display_items = info["items"][:JUNK_CAP_PER_CATEGORY]
                for item in display_items:
                    if total_displayed >= JUNK_CAP_TOTAL:
                        break
                    _add_item(item.path,
                              f"[{item.reason}] {os.path.basename(item.path)}  ({format_size(item.size)})")
                    total_displayed += 1
                if len(info["items"]) > JUNK_CAP_PER_CATEGORY:
                    _add_item(
                        None,
                        f"  ... 还有 {len(info['items']) - JUNK_CAP_PER_CATEGORY} 个文件未显示（已限制每类显示数量）"
                    )
                if total_displayed >= JUNK_CAP_TOTAL:
                    _add_item(
                        None,
                        f"  ... 已达到显示上限，仅展示前 {JUNK_CAP_TOTAL} 个文件"
                    )
                    break

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
        act_dir = QAction("打开所在文件夹", parent)
        act_dir.triggered.connect(lambda: (
            subprocess.Popen(['explorer', '/select,', os.path.abspath(path)])
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
        self._user_btn.setStyleSheet(f"""
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
