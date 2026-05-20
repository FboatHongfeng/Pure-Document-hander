"""固定位置的 QComboBox — 下拉菜单始终在控件正下方"""
from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import QPoint, Qt


class FixedComboBox(QComboBox):
    """下拉菜单始终向下打开，不随空间不足而上翻"""

    def showPopup(self):
        view = self.view()
        view.setMinimumWidth(self.width())
        # 设置popup始终在下方
        view.setProperty("_q_popupDirection", Qt.BottomEdge)
        super().showPopup()
        # 强制调整位置到控件正下方
        global_pos = self.mapToGlobal(QPoint(0, self.height()))
        view.move(global_pos)
