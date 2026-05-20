"""侧边栏导航 — 主题感知"""
from PySide6.QtWidgets import QPushButton, QLabel, QFrame, QVBoxLayout
from PySide6.QtCore import Signal, Qt

from app.utils.theme import theme


class SidebarButton(QPushButton):
    """功能按钮"""

    def __init__(self, text: str, icon: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._text = text
        self.setText(f"  {icon}  {text}")
        self.setCheckable(True)
        self.setFixedHeight(42)
        self._apply_style()

    def _apply_style(self):
        p = theme().palette
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                color: {p.text_secondary};
                background: transparent;
            }}
            QPushButton:hover {{
                background: {p.bg_hover};
                color: {p.text_primary};
            }}
            QPushButton:checked {{
                background: {p.accent};
                color: {p.accent_text};
                font-weight: bold;
            }}
        """)


class Sidebar(QFrame):

    page_changed = Signal(int)

    NAV_ITEMS = [
        ("文件转换", "📄"),
        ("文件压缩", "📦"),
        ("磁盘空间", "💾"),
        ("垃圾扫描", "🧹"),
    ]

    SETTINGS_INDEX = 4
    DONATE_INDEX = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.setFixedWidth(210)
        self._build_ui()
        theme().changed.connect(self._on_theme_changed)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(3)

        self._logo = QLabel("  Pure")
        self._logo.setStyleSheet("font-size: 19px; font-weight: bold; padding: 6px 10px;")
        layout.addWidget(self._logo)

        self._subtitle = QLabel("  免费多功能文件工具")
        self._subtitle.setStyleSheet("font-size: 10px; padding: 0 10px 12px;")
        layout.addWidget(self._subtitle)

        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.HLine)
        self._sep.setFixedHeight(1)
        layout.addWidget(self._sep)
        layout.addSpacing(8)

        self.buttons: list[SidebarButton] = []
        for text, icon in self.NAV_ITEMS:
            btn = SidebarButton(text, icon)
            btn.clicked.connect(lambda checked, i=len(self.buttons): self._on_click(i))
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # 设置
        self.settings_btn = QPushButton("  ⚙  设置")
        self.settings_btn.setFixedHeight(34)
        self.settings_btn.clicked.connect(lambda: self._on_click(self.SETTINGS_INDEX))
        layout.addWidget(self.settings_btn)

        # 捐赠
        self.donate_btn = QPushButton("  ❤  用爱发电")
        self.donate_btn.setFixedHeight(34)
        self.donate_btn.clicked.connect(lambda: self._on_click(self.DONATE_INDEX))
        layout.addWidget(self.donate_btn)

        self.buttons[0].setChecked(True)
        self._on_theme_changed("dark")

    def _on_click(self, index: int):
        if index >= len(self.buttons):
            self._uncheck_all()
        else:
            for i, btn in enumerate(self.buttons):
                btn.setChecked(i == index)
        self.page_changed.emit(index)

    def _uncheck_all(self):
        for btn in self.buttons:
            btn.setChecked(False)

    def _on_theme_changed(self, _):
        p = theme().palette
        self.setStyleSheet(f"""
            background-color: {p.bg_sidebar};
            border-right: 1px solid {p.border_main};
        """)
        self._logo.setStyleSheet(
            f"font-size: 19px; font-weight: bold; color: {p.accent}; padding: 6px 10px;")
        self._subtitle.setStyleSheet(
            f"font-size: 10px; color: {p.text_muted}; padding: 0 10px 12px;")
        self._sep.setStyleSheet(f"background: {p.border_main};")
        for btn in self.buttons:
            btn._apply_style()
        for b in (self.settings_btn, self.donate_btn):
            b.setStyleSheet(f"""
                QPushButton {{
                    text-align: left; border: none;
                    border-radius: 6px; padding: 4px 14px;
                    font-size: 12px; color: {p.text_muted};
                    background: transparent;
                }}
                QPushButton:hover {{
                    color: {p.text_secondary};
                    background: {p.bg_hover};
                }}
            """)
