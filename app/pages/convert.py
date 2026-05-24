"""文件转换页 — 自识别格式"""
import os
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from app.widgets.file_drop import FileDropZone
from app.widgets.progress import ProgressCard
from app.widgets.dropdown import Dropdown
from app.services.converter import (
    convert_file, get_target_formats, is_complex_file,
)
from app.services.dependency import find_libreoffice
from app.utils.i18n import t
from app.utils.file_utils import get_extension, format_size, get_file_size, get_default_output_dir
from app.utils.theme import theme
from app.utils.logger import get_logger

logger = get_logger("convert_page")


class ConvertWorker(QThread):
    finished = Signal(bool, str, str)

    def __init__(self, input_path: str, output_path: str, kwargs: dict, parent=None):
        super().__init__(parent)
        self._input = input_path
        self._output = output_path
        self._kwargs = kwargs
        self._cancel_event = threading.Event()
        self._kwargs["cancel_event"] = self._cancel_event

    def stop(self):
        self._cancel_event.set()

    def run(self):
        try:
            ok, err = convert_file(self._input, self._output, **self._kwargs)
        except Exception as e:
            ok, err = False, str(e)
            logger.exception("转换异常")
        self.finished.emit(ok, err, self._output)


class ConvertPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._input_file: str | None = None
        self._output_dir: str = self._load_output_dir("Convert")
        self._build_ui()
        theme().changed.connect(self._refresh_style)

    def _build_ui(self):
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(14)

        self._title = QLabel(t("convert", "title"))
        layout.addWidget(self._title)

        self._desc = QLabel(t("convert", "description"))
        layout.addWidget(self._desc)

        # 目标格式
        fmt_layout = QHBoxLayout()
        self._fmt_label = QLabel("目标格式:")
        self._fmt_label.setFixedWidth(70)
        fmt_layout.addWidget(self._fmt_label)

        self.format_combo = Dropdown()
        self.format_combo.setFixedSize(280, 34)
        self.format_combo.setEnabled(False)
        self.format_combo.setPlaceholderText("请先选择文件")
        fmt_layout.addWidget(self.format_combo, 1)
        layout.addLayout(fmt_layout)

        # 拖拽区
        self.drop_zone = FileDropZone(t("convert", "drop_zone"))
        self.drop_zone.file_dropped.connect(self._on_file_selected)
        layout.addWidget(self.drop_zone)

        # 文件信息
        btn_layout = QHBoxLayout()
        self._select_btn = QPushButton(t("convert", "select_file"))
        self._select_btn.clicked.connect(self._browse_file)
        btn_layout.addWidget(self._select_btn)

        self._file_info = QLabel("未选择文件")
        btn_layout.addWidget(self._file_info)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 输出目录
        out_layout = QHBoxLayout()
        self._out_label = QLabel("输出目录:")
        self._out_label.setFixedWidth(70)
        out_layout.addWidget(self._out_label)
        self._out_dir_label = QLabel(self._output_dir)
        out_layout.addWidget(self._out_dir_label, 1)
        self._browse_btn = QPushButton(t("common", "browse"))
        self._browse_btn.clicked.connect(self._browse_output)
        out_layout.addWidget(self._browse_btn)
        self._open_dir_btn = QPushButton("打开")
        self._open_dir_btn.setToolTip("打开输出目录")
        self._open_dir_btn.clicked.connect(lambda: os.startfile(self._output_dir))
        out_layout.addWidget(self._open_dir_btn)
        layout.addLayout(out_layout)

        # 进度
        self.progress_card = ProgressCard()
        self.progress_card.setVisible(False)
        layout.addWidget(self.progress_card)

        layout.addStretch()

        btn_layout2 = QHBoxLayout()
        btn_layout2.addStretch()
        self._start_btn = QPushButton(t("convert", "start_convert"))
        self._start_btn.setFixedHeight(44)
        self._start_btn.setFixedWidth(200)
        self._start_btn.clicked.connect(self._start_convert)
        btn_layout2.addWidget(self._start_btn)
        self._stop_btn = QPushButton("终止")
        self._stop_btn.setFixedHeight(44)
        self._stop_btn.setFixedWidth(80)
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._stop_convert)
        btn_layout2.addWidget(self._stop_btn)
        btn_layout2.addStretch()
        layout.addLayout(btn_layout2)

        self._converting = False
        self._refresh_style("light")

    # ---------- 事件 ----------

    def _on_file_selected(self, path: str):
        self._input_file = path
        ext = get_extension(path)
        size = format_size(get_file_size(path))
        self._file_info.setText(f"{os.path.basename(path)} ({size})")
        self.drop_zone.set_text(f"已选择: {os.path.basename(path)}")

        targets = get_target_formats(ext)
        self.format_combo.clear()
        self.format_combo.setEnabled(True)
        if targets:
            for tgt in targets:
                self.format_combo.addItem(f"{ext} → {tgt}", tgt)
            self.format_combo.setCurrentIndex(0)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if path:
            self._on_file_selected(path)

    def _browse_output(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self._output_dir)
        if dir_path:
            self._output_dir = dir_path
            self._out_dir_label.setText(dir_path)

    def _start_convert(self):
        if self._converting:
            return
        if not self._input_file:
            QMessageBox.warning(self, "提示", "请先选择文件")
            return
        out_ext = self.format_combo.currentData()
        if not out_ext:
            QMessageBox.warning(self, "错误", "请选择目标格式")
            return

        force_libre = False
        if is_complex_file(self._input_file) and not find_libreoffice():
            reply = QMessageBox.question(
                self, "提示", t("convert", "libre_required"),
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                import webbrowser
                webbrowser.open("https://www.libreoffice.org/download/")
                QMessageBox.information(self, "提示", "请安装后重试")
                return
        elif find_libreoffice():
            force_libre = True

        stem = os.path.splitext(os.path.basename(self._input_file))[0]
        output_path = os.path.join(self._output_dir, f"{stem}{out_ext}")

        # 立即显示滚动式进度条
        self._converting = True
        self._start_btn.setEnabled(False)
        self._start_btn.setText("转换中...")
        self._stop_btn.setVisible(True)
        self.progress_card.setVisible(True)
        self.progress_card.set_status("正在转换...")
        self.progress_card.progress.setRange(0, 0)  # 滚动式
        self.progress_card.set_detail("")

        self._worker = ConvertWorker(self._input_file, output_path,
                                     {"force_libre": force_libre})
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _stop_convert(self):
        if hasattr(self, "_worker") and self._worker and self._worker.isRunning():
            self._worker.stop()
            self._stop_btn.setEnabled(False)
            self._stop_btn.setText("终止中...")
            self.progress_card.set_status("正在终止...")

    def _on_done(self, ok: bool, error: str, output_path: str):
        try:
            self._converting = False
            self._start_btn.setEnabled(True)
            self._start_btn.setText("开始转换")
            self._stop_btn.setVisible(False)
            self._stop_btn.setEnabled(True)
            self._stop_btn.setText("终止")
            self.progress_card.progress.setRange(0, 100)
            self.progress_card.progress.setValue(100 if ok else 0)
            if ok:
                self.progress_card.set_status("转换完成")
                self.progress_card.set_detail(f"输出: {os.path.abspath(output_path)}")
            elif error == "用户取消":
                self.progress_card.set_status("已取消")
                self.progress_card.set_detail("")
            else:
                self.progress_card.set_status("转换失败")
                self.progress_card.set_detail(error[:120])
        except Exception:
            pass

    # ---------- 主题 ----------

    @staticmethod
    def _load_output_dir(category: str) -> str:
        from app.utils.config import config
        key = "convert_dir" if category == "Convert" else "compress_dir"
        dir_ = config.get(key)
        if dir_ and os.path.isdir(dir_):
            return dir_
        return get_default_output_dir(category)

    def _refresh_style(self, _):
        p = theme().palette
        self.setStyleSheet(f"background-color: {p.bg_main};")

        # 标题和描述
        self._title.setStyleSheet(
            f"font-size:22px; font-weight:bold; color:{p.text_primary}; border:none;")
        self._desc.setStyleSheet(
            f"font-size:13px; color:{p.text_secondary}; border:none;")

        # 字段标签
        for lbl in (self._fmt_label, self._out_label):
            lbl.setStyleSheet(
                f"font-size:14px; font-weight:bold; color:{p.text_primary}; border:none;")

        # 信息/路径文字
        for lbl in (self._file_info, self._out_dir_label):
            lbl.setStyleSheet(
                f"font-size:13px; color:{p.text_secondary}; border:none;")

        # 普通按钮
        for btn in (self._select_btn, self._browse_btn, self._open_dir_btn):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{p.bg_input}; border:1px solid {p.border_card};
                    border-radius:8px; padding:8px 16px;
                    color:{p.text_primary}; font-size:13px;
                }}
                QPushButton:hover {{ background:{p.bg_hover}; }}
            """)

        # 强调按钮
        self._start_btn.setStyleSheet(f"""
            QPushButton {{
                background:{p.accent}; border:none; border-radius:8px;
                color:{p.accent_text}; font-size:15px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{p.accent_hover}; }}
            QPushButton:disabled {{ background:{p.bg_hover}; color:{p.text_muted}; }}
        """)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{ background:#d63031; border:none; border-radius:8px;
                color:#ffffff; font-size:15px; font-weight:bold; }}
            QPushButton:hover {{ background:#b71c1c; }}
            QPushButton:disabled {{ background:#666; color:#999; }}""")

