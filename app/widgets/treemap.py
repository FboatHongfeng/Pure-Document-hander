"""Squarified Treemap — SpaceSniffer 风格磁盘可视化"""
import os
import math
import hashlib
from dataclasses import dataclass, field

from PySide6.QtWidgets import QWidget, QToolTip
from app.utils.theme import theme
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QFontMetrics, QMouseEvent,
)


@dataclass
class TreeNode:
    name: str
    path: str
    size: int
    children: list["TreeNode"] = field(default_factory=list)
    is_dir: bool = True

    @property
    def display_size(self) -> str:
        return _human_size(self.size)


def _human_size(b: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"


# ---------- Squarified Treemap 算法 ----------

def _worst_aspect(rows: list[float], w: float, h: float) -> float:
    """计算当前行最差宽高比"""
    if w <= 0 or h <= 0:
        return 1e9
    s = sum(rows)
    if s <= 0:
        return 1e9
    ratios = [(w * w * r) / (h * h * s) for r in rows]
    return max(ratios + [1.0 / r for r in ratios if r > 0] if ratios else [1e9])


def _squarify(items: list[tuple], bounds: QRectF, results: list,
              depth: int = 0):
    if not items or depth > 50:
        return
    if len(items) == 1:
        results.append((bounds, items[0][1]))
        return

    total = sum(s for s, _ in items)
    if total <= 0:
        return

    w, h = bounds.width(), bounds.height()
    if w <= 0 or h <= 0:
        return

    vertical = w >= h

    row: list[float] = []
    row_sum = 0.0
    remaining = float(total)

    for i, (size, data) in enumerate(items):
        row.append(size)
        row_sum += size
        remaining -= size

        # 最后一个元素：布局当前行
        if i == len(items) - 1:
            _layout_row(row, list(items[i + 1 - len(row):]), bounds, results,
                        row_sum, vertical)
            return

        # 是否应该切行
        if len(row) >= 2:
            cur = _worst_aspect(row, bounds.width(), bounds.height())
            nxt = _worst_aspect(row + [items[i + 1][0]],
                                bounds.width(), bounds.height())
            if cur < nxt:       # 切行
                row_sum -= size
                remaining += size
                row.pop()

                used_ratio = row_sum / (row_sum + remaining)
                if vertical:
                    row_bounds = QRectF(bounds.x(), bounds.y(),
                                        bounds.width() * used_ratio, bounds.height())
                    rest_bounds = QRectF(bounds.x() + bounds.width() * used_ratio,
                                         bounds.y(),
                                         bounds.width() * (1.0 - used_ratio), bounds.height())
                else:
                    row_bounds = QRectF(bounds.x(), bounds.y(),
                                        bounds.width(), bounds.height() * used_ratio)
                    rest_bounds = QRectF(bounds.x(), bounds.y() + bounds.height() * used_ratio,
                                         bounds.width(), bounds.height() * (1.0 - used_ratio))

                _layout_row(row, list(items[i - len(row):i]), row_bounds, results,
                            row_sum, vertical)
                _squarify(list(items[i:]), rest_bounds, results, depth + 1)
                return


def _layout_row(sizes, items_data, bounds, results, row_sum, vertical):
    """布局一行"""
    if not sizes:
        return
    if vertical:
        x = bounds.x()
        for sz, (_, d) in zip(sizes, items_data):
            rw = bounds.width() * (sz / row_sum) if row_sum > 0 else bounds.width() / len(sizes)
            results.append((QRectF(x, bounds.y(), max(rw, 4), bounds.height()), d))
            x += rw
    else:
        y = bounds.y()
        for sz, (_, d) in zip(sizes, items_data):
            rh = bounds.height() * (sz / row_sum) if row_sum > 0 else bounds.height() / len(sizes)
            results.append((QRectF(bounds.x(), y, bounds.width(), max(rh, 4)), d))
            y += rh


# ---------- 颜色方案 ----------

DEPTH_COLORS = [
    QColor("#4a6cf7"), QColor("#6c5ce7"), QColor("#00b894"),
    QColor("#e17055"), QColor("#fdcb6e"), QColor("#0984e3"),
    QColor("#a29bfe"), QColor("#55efc4"), QColor("#ff7675"),
    QColor("#fab1a0"), QColor("#74b9ff"), QColor("#81ecec"),
    QColor("#636e72"), QColor("#b2bec3"),
]


def _color_for_node(node: TreeNode, depth: int = 0) -> QColor:
    c = DEPTH_COLORS[depth % len(DEPTH_COLORS)]
    h = c.hue()
    s = c.saturation()
    v = c.value()
    hsh = int(hashlib.md5(node.name.encode()).hexdigest()[:4], 16)
    h = (h + (hsh % 30) - 15) % 360
    v = max(120, min(255, v + (hsh % 40) - 20))
    return QColor.fromHsv(h, s, v)


# ---------- Treemap Widget ----------

class TreemapWidget(QWidget):
    """Squarified treemap，支持点击钻入"""

    node_clicked = Signal(object)
    path_changed = Signal(str)
    drill_needed = Signal(str)      # 请求深度扫描指定路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root: TreeNode | None = None
        self._current: TreeNode | None = None
        self._rects: list[tuple[QRectF, TreeNode, QColor]] = []
        self._hovered: tuple[QRectF, TreeNode] | None = None
        self._breadcrumb: list[TreeNode] = []
        self.setMouseTracking(True)
        self.setMinimumSize(400, 280)

    def set_data(self, root: TreeNode):
        self._root = root
        self._current = root
        self._breadcrumb = [root]
        self._layout()
        self.update()

    MIN_W, MIN_H = 36, 24
    MAX_RATIO = 0.70       # 单个块最多占70%面积

    def _layout(self):
        self._rects = []
        if not self._current or not self._current.children:
            return

        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        items = [(c.size, c) for c in self._current.children if c.size > 0]
        if not items:
            return

        total = sum(s for s, _ in items)
        if total <= 0:
            return

        # 小项聚合：< 0.5% 的合并为"其他"
        main, others = [], []
        for sz, node in items:
            if sz / total < 0.005:
                others.append((sz, node))
            else:
                main.append((sz, node))
        if len(others) > 1 and main:
            other_size = sum(s for s, _ in others)
            other_node = TreeNode(
                name=f"其他 ({len(others)}项)",
                path="", size=other_size, is_dir=False)
            main.append((other_size, other_node))
        elif others:
            main.extend(others)

        # 最大项封顶（迭代精确求解）
        total2 = sum(s for s, _ in main)
        sizes = [s for s, _ in main]
        sizes.sort(reverse=True)
        n = len(sizes)
        capped_sizes = sizes[:]
        for k in range(1, n + 1):
            small_sum = sum(sizes[k:])
            x = (self.MAX_RATIO * small_sum) / (1.0 - self.MAX_RATIO * k) if (1.0 - self.MAX_RATIO * k) > 0 else float('inf')
            # 检查x是否落在合理范围内：> sizes[k]（如果k<n）且 <= sizes[k-1]
            lower_ok = x >= sizes[k] if k < n else True
            upper_ok = x <= sizes[k - 1]
            if lower_ok and upper_ok:
                # 找到了正确的k：前k个封顶为x
                capped_sizes = [min(sz, x) for sz in sizes]
                break
        # 用 capped_sizes 重建 main 列表
        main.sort(key=lambda x: x[0], reverse=True)
        capped_main = [(cs, node) for cs, (_, node) in zip(capped_sizes, main)]

        results: list[tuple[QRectF, object]] = []
        margin = 4
        bounds = QRectF(margin, margin, w - 2 * margin, h - 2 * margin)
        _squarify(capped_main, bounds, results)

        for rect, node in results:
            # 确保最小尺寸
            r = QRectF(rect)
            if r.width() < self.MIN_W:
                r.setWidth(self.MIN_W)
            if r.height() < self.MIN_H:
                r.setHeight(self.MIN_H)
            color = _color_for_node(node, len(self._breadcrumb))
            self._rects.append((r, node, color))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.fillRect(self.rect(), QColor(theme().palette.bg_sidebar))

        if not self._rects:
            p.setPen(QColor(theme().palette.text_muted))
            p.setFont(QFont("Microsoft YaHei", 11))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "点击「扫描全部磁盘」开始分析" if not self._current
                       else "扫描中...")
            p.end()
            return

        for rect, node, color in self._rects:
            is_hovered = (self._hovered and self._hovered[1] is node)

            c = color.lighter(115) if is_hovered else color

            # 绘制方块
            p.setBrush(c)
            border = c.darker(115)
            p.setPen(QPen(border, 1))
            p.drawRoundedRect(rect, 2, 2)

            # 标签
            if rect.width() < 20 or rect.height() < 14:
                continue

            text_color = QColor("#ffffff") if c.value() < 160 else QColor("#1a1c22")
            p.setPen(text_color)

            label = node.name
            size_str = node.display_size

            # 根据可用空间选择字体大小
            font_sizes = [11, 9, 7, 6]
            best_fs = 6
            for fs in font_sizes:
                font = QFont("Microsoft YaHei", fs)
                p.setFont(font)
                fm = QFontMetrics(font)
                lw = fm.horizontalAdvance(label)
                if lw < rect.width() - 8:
                    best_fs = fs
                    break

            font = QFont("Microsoft YaHei", best_fs)
            p.setFont(font)
            fm = QFontMetrics(font)

            # 二分查找截断点
            avail_w = rect.width() - 8
            if fm.horizontalAdvance(label) > avail_w:
                lo, hi = 0, len(label)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if fm.horizontalAdvance(label[:mid] + "...") <= avail_w:
                        lo = mid + 1
                    else:
                        hi = mid
                label = label[:max(0, lo - 1)] + "..."

            text_rect = rect.adjusted(4, 3, -4, -3)
            # 标题
            p.drawText(text_rect, Qt.AlignTop | Qt.AlignLeft, label)

            # 大小（如果够高）
            if rect.height() > 28 and best_fs >= 7:
                size_font = QFont("Microsoft YaHei", max(6, best_fs - 2))
                p.setFont(size_font)
                p.setPen(QColor(255, 255, 255, 180)
                         if c.value() < 160 else QColor(0, 0, 0, 140))
                p.drawText(text_rect, Qt.AlignBottom | Qt.AlignRight, size_str)

        p.end()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        self._hovered = None
        for rect, node, _ in self._rects:
            if rect.contains(pos):
                self._hovered = (rect, node)
                self.setCursor(Qt.PointingHandCursor)
                break
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if not self._hovered:
            return
        _, node = self._hovered
        if event.button() == Qt.LeftButton:
            if node.is_dir:
                if node.children:
                    self._current = node
                    self._breadcrumb.append(node)
                    self._layout()
                    self.update()
                    self.path_changed.emit(self._current.path)
                    self.node_clicked.emit(node)
                else:
                    self.drill_needed.emit(node.path)
        elif event.button() == Qt.RightButton:
            if node.path:
                import subprocess
                target = os.path.abspath(node.path)
                if not node.is_dir:
                    subprocess.Popen(['explorer', '/select,' + target])
                else:
                    os.startfile(target)

    def go_up(self):
        if len(self._breadcrumb) > 1:
            self._breadcrumb.pop()
            self._current = self._breadcrumb[-1]
            self._layout()
            self.update()
            self.path_changed.emit(self._current.path)

    def go_to_index(self, idx: int):
        if 0 <= idx < len(self._breadcrumb):
            self._breadcrumb = self._breadcrumb[:idx + 1]
            self._current = self._breadcrumb[-1]
            self._layout()
            self.update()
            self.path_changed.emit(self._current.path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout()
        self.update()
