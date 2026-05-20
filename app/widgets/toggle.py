"""现代滑块开关 — iOS风格 Toggle Switch"""
from PySide6.QtWidgets import QCheckBox, QApplication
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QBrush, QPen


class ToggleSwitch(QCheckBox):
    """iOS风格滑块开关

    用法同 QCheckBox:
        sw = ToggleSwitch()
        sw.toggled.connect(lambda v: print(v))
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 26)
        self._offset = 3

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        checked = self.isChecked()
        w, h = self.width(), self.height()
        r = h / 2

        # 背景
        from app.utils.theme import theme
        if checked:
            bg = QColor(theme().palette.accent)
        else:
            bg = QColor("#c0c4cc") if self._is_light() else QColor("#4a4d55")
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)

        # 滑块
        knob_r = r - 3
        knob_x = w - h + 3 if checked else 3
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(int(knob_x), 3, int(knob_r * 2), int(knob_r * 2))

        p.end()

    def _is_light(self) -> bool:
        from app.utils.theme import theme
        return theme().current == "light"

    def hitButton(self, pos):
        return self.rect().contains(pos)
