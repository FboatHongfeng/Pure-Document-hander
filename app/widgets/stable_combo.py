"""QComboBox — 悬停不消失 + 三角箭头"""
from PySide6.QtWidgets import QComboBox
from PySide6.QtGui import QPainter, QColor, QPolygon
from PySide6.QtCore import Qt, QPoint


class StableComboBox(QComboBox):

    def showPopup(self):
        self.view().setMinimumWidth(self.width())
        super().showPopup()
        self.update()

    def hidePopup(self):
        super().hidePopup()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w - 14, h // 2
        s = 4
        if self.view().isVisible():
            c = QColor("#6384ff")
            pts = [QPoint(cx - s, cy + 1), QPoint(cx + s, cy + 1), QPoint(cx, cy - s)]
        else:
            c = QColor("#888888")
            pts = [QPoint(cx - s, cy - 1), QPoint(cx + s, cy - 1), QPoint(cx, cy + s)]
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPolygon(pts)
        p.end()
