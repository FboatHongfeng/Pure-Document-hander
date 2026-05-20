"""主题管理器 — 深色/浅色模式完整切换"""
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

# ---------- 色板 ----------

@dataclass
class Palette:
    """全局色板"""
    # 背景
    bg_main: str
    bg_sidebar: str
    bg_card: str
    bg_input: str
    bg_hover: str
    bg_drop: str
    # 边框
    border_main: str
    border_card: str
    border_drop: str
    # 文字
    text_primary: str
    text_secondary: str
    text_muted: str
    text_accent: str
    # 强调色
    accent: str
    accent_hover: str
    accent_text: str
    # 特殊
    danger_bg: str
    danger_border: str
    danger_text: str
    # 进度条
    progress_bg: str
    progress_chunk: str


PALETTE_DARK = Palette(
    bg_main="#16181d",
    bg_sidebar="#1a1d23",
    bg_card="#22252b",
    bg_input="#2a2d33",
    bg_hover="#363a42",
    bg_drop="rgba(255,255,255,0.03)",
    border_main="#2a2d33",
    border_card="#363a42",
    border_drop="#4a4d55",
    text_primary="#e8e8ed",
    text_secondary="#b0b3ba",
    text_muted="#6a6d75",
    text_accent="#6384ff",
    accent="#6384ff",
    accent_hover="#7b9fff",
    accent_text="#ffffff",
    danger_bg="#2a2225",
    danger_border="#5a4040",
    danger_text="#e09080",
    progress_bg="#2a2d33",
    progress_chunk="#6384ff",
)

PALETTE_LIGHT = Palette(
    bg_main="#f8f9fa",
    bg_sidebar="#eeeff2",
    bg_card="#ffffff",
    bg_input="#f2f3f5",
    bg_hover="#e4e6ea",
    bg_drop="rgba(0,0,0,0.03)",
    border_main="#d0d3d8",
    border_card="#dcdfe4",
    border_drop="#b0b4bb",
    text_primary="#0d1117",
    text_secondary="#2d3138",
    text_muted="#4d5158",
    text_accent="#3050e0",
    accent="#3d60f0",
    accent_hover="#5578ff",
    accent_text="#ffffff",
    danger_bg="#fff5f5",
    danger_border="#e8c0c0",
    danger_text="#b02020",
    progress_bg="#e0e3e8",
    progress_chunk="#3d60f0",
)


# ---------- 主题管理器 ----------

class ThemeManager(QObject):
    """单例主题管理器，切换时发信号通知所有页面"""

    changed = Signal(str)  # "dark" | "light"

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current = "light"
        return cls._instance

    @property
    def current(self) -> str:
        return self._current

    @property
    def palette(self) -> Palette:
        return PALETTE_DARK if self._current == "dark" else PALETTE_LIGHT

    def toggle(self) -> str:
        self._current = "light" if self._current == "dark" else "dark"
        _apply_global_qss(self.palette)
        self.changed.emit(self._current)
        return self._current

    def set_theme(self, theme: str) -> None:
        if theme not in ("dark", "light"):
            return
        if self._current == theme:
            return
        self._current = theme
        _apply_global_qss(self.palette)
        self.changed.emit(self._current)


_theme_manager: ThemeManager | None = None


def theme() -> ThemeManager:
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


# ---------- 全局 QSS 生成 ----------

def _global_qss(p: Palette) -> str:
    return f"""
        QMainWindow {{ background: {p.bg_main}; }}
        QWidget {{ color: {p.text_primary}; }}
        QLabel {{ color: {p.text_primary}; }}

        /* 输入框 */
        QComboBox {{
            background: {p.bg_card};
            border: 1px solid {p.border_card};
            border-radius: 8px;
            padding: 6px 12px;
            color: {p.text_primary};
            font-size: 13px;
            min-height: 32px;
            max-height: 32px;
        }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{
            background: {p.bg_card};
            color: {p.text_primary};
            selection-background-color: {p.accent};
            selection-color: {p.accent_text};
            border: 1px solid {p.border_card};
            border-radius: 8px;
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background: {p.accent};
            color: {p.accent_text};
        }}

        /* 滚动区域 */
        QScrollArea {{ border: none; background: transparent; }}
        QScrollBar:vertical {{
            background: {p.bg_sidebar};
            width: 6px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.bg_hover};
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar:horizontal {{
            background: {p.bg_sidebar};
            height: 6px;
            border-radius: 3px;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.bg_hover};
            border-radius: 3px;
            min-width: 20px;
        }}

        /* 进度条 */
        QProgressBar {{
            border: none;
            border-radius: 4px;
            background: {p.progress_bg};
        }}
        QProgressBar::chunk {{
            border-radius: 4px;
            background: {p.progress_chunk};
        }}

        /* 通用按钮 */
        QPushButton {{
            background: {p.bg_input};
            border: 1px solid {p.border_card};
            border-radius: 8px;
            padding: 8px 16px;
            color: {p.text_primary};
            font-size: 13px;
        }}
        QPushButton:hover {{ background: {p.bg_hover}; }}

        /* 复选框 */
        QCheckBox {{ color: {p.text_primary}; spacing: 8px; }}
        QCheckBox::indicator {{
            width: 18px; height: 18px;
            border-radius: 4px;
            border: 2px solid {p.border_card};
            background: {p.bg_input};
        }}
        QCheckBox::indicator:checked {{
            background: {p.accent};
            border-color: {p.accent};
        }}

        /* 单选框 */
        QRadioButton {{ color: {p.text_primary}; spacing: 8px; }}
    """


def _apply_global_qss(p: Palette) -> None:
    app = QApplication.instance()
    if app:
        app.setStyleSheet(_global_qss(p))
