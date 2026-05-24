"""用爱发电"""
import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from app.utils.i18n import t
from app.utils.theme import theme


class DonatePage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        theme().changed.connect(self._refresh_style)

    def _build_ui(self):
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(24)

        layout.addStretch()

        self._title = QLabel(t("donate", "title"))
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(self._title)

        self._desc = QLabel(t("donate", "description"))
        self._desc.setAlignment(Qt.AlignCenter)
        self._desc.setStyleSheet("font-size: 14px;")
        self._desc.setWordWrap(True)
        layout.addWidget(self._desc)

        layout.addSpacing(16)

        # 两个二维码横排
        qr_row = QHBoxLayout()
        qr_row.addStretch()

        # 收款码
        pay_col = QVBoxLayout()
        pay_frame = QFrame()
        pay_frame.setFixedSize(240, 240)
        pay_inner = QVBoxLayout(pay_frame)
        pay_inner.setAlignment(Qt.AlignCenter)
        self._fill_qr(pay_frame, pay_inner, self._find_qr(), self._placeholder)
        pay_col.addWidget(pay_frame, alignment=Qt.AlignCenter)
        self._pay_hint = QLabel("收款码")
        self._pay_hint.setAlignment(Qt.AlignCenter)
        pay_col.addWidget(self._pay_hint)
        qr_row.addLayout(pay_col)

        qr_row.addSpacing(40)

        # 微信码
        wx_col = QVBoxLayout()
        wx_frame = QFrame()
        wx_frame.setFixedSize(240, 240)
        wx_inner = QVBoxLayout(wx_frame)
        wx_inner.setAlignment(Qt.AlignCenter)
        self._fill_qr(wx_frame, wx_inner, self._find_wechat_qr(), self._wx_placeholder)
        wx_col.addWidget(wx_frame, alignment=Qt.AlignCenter)
        self._wx_hint = QLabel("微信好友")
        self._wx_hint.setAlignment(Qt.AlignCenter)
        self._wx_hint.setStyleSheet("font-size: 12px;")
        wx_col.addWidget(self._wx_hint)
        qr_row.addLayout(wx_col)

        qr_row.addStretch()
        layout.addLayout(qr_row)

        layout.addSpacing(24)

        self._note = QLabel(t("donate", "no_obligation"))
        self._note.setAlignment(Qt.AlignCenter)
        self._note.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._note)

        layout.addSpacing(8)

        self._credit = QLabel("Made by HongFeng")
        self._credit.setAlignment(Qt.AlignCenter)
        self._credit.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._credit)

        layout.addSpacing(12)

        # 协会标识
        assoc_row = QHBoxLayout()
        assoc_row.addStretch()
        self._assoc_icon = QLabel()
        self._assoc_icon.setFixedSize(36, 36)
        self._assoc_icon.setAlignment(Qt.AlignCenter)
        self._assoc_icon.setScaledContents(True)
        icon_path = self._find_assoc_icon()
        if icon_path and os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            if not pix.isNull():
                # 裁剪为圆形
                from PySide6.QtGui import QBitmap, QPainter, QBrush, QColor
                mask = QBitmap(36, 36)
                mask.fill(Qt.GlobalColor.color0)
                painter = QPainter(mask)
                painter.setBrush(QBrush(Qt.GlobalColor.color1))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(0, 0, 36, 36)
                painter.end()
                scaled = pix.scaled(36, 36, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                # 从缩放图中取中心36x36
                cx = max(0, (scaled.width() - 36) // 2)
                cy = max(0, (scaled.height() - 36) // 2)
                cropped = scaled.copy(cx, cy, min(36, scaled.width()), min(36, scaled.height()))
                cropped.setMask(mask)
                self._assoc_icon.setPixmap(cropped)
        assoc_row.addWidget(self._assoc_icon)
        assoc_row.addSpacing(6)
        self._assoc_label = QLabel("成都大学计算机协会开发")
        self._assoc_label.setAlignment(Qt.AlignCenter)
        self._assoc_label.setStyleSheet("font-size: 11px;")
        assoc_row.addWidget(self._assoc_label)
        assoc_row.addStretch()
        layout.addLayout(assoc_row)

        layout.addSpacing(6)

        # GitHub 链接放在最下面
        self._github_label = QLabel()
        self._github_label.setAlignment(Qt.AlignCenter)
        self._github_label.setOpenExternalLinks(True)
        self._github_label.setTextFormat(Qt.RichText)
        layout.addWidget(self._github_label)

        layout.addStretch()

        self._refresh_style("light")

    def _fill_qr(self, frame, layout, path, placeholder_fn):
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                qr_img = QLabel()
                qr_img.setPixmap(scaled)
                qr_img.setAlignment(Qt.AlignCenter)
                qr_img.setStyleSheet("border: none;")
                layout.addWidget(qr_img)
                return
        layout.addWidget(placeholder_fn())

    def _find_qr(self) -> str:
        for name in ("qr_code.png", "qr_code.jpg"):
            p = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))),
                "resources", name)
            if os.path.exists(p):
                return p
        return ""

    def _find_wechat_qr(self) -> str:
        for name in ("wechat_qr.png", "wechat_qr.jpg"):
            p = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))),
                "resources", name)
            if os.path.exists(p):
                return p
        return ""

    def _find_assoc_icon(self) -> str:
        for name in ("assoc_icon.png", "assoc_icon.jpg", "association.png"):
            p = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))),
                "resources", name)
            if os.path.exists(p):
                return p
        return ""

    def _placeholder(self) -> QLabel:
        label = QLabel(t("donate", "qr_placeholder"))
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(
            f"font-size:13px; border:none; color:{theme().palette.text_secondary};")
        label.setWordWrap(True)
        return label

    def _wx_placeholder(self) -> QLabel:
        label = QLabel("微信二维码占位\n(resources/wechat_qr.png)")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(
            f"font-size:12px; border:none; color:{theme().palette.text_secondary};")
        label.setWordWrap(True)
        return label

    def _refresh_style(self, _):
        p = theme().palette
        self.setStyleSheet(f"background-color: {p.bg_main};")
        self._title.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {p.text_primary};")
        self._desc.setStyleSheet(f"font-size: 14px; color: {p.text_secondary};")
        for lbl in (self._pay_hint, self._wx_hint):
            lbl.setStyleSheet(f"font-size: 12px; color: {p.text_secondary};")
        github_url = t("donate", "github_url")
        github_text = t("donate", "github_text")
        self._github_label.setText(
            f'<a href="{github_url}" '
            f'style="color:#c07830; font-size:12px; font-weight:bold; text-decoration:none;">'
            f'{github_text}</a>')
        self._note.setStyleSheet(f"font-size: 12px; color: {p.text_muted};")
        self._credit.setStyleSheet(f"font-size: 11px; color: {p.text_muted};")
        self._assoc_label.setStyleSheet(f"font-size: 11px; color: {p.text_muted};")
