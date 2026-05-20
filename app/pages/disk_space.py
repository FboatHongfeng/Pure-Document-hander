"""磁盘空间可视化 — squarified treemap + 面包屑导航"""
import os
import string
from ctypes import windll

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFileDialog, QSizePolicy,
)
from PySide6.QtCore import QThread, Signal, Qt

from app.widgets.treemap import TreemapWidget, TreeNode
from app.utils.file_utils import format_size
from app.utils.theme import theme
from app.utils.logger import get_logger

logger = get_logger("disk_space")


# 始终跳过
SKIP_NAMES = {"$Recycle.Bin", "System Volume Information", "Config.Msi",
              "node_modules", ".git", "__pycache__", ".vscode"}
# 大系统目录：扫描时不递归深入，但显示为叶子节点
HEAVY_DIRS = {"Windows", "Program Files", "Program Files (x86)",
              "WinSxS", "Microsoft", "assembly", "Fonts",
              "Microsoft.NET", "Python312", "Python311", "packages"}
MAX_DIRS = 100
MAX_FILES = 2000


def _get_dir_size_fast(path: str) -> int:
    """快速获取目录大小——用 scandir 走一层，对大目录粗略估算"""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                pass
    except (PermissionError, OSError):
        pass
    return total


def _get_dir_size_deep(path: str, max_depth: int) -> int:
    """递归获取目录大小——scandir 深度遍历"""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    if entry.name not in SKIP_NAMES and not entry.name.startswith("."):
                        if max_depth > 0:
                            total += _get_dir_size_deep(entry.path, max_depth - 1)
                        else:
                            total += _get_dir_size_fast(entry.path)
            except OSError:
                pass
    except (PermissionError, OSError):
        pass
    return total


def _scan_tree(path: str, depth: int, max_depth: int, prog_cb) -> TreeNode:
    basename = os.path.basename(path) or path
    node = TreeNode(name=basename, path=path, size=0, is_dir=True)

    try:
        entries = list(os.scandir(path))
    except (PermissionError, OSError):
        return node

    dirs, files = [], []
    for e in entries:
        try:
            if e.is_dir(follow_symlinks=False):
                if e.name not in SKIP_NAMES and not e.name.startswith("."):
                    dirs.append(e)
            elif e.is_file(follow_symlinks=False):
                if len(files) < MAX_FILES:
                    files.append(e)
        except OSError:
            continue

    done = 0
    total = len(dirs) + min(len(files), MAX_FILES)

    # 子目录：用 _get_dir_size_deep 获取真实大小
    dir_sizes = []
    for d in dirs:
        try:
            sz = _get_dir_size_fast(d.path)  # 快速估算用于排序
        except OSError:
            sz = 0
        dir_sizes.append((d, sz))
    dir_sizes.sort(key=lambda x: x[1], reverse=True)

    for d, est_sz in dir_sizes[:MAX_DIRS]:
        done += 1
        if prog_cb and total > 0:
            prog_cb(min(done / max(total, 1), 1.0) * 0.9)

        if d.name in HEAVY_DIRS or depth >= max_depth:
            # 叶子节点：深度遍历获取准确大小
            if d.name == "Windows" or d.name == "WinSxS":
                scan_depth = 6
            elif d.name in ("Program Files", "Program Files (x86)", "ProgramData"):
                scan_depth = 5
            elif depth >= max_depth:
                scan_depth = 4
            else:
                scan_depth = 4
            real_sz = _get_dir_size_deep(d.path, scan_depth)
            child = TreeNode(name=d.name, path=d.path, size=real_sz, is_dir=True)
        else:
            child = _scan_tree(d.path, depth + 1, max_depth, prog_cb)
        if child.size > 0 or child.children:
            node.children.append(child)

    # 文件按类型聚合
    type_sizes: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for f in files:
        try:
            sz = f.stat(follow_symlinks=False).st_size
        except OSError:
            sz = 0
        ext = os.path.splitext(f.name)[1].lower() or "[无扩展名]"
        type_sizes[ext] = type_sizes.get(ext, 0) + sz
        type_counts[ext] = type_counts.get(ext, 0) + 1

    for ext, sz in sorted(type_sizes.items(), key=lambda x: x[1], reverse=True)[:20]:
        if sz > 0:
            node.children.append(TreeNode(
                name=f"{ext} ({type_counts[ext]}个)",
                path=os.path.join(path, f"[{ext}]"),
                size=sz, is_dir=False))

    if prog_cb:
        prog_cb(1.0)

    node.size = sum(c.size for c in node.children)
    return node


class ScanThread(QThread):
    progress = Signal(float)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, path: str, max_depth: int = 4, parent=None):
        super().__init__(parent)
        self._path = path
        self._max_depth = max_depth

    def run(self):
        try:
            import signal
            root = _scan_tree(self._path, 0, self._max_depth,
                              prog_cb=lambda p: self.progress.emit(p))
            self.finished.emit(root)
        except Exception as e:
            import traceback
            self.error.emit(f"扫描出错: {e}")


class DiskSpacePage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        theme().changed.connect(self._refresh_style)

    def _build_ui(self):
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(6)

        # 标题 + 面包屑
        top = QHBoxLayout()
        self._title = QLabel("磁盘空间分析")
        self._title.setObjectName("pageTitle")
        self._title.setStyleSheet("font-size: 20px; font-weight: bold;")
        top.addWidget(self._title)
        top.addSpacing(16)

        self.breadcrumb_layout = QHBoxLayout()
        top.addLayout(self.breadcrumb_layout)
        top.addStretch()
        layout.addLayout(top)

        # 控制栏
        ctrl = QHBoxLayout()

        self.scan_all_btn = QPushButton("扫描全部磁盘")
        self.scan_all_btn.clicked.connect(self._scan_all_disks)
        ctrl.addWidget(self.scan_all_btn)

        self._stop_btn = QPushButton("终止扫描")
        self._stop_btn.clicked.connect(self._stop_scan)
        self._stop_btn.setVisible(False)
        ctrl.addWidget(self._stop_btn)

        self._browse_btn = QPushButton("选择目录...")
        self._browse_btn.clicked.connect(self._scan_folder)
        ctrl.addWidget(self._browse_btn)

        self._back_btn = QPushButton("← 返回上级")
        self._back_btn.clicked.connect(lambda: self.treemap.go_up())
        self._back_btn.setVisible(False)
        ctrl.addWidget(self._back_btn)

        self._status = QLabel("")
        self._status.setObjectName("statusLabel")
        ctrl.addWidget(self._status)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # 磁盘快捷按钮行
        self._drive_btns_layout = QHBoxLayout()
        layout.addLayout(self._drive_btns_layout)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Treemap
        self.treemap = TreemapWidget()
        self.treemap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.treemap.path_changed.connect(self._on_treemap_path)
        self.treemap.node_clicked.connect(lambda _: self._back_btn.setVisible(True))
        self.treemap.drill_needed.connect(self._drill_down)
        layout.addWidget(self.treemap, 1)

        self._treemap_hint = QLabel("左键进入子目录 | 右键打开文件夹")
        layout.addWidget(self._treemap_hint)

        self._refresh_style("light")

    # ---------- 逻辑 ----------

    def _scan_all_disks(self):
        self._clear_drive_btns()
        drives = self._get_drives()
        for d in drives:
            btn = QPushButton(f"  {d}  ")
            btn.setObjectName("driveBtn")
            btn.clicked.connect(lambda checked, path=d: self._start_scan(path))
            self._drive_btns_layout.addWidget(btn)
        self._drive_btns_layout.addStretch()
        self._status.setText(f"请选择磁盘 ({len(drives)} 个可用)")

    def _scan_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            self._clear_drive_btns()
            self._start_scan(path)

    def _start_scan(self, path: str):
        logger.info(f"磁盘扫描开始: {path}")
        try:
            self.scan_all_btn.setVisible(False)
            self._stop_btn.setVisible(True)
            self._progress.setVisible(True)
            self._progress.setValue(0)
            self._status.setText(f"扫描 {path} ...")
            self._back_btn.setVisible(False)

            self._thread = ScanThread(path)
            self._thread.progress.connect(lambda v: self._progress.setValue(int(v * 100)))
            self._thread.finished.connect(self._on_done)
            self._thread.error.connect(self._on_scan_error)
            self._thread.start()
        except Exception as e:
            logger.exception(f"启动扫描失败: {e}")
            self._status.setText(f"扫描启动失败: {e}")
            self._scan_finished()

    def _stop_scan(self):
        if hasattr(self, '_thread') and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait(1000)
            self._status.setText("扫描已终止")
        self._scan_finished()

    def _scan_finished(self):
        self._progress.setVisible(False)
        self.scan_all_btn.setVisible(True)
        self._stop_btn.setVisible(False)

    def _on_scan_error(self, error_msg: str):
        try:
            logger.error(f"扫描错误: {error_msg}")
            self._scan_finished()
            self._status.setText(f"扫描失败: {error_msg[:60]}")
        except Exception:
            pass

    def _on_done(self, root: TreeNode):
        try:
            logger.info(f"扫描完成: {root.name}, size={root.display_size}, children={len(root.children)}")
            self._scan_finished()
            self._status.setText(
                f"{root.name} — {root.display_size} ({len(root.children)} 类)"
            )
            self.treemap.set_data(root)
            self._update_breadcrumbs()
        except Exception as e:
            logger.exception(f"渲染结果失败: {e}")
            self._scan_finished()
            self._status.setText(f"渲染失败: {e}")

    def _drill_down(self, path: str):
        """按需深度扫描"""
        # 防止并发
        if hasattr(self, '_drill_thread') and self._drill_thread.isRunning():
            return
        logger.info(f"按需深度扫描: {path}")
        self._status.setText(f"正在深入扫描 {os.path.basename(path)} ...")
        self._progress.setVisible(True)

        def on_done(new_root):
            try:
                self._progress.setVisible(False)
                if new_root.children and hasattr(self, 'treemap'):
                    current = self.treemap._current
                    if current and current.children:
                        for i, child in enumerate(current.children):
                            if child.path == path:
                                current.children[i] = new_root
                                break
                    self.treemap._current = new_root
                    self.treemap._breadcrumb.append(new_root)
                    self.treemap._layout()
                    self.treemap.update()
                    self._back_btn.setVisible(True)
                    self._update_breadcrumbs()
                    self._status.setText(
                        f"{new_root.name} — {new_root.display_size} ({len(new_root.children)} 类)")
                else:
                    self._status.setText("此目录无可读内容（权限不足或为空）")
            except Exception as e:
                logger.exception(f"深入扫描回调失败: {e}")
                self._progress.setVisible(False)

        self._drill_thread = ScanThread(path, max_depth=4)
        self._drill_thread.finished.connect(on_done)
        self._drill_thread.error.connect(lambda e: (
            logger.error(f"深度扫描失败: {e}"),
            self._status.setText("扫描失败"),
            self._progress.setVisible(False)
        ))
        self._drill_thread.start()

    def _on_treemap_path(self, path: str):
        self._update_breadcrumbs()

    def _update_breadcrumbs(self):
        while self.breadcrumb_layout.count():
            item = self.breadcrumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        crumbs = self.treemap._breadcrumb
        for i, node in enumerate(crumbs):
            if i > 0:
                sep = QLabel("›")
                sep.setStyleSheet(f"color: {theme().palette.text_secondary}; "
                                  "font-size: 14px; border: none; padding: 0 2px;")
                self.breadcrumb_layout.addWidget(sep)
            btn = QPushButton(node.name[:18])
            btn.setStyleSheet(
                f"border: none; color: {theme().palette.accent}; "
                "font-size: 12px; padding: 2px 4px; background: transparent;"
            )
            idx = i
            btn.clicked.connect(lambda checked, n=idx: self.treemap.go_to_index(n))
            self.breadcrumb_layout.addWidget(btn)

    @staticmethod
    def _get_drives() -> list[str]:
        drives = []
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                p = f"{letter}:\\"
                if os.path.exists(p):
                    drives.append(p)
            bitmask >>= 1
        return drives

    def _clear_drive_btns(self):
        while self._drive_btns_layout.count():
            item = self._drive_btns_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ---------- 主题 ----------

    def _refresh_style(self, _):
        p = theme().palette

        self.setStyleSheet(f"background-color: {p.bg_main};")
        self._title.setStyleSheet(
            f"font-size:20px; font-weight:bold; color:{p.text_primary}; border:none;")
        self._status.setStyleSheet(
            f"font-size:13px; color:{p.text_secondary}; border:none;")

        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                background:{p.bg_input}; border:1px solid {p.border_card};
                border-radius:8px; padding:6px 14px;
                color:{p.text_primary}; font-size:13px;
            }}
            QPushButton:hover {{ background:{p.bg_hover}; }}
        """)
        self.scan_all_btn.setStyleSheet(f"""
            QPushButton {{
                background:{p.accent}; border:none; border-radius:6px;
                padding:8px 16px; color:{p.accent_text};
                font-size:13px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{p.accent_hover}; }}
        """)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background:#d63031; border:none; border-radius:6px;
                padding:8px 16px; color:#ffffff;
                font-size:13px; font-weight:bold;
            }}
            QPushButton:hover {{ background:#e84141; }}
        """)
        self._treemap_hint.setStyleSheet(
            f"font-size: 11px; color: {p.text_muted}; border: none; padding: 2px 4px;")

        self._browse_btn.setStyleSheet(f"""
            QPushButton {{
                background:{p.bg_input}; border:1px solid {p.border_card};
                border-radius:8px; padding:6px 14px;
                color:{p.text_primary}; font-size:13px;
            }}
            QPushButton:hover {{ background:{p.bg_hover}; }}
        """)
