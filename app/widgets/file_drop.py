"""拖拽区域 — 主题感知"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from app.utils.theme import theme


class FileDropZone(QFrame):

    file_dropped = Signal(str)

    def __init__(self, placeholder: str = "拖拽文件到此处\n或点击选择文件", parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel(placeholder)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("font-size: 14px; border: none;")
        layout.addWidget(self.label)

        self._placeholder = placeholder
        self._apply_style()
        theme().changed.connect(lambda _: self._apply_style())

    def _apply_style(self):
        p = theme().palette
        self._base_style = f"""
            border: 2px dashed {p.border_drop};
            border-radius: 12px;
            background-color: {p.bg_drop};
        """
        self._hover_style = f"""
            border: 2px solid {p.accent};
            border-radius: 12px;
            background-color: rgba(99,132,255,0.12);
        """
        self.setStyleSheet(self._base_style)
        self.label.setStyleSheet(f"font-size: 14px; color: {p.text_muted}; border: none;")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._hover_style)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._base_style)

    def dropEvent(self, event: QDropEvent):
        self.dragLeaveEvent(None)
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path:
                    self.file_dropped.emit(path)
                    self.label.setText(f"已选择: {path.split('/')[-1][:50]}")
                    break

    def set_text(self, text: str):
        self.label.setText(text)

    def reset(self):
        self.label.setText(self._placeholder)
