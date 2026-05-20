"""进度组件 — 主题感知"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QProgressBar, QLabel, QFrame, QHBoxLayout,
)
from PySide6.QtCore import Qt

from app.utils.theme import theme


class ProgressCard(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self._build()
        theme().changed.connect(lambda _: self._apply_style())

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("font-size: 13px; border: none;")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        layout.addWidget(self.progress)

        info_layout = QHBoxLayout()
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("font-size: 12px; border: none;")
        info_layout.addWidget(self.detail_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        self._apply_style()

    def _apply_style(self):
        p = theme().palette
        self.setStyleSheet(f"""
            background-color: {p.bg_card};
            border: 1px solid {p.border_card};
            border-radius: 12px;
            padding: 16px;
        """)
        self.status_label.setStyleSheet(f"font-size: 13px; color: {p.text_secondary}; border: none;")
        self.detail_label.setStyleSheet(f"font-size: 12px; color: {p.text_muted}; border: none;")
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 8px; background: {p.progress_bg};
            }}
            QProgressBar::chunk {{
                border-radius: 8px; background: {p.progress_chunk};
            }}
        """)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_progress(self, value: int):
        self.progress.setValue(value)

    def set_detail(self, text: str):
        self.detail_label.setText(text)
