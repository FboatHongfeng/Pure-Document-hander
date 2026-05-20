"""文件压缩页"""
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QFrame, QRadioButton,
    QButtonGroup, QSlider, QLineEdit, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal

from app.widgets.file_drop import FileDropZone
from app.widgets.dropdown import Dropdown
from app.services.compressor import (
    compress_file, is_compress_supported, get_compress_options,
)
from app.services.dependency import check_ffmpeg_available
from app.utils.i18n import t
from app.utils.file_utils import get_extension, get_file_size, format_size, get_default_output_dir
from app.utils.theme import theme
from app.utils.logger import get_logger

logger = get_logger("compress_page")

VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"}


class CompressWorker(QThread):
    finished = Signal(bool, str, str)
    progress = Signal(int, str)

    def __init__(self, input_path, output_path, kwargs, parent=None):
        super().__init__(parent)
        self._input = input_path
        self._output = output_path
        self._kwargs = kwargs

    def run(self):
        self._kwargs["progress_cb"] = lambda p, e: self.progress.emit(p, e)
        try:
            ok, err = compress_file(self._input, self._output, **self._kwargs)
        except Exception as e:
            ok, err = False, str(e)
            logger.exception("compress error")
        self.finished.emit(ok, err, self._output)


class CompressPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._input_file = None
        self._output_dir = self._load_output_dir("Compress")
        self._compressing = False
        self._build_ui()
        theme().changed.connect(self._refresh_style)

    def _build_ui(self):
        self.setAutoFillBackground(True)
        l = QVBoxLayout(self)
        l.setContentsMargins(32, 20, 32, 20)
        l.setSpacing(10)

        self._title = QLabel("文件压缩")
        l.addWidget(self._title)
        self._desc = QLabel("支持视频、音频、图片、PDF、PPT 压缩")
        l.addWidget(self._desc)

        self.drop_zone = FileDropZone("拖拽文件到此处压缩")
        self.drop_zone.setMinimumHeight(100)
        self.drop_zone.file_dropped.connect(self._dropped)
        l.addWidget(self.drop_zone)

        r = QHBoxLayout()
        self._browse_btn = QPushButton("选择文件")
        self._browse_btn.clicked.connect(self._browse)
        r.addWidget(self._browse_btn)
        self._file_label = QLabel("未选择文件")
        r.addWidget(self._file_label)
        r.addStretch()
        l.addLayout(r)

        self._params_frame = QFrame()
        self._params_frame.setVisible(False)
        self._pl = QVBoxLayout(self._params_frame)
        self._pl.setContentsMargins(14, 10, 14, 10)
        self._pl.setSpacing(8)
        l.addWidget(self._params_frame)

        self._prog = QFrame()
        self._prog.setFixedHeight(82)
        pl2 = QVBoxLayout(self._prog)
        pl2.setContentsMargins(0, 4, 0, 4)
        self._prog_status = QLabel("")
        self._prog_status.setAlignment(Qt.AlignCenter)
        pl2.addWidget(self._prog_status)
        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(0)
        self._prog_bar.setFixedHeight(8)
        self._prog_bar.setTextVisible(False)
        pl2.addWidget(self._prog_bar)
        self._prog_detail = QLabel("")
        self._prog_detail.setAlignment(Qt.AlignCenter)
        pl2.addWidget(self._prog_detail)
        l.addWidget(self._prog)

        r2 = QHBoxLayout()
        self._start_btn = QPushButton("开始压缩")
        self._start_btn.setFixedHeight(44)
        self._start_btn.setFixedWidth(200)
        self._start_btn.clicked.connect(self._start)
        r2.addStretch()
        r2.addWidget(self._start_btn)
        r2.addStretch()
        l.addLayout(r2)
        l.addStretch()

        self._refresh_style("light")

    # ── file ──
    def _dropped(self, path):
        self._set(path)
        self.drop_zone.set_text(f"已选择: {os.path.basename(path)}")

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if p:
            self._set(p)
            self.drop_zone.set_text(f"已选择: {os.path.basename(p)}")

    def _set(self, path):
        self._input_file = path
        ext = get_extension(path)
        sz = get_file_size(path)
        self._file_label.setText(f"{os.path.basename(path)}  ({format_size(sz)})")
        self._build_params(ext, sz)

    # ── params ──
    def _build_params(self, ext, orig_size):
        while self._pl.count():
            it = self._pl.takeAt(0)
            if it.widget(): it.widget().deleteLater()

        self._plabels = []
        opts = get_compress_options(ext)
        if not any(opts.values()):
            self._params_frame.setVisible(False)
            return
        self._params_frame.setVisible(True)
        p = theme().palette

        def lbl(t, bold=False):
            w = QLabel(t)
            fs = 14 if bold else 13
            fw = "bold" if bold else "normal"
            w.setStyleSheet(f"font-size:{fs}px; font-weight:{fw}; color:{p.text_primary}; border:none;")
            w.setProperty("pfs", fs)
            w.setProperty("pfw", fw)
            self._plabels.append(w)
            return w

        if opts.get("mode"):
            self._pl.addWidget(lbl("压缩模式", True))
            self._mg = QButtonGroup(self)
            for k, lb in [("normal", "常规压缩"), ("deep", "深度融合压缩")]:
                rb = QRadioButton(lb)
                rb.setStyleSheet(f"font-size:13px; color:{p.text_primary};")
                self._mg.addButton(rb)
                self._pl.addWidget(rb)
            self._mg.buttons()[1].setChecked(True)
            tip = QLabel("深度融合：合并为整体去除冗余，更高压缩率")
            tip.setStyleSheet(f"font-size:12px; color:{p.text_secondary}; border:none;")
            tip.setWordWrap(True)
            self._plabels.append(tip)
            self._pl.addWidget(tip)

        if opts.get("level"):
            row = QHBoxLayout()
            row.addWidget(lbl("压缩级别:", True))
            row.addSpacing(8)
            self._lc = Dropdown()
            self._lc.setFixedSize(220, 34)
            if ext == ".pdf":
                self._lc.addItem("无损 (100%保真)", "lossless")
                self._lc.addItem("常规", "normal")
                self._lc.addItem("深度", "deep")
            else:
                self._lc.addItem("轻度", "light")
                self._lc.addItem("中度", "medium")
                self._lc.addItem("重度", "heavy")
            self._lc.addItem("自定义大小", "custom")
            self._lc.setCurrentIndex(1)
            self._lc.currentIndexChanged.connect(self._on_lvl)
            row.addWidget(self._lc)
            row.addStretch()
            self._pl.addLayout(row)

            self._cr = QWidget()
            cr2 = QHBoxLayout(self._cr)
            cr2.setContentsMargins(0, 2, 0, 0)
            t1 = QLabel("目标:")
            t1.setProperty("pfs", 13); t1.setProperty("pfw", "normal")
            t1.setStyleSheet(f"font-size:13px; color:{p.text_primary}; border:none;")
            self._plabels.append(t1)
            cr2.addWidget(t1)
            self._ti = QLineEdit()
            self._ti.setPlaceholderText("MB")
            self._ti.setFixedWidth(80)
            self._ti.setStyleSheet(f"""
                QLineEdit {{ background:{p.bg_input}; border:1px solid {p.border_card};
                    border-radius:6px; padding:4px 8px; color:{p.text_primary}; font-size:13px; }}""")
            cr2.addWidget(self._ti)
            t2 = QLabel("MB")
            t2.setProperty("pfs", 13); t2.setProperty("pfw", "normal")
            t2.setStyleSheet(f"font-size:13px; color:{p.text_primary}; border:none;")
            self._plabels.append(t2)
            cr2.addWidget(t2)
            cr2.addStretch()
            self._cr.setVisible(False)
            self._pl.addWidget(self._cr)

        if opts.get("strategy"):
            self._pl.addWidget(lbl("压缩策略", True))
            self._sg = QButtonGroup(self)
            for k, lb in [("quality_first", "画质优先（压缩音频）"),
                          ("balanced", "均衡"),
                          ("size_first", "体积优先（压缩画质）")]:
                rb = QRadioButton(lb)
                rb.setStyleSheet(f"font-size:13px; color:{p.text_primary};")
                self._sg.addButton(rb)
                self._pl.addWidget(rb)
            self._sg.buttons()[1].setChecked(True)

        if opts.get("quality"):
            self._pl.addWidget(lbl("压缩质量", True))
            qr = QHBoxLayout()
            self._qs = QSlider(Qt.Horizontal)
            self._qs.setRange(10, 95)
            self._qs.setValue(70)
            qr.addWidget(self._qs)
            self._ql = QLabel("70%")
            self._ql.setStyleSheet(f"color:{p.text_primary}; border:none; font-size:14px;")
            self._qs.valueChanged.connect(lambda v: self._ql.setText(f"{v}%"))
            qr.addWidget(self._ql)
            self._pl.addLayout(qr)

        if ext in VIDEO_EXTS:
            idx = self._lc.findData("custom")
            if idx >= 0:
                self._lc.setCurrentIndex(idx)

    def _on_lvl(self, idx):
        show = self._lc.currentData() == "custom"
        self._cr.setVisible(show)
        if show and self._input_file:
            sz = get_file_size(self._input_file)
            self._ti.setText(str(max(1, int(sz / 1024 / 1024 / 8))))

    # ── run ──
    def _start(self):
        if self._compressing or not self._input_file:
            return
        ext = get_extension(self._input_file)
        if not is_compress_supported(ext):
            QMessageBox.warning(self, "错误", f"不支持压缩: {ext}")
            return
        if ext in VIDEO_EXTS or ext in AUDIO_EXTS:
            if not check_ffmpeg_available():
                QMessageBox.critical(self, "错误", "FFmpeg 未安装")
                return

        kw = {}
        opts = get_compress_options(ext)
        if opts.get("mode") and hasattr(self, "_mg"):
            btns = self._mg.buttons()
            kw["mode"] = "deep" if btns[1].isChecked() else "normal"
        if opts.get("strategy") and hasattr(self, "_sg"):
            btns = self._sg.buttons()
            i = btns.index(self._sg.checkedButton())
            kw["strategy"] = ["quality_first", "balanced", "size_first"][i]
        if opts.get("level"):
            kw["level"] = self._lc.currentData()
            if kw["level"] == "custom":
                try:
                    mb = float(self._ti.text().strip())
                    tgt = int(mb * 1024 * 1024)
                except (ValueError, AttributeError):
                    QMessageBox.warning(self, "提示", "请输入有效目标大小（MB）")
                    return
                orig = get_file_size(self._input_file)
                ratio = orig / max(tgt, 1)
                if ratio > 100:
                    r = QMessageBox.question(self, "压缩比过大",
                        f"{format_size(orig)} -> {format_size(tgt)} ({ratio:.0f}:1)，继续？",
                        QMessageBox.Yes | QMessageBox.No)
                    if r != QMessageBox.Yes: return
                elif ratio > 20:
                    QMessageBox.warning(self, "提示", f"压缩比 {ratio:.0f}:1")
                kw["target_size"] = tgt
        if opts.get("quality"):
            kw["quality"] = self._qs.value()

        stem = os.path.splitext(os.path.basename(self._input_file))[0]
        out_ext = ext
        if kw.get("mode") == "deep" and ext in (".pptx", ".ppt"):
            out_ext = ".pdf"
        if ext in (".png", ".bmp", ".webp"):
            out_ext = ".jpg"
        out = os.path.join(self._output_dir, f"{stem}_compressed{out_ext}")

        self._compressing = True
        self._start_btn.setEnabled(False)
        self._start_btn.setText("压缩中...")
        self._prog_status.setText("正在压缩...")
        self._prog_bar.setRange(0, 0)
        self._prog_bar.setValue(0)
        self._prog_detail.setText("")

        self._w = CompressWorker(self._input_file, out, kw)
        self._w.progress.connect(self._on_prog)
        self._w.finished.connect(self._on_done)
        self._w.start()

    def _on_prog(self, pct, eta):
        if self._prog_bar.maximum() == 0:
            self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(pct)
        self._prog_detail.setText(f"预计剩余: {eta}")

    def _on_done(self, ok, error, out):
        try:
            self._compressing = False
            self._start_btn.setEnabled(True)
            self._start_btn.setText("开始压缩")
            self._prog_bar.setRange(0, 100)
            self._prog_bar.setValue(100 if ok else 0)
            if ok:
                o = format_size(get_file_size(self._input_file))
                n = format_size(get_file_size(out))
                self._prog_status.setText("压缩完成")
                self._prog_detail.setText(f"{o} -> {n}\n输出: {os.path.abspath(out)}")
            else:
                self._prog_status.setText("压缩失败")
                self._prog_detail.setText(error[:120])
        except Exception:
            pass

    @staticmethod
    def _load_output_dir(category):
        import json
        try:
            p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "resources", "user_settings.json")
            if os.path.exists(p):
                with open(p) as f:
                    s = json.load(f)
                key = "convert_dir" if category == "Convert" else "compress_dir"
                if key in s and os.path.isdir(s[key]):
                    return s[key]
        except Exception:
            pass
        return get_default_output_dir(category)

    # ── theme ──
    def _refresh_style(self, _):
        p = theme().palette
        self.setStyleSheet(f"background-color: {p.bg_main};")
        self._title.setStyleSheet(f"font-size:22px; font-weight:bold; color:{p.text_primary}; border:none;")
        self._desc.setStyleSheet(f"font-size:13px; color:{p.text_secondary}; border:none;")
        self._file_label.setStyleSheet(f"font-size:13px; color:{p.text_secondary}; border:none;")

        self._browse_btn.setStyleSheet(f"""
            QPushButton {{ background:{p.bg_input}; border:1px solid {p.border_card};
                border-radius:8px; padding:8px 16px; color:{p.text_primary}; font-size:13px; }}
            QPushButton:hover {{ background:{p.bg_hover}; }}""")
        self._start_btn.setStyleSheet(f"""
            QPushButton {{ background:{p.accent}; border:none; border-radius:8px;
                color:{p.accent_text}; font-size:15px; font-weight:bold; }}
            QPushButton:hover {{ background:{p.accent_hover}; }}
            QPushButton:disabled {{ background:{p.bg_hover}; color:{p.text_muted}; }}""")

        self._params_frame.setStyleSheet(
            f"QFrame {{ background:{p.bg_card}; border:1px solid {p.border_card}; border-radius:12px; }}")
        self._prog.setStyleSheet(
            f"QFrame {{ background:{p.bg_card}; border:1px solid {p.border_card}; border-radius:8px; }}")
        self._prog_status.setStyleSheet(f"font-size:14px; font-weight:bold; color:{p.text_primary}; border:none;")
        self._prog_detail.setStyleSheet(f"font-size:13px; color:{p.text_secondary}; border:none;")
        self._prog_bar.setStyleSheet(f"""
            QProgressBar {{ border:none; border-radius:8px; background:{p.progress_bg}; }}
            QProgressBar::chunk {{ border-radius:8px; background:{p.accent}; }}""")

        for lbl in getattr(self, "_plabels", []):
            fs = lbl.property("pfs") or 13
            fw = lbl.property("pfw") or "normal"
            lbl.setStyleSheet(f"font-size:{fs}px; font-weight:{fw}; color:{p.text_primary}; border:none;")
        for rb in self._params_frame.findChildren(QRadioButton):
            rb.setStyleSheet(f"font-size:13px; color:{p.text_primary};")
        if hasattr(self, "_ti"):
            self._ti.setStyleSheet(f"""
                QLineEdit {{ background:{p.bg_input}; border:1px solid {p.border_card};
                    border-radius:6px; padding:4px 8px; color:{p.text_primary}; font-size:13px; }}""")

        # 下拉菜单悬停样式
        combo_qss = f"""
            QComboBox {{
                background:{p.bg_card}; border:1px solid {p.border_card};
                border-radius:8px; padding:6px 12px;
                color:{p.text_primary}; font-size:13px;
                min-height:32px; max-height:32px;
            }}
            QComboBox::drop-down {{ border:none; width:0px; }}
            QComboBox::down-arrow {{ image:none; width:0px; height:0px; }}
            QComboBox QAbstractItemView {{
                background:{p.bg_card}; color:{p.text_primary};
                selection-background-color:{p.accent};
                selection-color:{p.accent_text};
                border:1px solid {p.border_card}; border-radius:8px;
                padding:4px; outline:none;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background:{p.accent}; color:{p.accent_text};
            }}
        """
        for cb in self._params_frame.findChildren(QComboBox):
            cb.setStyleSheet(combo_qss)
