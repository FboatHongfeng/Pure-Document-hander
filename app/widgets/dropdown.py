"""自定义下拉选择器"""
from PySide6.QtWidgets import (
    QWidget, QPushButton, QListWidget, QListWidgetItem, QFrame,
    QVBoxLayout, QApplication,
)
from PySide6.QtCore import Qt, Signal, QPoint
from app.utils.theme import theme


class Dropdown(QWidget):
    currentIndexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._idx = -1
        self._popup = None

        self._btn = QPushButton(self)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self._toggle)
        self._btn.setGeometry(0, 0, self.width(), self.height())

        self._restyle()
        theme().changed.connect(self._restyle)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._btn.setGeometry(0, 0, self.width(), self.height())

    # ── 公共接口 ──
    def addItem(self, text, data=None):
        self._items.append((text, data))
        if len(self._items) == 1:
            self._idx = 0
            self._btn.setText(text)

    def setCurrentIndex(self, i):
        if 0 <= i < len(self._items):
            self._idx = i
            self._btn.setText(self._items[i][0])

    def currentIndex(self):  return self._idx
    def currentData(self):   return self._items[self._idx][1] if 0 <= self._idx < len(self._items) else None
    def currentText(self):   return self._items[self._idx][0] if 0 <= self._idx < len(self._items) else ""
    def findData(self, data):
        for i, (_, d) in enumerate(self._items):
            if d == data: return i
        return -1
    def clear(self):
        self._items.clear(); self._idx = -1; self._btn.setText("")
    def setEnabled(self, en): self._btn.setEnabled(en)
    def setPlaceholderText(self, t):
        if not self._items: self._btn.setText(t)

    # ── 弹出 ──
    def _toggle(self):
        if self._popup and self._popup.isVisible():
            self._popup.close()
            self._popup = None
        else:
            self._show_popup()

    def _show_popup(self):
        if not self._items: return
        self._popup = QFrame(self.window(),
                             Qt.Popup | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self._popup.setAttribute(Qt.WA_ShowWithoutActivating)
        l = QVBoxLayout(self._popup)
        l.setContentsMargins(0, 0, 0, 0)

        lst = QListWidget()
        lst.setCursor(Qt.PointingHandCursor)
        lst.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for i, (t, _) in enumerate(self._items):
            lst.addItem(QListWidgetItem(t))
        lst.setCurrentRow(max(0, self._idx))
        lst.setMinimumWidth(self.width())
        n = min(len(self._items), 8)
        lst.setFixedHeight(n * 30 + 6)
        lst.itemClicked.connect(lambda item: self._pick(lst.row(item)))
        l.addWidget(lst)
        self._style_popup(lst)

        # 定位：按钮正下方
        pos = self._btn.mapToGlobal(QPoint(0, self._btn.height()))
        screen = QApplication.screenAt(pos)
        if screen:
            sg = screen.availableGeometry()
            x = max(sg.left(), min(pos.x(), sg.right() - lst.width()))
            y = pos.y()
            if y + lst.height() > sg.bottom():
                y = pos.y() - self._btn.height() - lst.height()
            self._popup.move(x, y)
        self._popup.show()

    def _pick(self, i):
        self.setCurrentIndex(i)
        self.currentIndexChanged.emit(i)
        if self._popup:
            self._popup.close()
            self._popup = None

    def _style_popup(self, lst):
        p = theme().palette
        self._popup.setStyleSheet(
            f"QFrame {{ background:{p.bg_card}; border:1px solid {p.border_card}; border-radius:8px; }}")
        lst.setStyleSheet(f"""
            QListWidget {{ background:transparent; border:none; color:{p.text_primary}; font-size:13px; outline:none; padding:4px; }}
            QListWidget::item {{ padding:6px 14px; border-radius:6px; }}
            QListWidget::item:hover {{ background:{p.accent}; color:{p.accent_text}; }}
            QListWidget::item:selected {{ background:{p.accent}; color:{p.accent_text}; }}
        """)

    def _restyle(self, _=None):
        p = theme().palette
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background:{p.bg_card}; border:1px solid {p.border_card};
                border-radius:8px; padding:6px 14px;
                color:{p.text_primary}; font-size:13px; text-align:left;
            }}
            QPushButton:hover {{ border-color:{p.accent}; }}
        """)
        self._btn.setFixedHeight(34)
