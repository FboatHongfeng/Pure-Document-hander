"""设置页面 — Toggle 开关 + 输出路径 + 折叠分组"""
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QFileDialog, QScrollArea, QSizePolicy, QMessageBox,
)
from PySide6.QtCore import Qt

from app.services.shell_integration import (
    install_context_menu, uninstall_context_menu, is_context_menu_installed,
)
from app.widgets.toggle import ToggleSwitch
from app.utils.i18n import t
from app.utils.theme import theme
from app.utils.config import config


def _default_dir(kind: str) -> str:
    return os.path.join(os.path.expanduser("~"), "Documents", "Pure", kind)


class SectionHeader(QPushButton):
    """可折叠分组标题 — 三角箭头随展开/折叠变化"""

    def __init__(self, text: str, parent=None):
        self._base_text = text
        super().__init__(f"▾ {text}", parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.setFixedHeight(34)
        self.toggled.connect(self._update_arrow)

    def _update_arrow(self, checked):
        arrow = "▾" if checked else "▸"
        self.setText(f"{arrow} {self._base_text}")

    def _apply_style(self, p):
        self.setStyleSheet(f"""
            QPushButton {{
                text-align:left; border:none; border-radius:6px;
                padding:6px 14px; font-size:15px; font-weight:bold;
                color:{p.text_primary}; background:{p.bg_card};
                border:1px solid {p.border_card};
            }}
            QPushButton:hover {{ background:{p.bg_hover}; }}
            QPushButton:checked {{ color:{p.text_primary}; background:{p.bg_card}; }}
        """)


class PathRow(QFrame):
    """输出路径行: 标签 + 路径编辑框 + 浏览按钮"""

    def __init__(self, label: str, default_kind: str, parent=None):
        super().__init__(parent)
        self._default_kind = default_kind
        self._default_path = _default_dir(default_kind)
        self.setAutoFillBackground(True)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        self._lbl = QLabel(f"{label}:")
        self._lbl.setFixedWidth(90)
        row.addWidget(self._lbl)
        self._input = QLineEdit()
        self._input.setText(self._default_path)
        row.addWidget(self._input, 1)
        self._btn = QPushButton("浏览...")
        self._btn.clicked.connect(self._browse)
        row.addWidget(self._btn)
        self._open_btn = QPushButton("打开")
        self._open_btn.setToolTip("打开输出目录")
        self._open_btn.clicked.connect(self._open_dir)
        row.addWidget(self._open_btn)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._apply_style(theme().palette)
        theme().changed.connect(lambda _: self._apply_style(theme().palette))

    def _apply_style(self, p):
        self.setStyleSheet(f"background:{p.bg_card}; border:1px solid {p.border_card};"
                           f"border-radius:8px;")
        self._lbl.setStyleSheet(f"font-size:13px; color:{p.text_primary}; border:none;")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background:{p.bg_input}; border:1px solid {p.border_card};
                border-radius:4px; padding:2px 6px;
                color:{p.text_primary}; font-size:12px;
            }}
        """)
        btn_qss = f"""
            QPushButton {{
                background:{p.bg_input}; border:1px solid {p.border_card};
                border-radius:4px; padding:4px 12px;
                color:{p.text_primary}; font-size:12px;
            }}
            QPushButton:hover {{ background:{p.bg_hover}; }}
        """
        self._btn.setStyleSheet(btn_qss)
        self._open_btn.setStyleSheet(btn_qss)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self._input.setText(d)
            # 通知父页面标记dirty
            p = self.parent()
            while p:
                if hasattr(p, '_dirty'):
                    p._dirty = True
                    break
                p = p.parent()

    def _open_dir(self):
        import os as _os
        _os.startfile(self.path)

    @property
    def path(self) -> str:
        return self._input.text().strip() or self._default_path


class SettingsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dirty = False
        self._build_ui()
        self._load_settings()
        self._refresh_context_menu_state()
        theme().changed.connect(self._refresh_style)

    def _build_ui(self):
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(8)

        # 标题
        self._title_lbl = QLabel("设置")
        self._title_lbl.setStyleSheet("font-size:22px; font-weight:bold;")
        layout.addWidget(self._title_lbl)
        self._desc_lbl = QLabel("管理可选功能和输出路径")
        self._desc_lbl.setStyleSheet("font-size:13px;")
        layout.addWidget(self._desc_lbl)

        layout.addSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(6)

        # ── 外观 ──
        theme_row = self._toggle_row("深色模式", "开启深色/暗黑主题", "theme")
        self._sw_theme.toggled.connect(lambda v: (theme().set_theme("dark" if v else "light"), setattr(self, '_dirty', True)))
        self._add_section("外观", [theme_row])

        # ── 集成 ──
        self._ctx_row = self._toggle_row(
            "右键菜单集成",
            "在文件右键添加 Purue 转换/压缩选项",
            "context_menu",
        )
        self._sw_context_menu.toggled.connect(lambda v: (self._on_ctx_toggled(v), setattr(self, '_dirty', True)))
        self._add_section("系统集成", [self._ctx_row])

        # ── 输出目录 ──
        self._convert_path = PathRow("文件转换", "convert")
        self._compress_path = PathRow("文件压缩", "compress")
        self._output_section_content = QWidget()
        out_layout = QVBoxLayout(self._output_section_content)
        out_layout.setContentsMargins(0, 2, 0, 2)
        out_layout.setSpacing(4)
        out_layout.addWidget(self._convert_path)
        out_layout.addWidget(self._compress_path)
        self._add_section("输出目录", [self._output_section_content])

        self._content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # 底部按钮
        save_btn = QPushButton("保存设置")
        save_btn.setFixedHeight(40)
        save_btn.clicked.connect(self._save_all)
        layout.addWidget(save_btn)

        self._refresh_style("light")

    def _toggle_row(self, title: str, desc: str, key: str) -> QWidget:
        w = QWidget()
        w.setAutoFillBackground(True)
        row = QHBoxLayout(w)
        row.setContentsMargins(12, 8, 12, 8)
        info = QVBoxLayout()
        tl = QLabel(title)
        tl.setStyleSheet("font-size:14px; font-weight:bold; border:none;")
        info.addWidget(tl)
        dl = QLabel(desc)
        dl.setStyleSheet("font-size:11px; border:none;")
        info.addWidget(dl)
        row.addLayout(info, 1)
        sw = ToggleSwitch()
        row.addWidget(sw)
        setattr(self, f"_sw_{key}", sw)
        setattr(self, f"_tw_{key}_title", tl)
        setattr(self, f"_tw_{key}_desc", dl)
        setattr(self, f"_tw_{key}_widget", w)
        return w

    def _add_section(self, title: str, rows: list):
        header = SectionHeader(title)
        self._content_layout.addWidget(header)
        self._content_layout.addWidget(QLabel())  # spacer
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(4, 2, 4, 2)
        cl.setSpacing(4)
        for r in rows:
            cl.addWidget(r)
        self._content_layout.addWidget(container)
        container.setVisible(False)  # 默认折叠
        header.toggled.connect(lambda v, c=container: c.setVisible(v))
        # Save refs for theme
        if not hasattr(self, '_sections'):
            self._sections = []
        self._sections.append((header, container))

    # ── 数据 ──

    def _load_settings(self):
        theme().set_theme(config.get("theme", "light"))
        sw = getattr(self, "_sw_theme", None)
        if sw:
            sw.blockSignals(True)
            sw.setChecked(config.get("theme", "light") == "dark")
            sw.blockSignals(False)
        for attr, key in [(self._convert_path, "convert_dir"),
                          (self._compress_path, "compress_dir")]:
            dir_ = config.get(key)
            if dir_ and os.path.isdir(dir_):
                attr._input.setText(dir_)
        installed = is_context_menu_installed()
        sw_ctx = getattr(self, "_sw_context_menu", None)
        if sw_ctx:
            sw_ctx.blockSignals(True)
            sw_ctx.setChecked(installed)
            sw_ctx.blockSignals(False)

    def _save_all(self):
        config.set("theme", theme().current)
        # 仅当用户显式修改了路径才保存，不保存默认值
        for attr, key in [(self._convert_path, "convert_dir"),
                           (self._compress_path, "compress_dir")]:
            custom = attr._input.text().strip()
            if custom and custom != attr._default_path:
                config.set(key, custom)
            else:
                config.set(key, "")  # 与默认值相同或为空，清空让后续使用默认值
        config.save()
        self._dirty = False
        self._update_main_pages()
        self._navigate_to(0)

    def has_unsaved(self) -> bool:
        return self._dirty

    def maybe_save(self) -> bool:
        """弹窗询问保存。返回 True=已保存/不保存, False=未触发（无修改）"""
        if not self._dirty:
            return False
        box = QMessageBox(self)
        box.setWindowTitle("未保存的更改")
        box.setText("设置已修改，是否保存？")
        box.setIcon(QMessageBox.Question)
        save_btn = box.addButton("保存", QMessageBox.AcceptRole)
        box.addButton("不保存", QMessageBox.DestructiveRole)
        box.setDefaultButton(save_btn)
        box.exec()
        if box.clickedButton() == save_btn:
            self._save_all()
        else:
            self._dirty = False
        return True

    def _update_main_pages(self):
        """更新主窗口中所有页面的输出目录"""
        w = self.window()
        if w and hasattr(w, 'pages'):
            convert_dir = self._convert_path.path
            compress_dir = self._compress_path.path
            # 更新转换页
            cp = w.pages[0]
            cp._output_dir = convert_dir
            cp._out_dir_label.setText(convert_dir)
            # 更新压缩页
            cmp = w.pages[1]
            cmp._output_dir = compress_dir
            cmp._out_dir_label.setText(compress_dir)

    def _navigate_to(self, index):
        w = self.window()
        if w and hasattr(w, 'sidebar'):
            w.sidebar._on_click(index)

    def _on_ctx_toggled(self, checked):
        if checked:
            install_context_menu()
        else:
            uninstall_context_menu()

    def _refresh_context_menu_state(self):
        installed = is_context_menu_installed()
        sw = getattr(self, "_sw_context_menu", None)
        if sw:
            sw.blockSignals(True)
            sw.setChecked(installed)
            sw.blockSignals(False)

    # ── 主题 ──

    def _refresh_style(self, _):
        p = theme().palette
        self.setStyleSheet(f"background-color: {p.bg_main};")
        self._title_lbl.setStyleSheet(
            f"font-size:22px; font-weight:bold; color:{p.text_primary};")
        self._desc_lbl.setStyleSheet(
            f"font-size:13px; color:{p.text_secondary};")

        for header, _ in getattr(self, '_sections', []):
            header._apply_style(p)
        # Toggle rows - all labels get theme color
        for key in ["theme", "context_menu"]:
            w = getattr(self, f"_tw_{key}_widget", None)
            tl = getattr(self, f"_tw_{key}_title", None)
            dl = getattr(self, f"_tw_{key}_desc", None)
            if w:
                w.setStyleSheet(
                    f"background:{p.bg_card}; border:1px solid {p.border_card};"
                    f"border-radius:8px;")
            if tl:
                tl.setStyleSheet(
                    f"font-size:14px; font-weight:bold; color:{p.text_primary}; border:none;")
            if dl:
                dl.setStyleSheet(
                    f"font-size:12px; color:{p.text_secondary}; border:none;")

        # Save button
        save_btn = self.findChild(QPushButton, "保存设置")
        if not save_btn:
            for child in self.children():
                if isinstance(child, QPushButton) and child.text() == "保存设置":
                    save_btn = child
                    break
        if save_btn:
            save_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{p.accent}; border:none; border-radius:8px;
                    color:{p.accent_text}; font-size:15px; font-weight:bold;
                }}
                QPushButton:hover {{ background:{p.accent_hover}; }}
            """)
