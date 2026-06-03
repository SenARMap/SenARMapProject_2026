#!/usr/bin/env python3
"""
SVG Coordinate Picker (PyQt5)
------------------------------
SVGファイルを画面に表示し、クリックした位置のSVG座標(x, y)を取得する。
クリックするたびに全点がクリップボードにタブ区切りでコピーされ、
スプレッドシートに2列でペースト可能。

Usage:
  python svg_picker.py [file.svg]
  python svg_picker.py             # ファイルダイアログで選択

依存:
  pip install PyQt5
"""

import sys
from pathlib import Path

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
        QWidget, QVBoxLayout, QPushButton, QListWidget,
        QLabel, QFileDialog, QSplitter,
    )
    from PyQt5.QtSvg import QGraphicsSvgItem
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QPainter
except ImportError:
    print("PyQt5が必要です:  pip install PyQt5")
    sys.exit(1)


PIN_R = 6
PIN_FILL    = QColor("#ff3333")
PIN_OUTLINE = QColor("white")
PIN_TEXT    = QColor("#cc0000")


# ---------------------------------------------------------------------------
# カスタム QGraphicsView — ズーム・パン・クリック
# ---------------------------------------------------------------------------

class SVGView(QGraphicsView):

    def __init__(self, scene: QGraphicsScene, on_click):
        super().__init__(scene)
        self._on_click = on_click
        self._press_pos = None

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor("#e8e8e8")))

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press_pos is not None:
            # 5px以内の移動ならクリック扱い（ドラッグと区別）
            if (event.pos() - self._press_pos).manhattanLength() < 5:
                sp = self.mapToScene(event.pos())
                self._on_click(sp.x(), sp.y())
            self._press_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        k = event.key()
        if k in (Qt.Key_Plus, Qt.Key_Equal):
            self.scale(1.25, 1.25)
        elif k == Qt.Key_Minus:
            self.scale(0.8, 0.8)
        elif k == Qt.Key_0:
            self.fit_all()
        else:
            super().keyPressEvent(event)

    def fit_all(self):
        rect = self.scene().itemsBoundingRect()
        if not rect.isEmpty():
            self.fitInView(rect, Qt.KeepAspectRatio)


# ---------------------------------------------------------------------------
# メインウィンドウ
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(self, svg_path: str):
        super().__init__()
        self.svg_path = svg_path
        self.points: list = []   # (svg_x, svg_y)

        self.setWindowTitle(f"SVG Coord Picker — {Path(svg_path).name}")
        self.resize(1280, 820)

        self._build_ui()
        self._load_svg()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        # 左: SVGビュー
        self._scene = QGraphicsScene()
        self._view = SVGView(self._scene, self._on_click)
        splitter.addWidget(self._view)

        # 右: サイドパネル
        side = QWidget()
        side.setFixedWidth(240)
        side.setStyleSheet("background:#f5f5f5;")
        vl = QVBoxLayout(side)
        vl.setContentsMargins(8, 12, 8, 8)
        vl.setSpacing(4)

        vl.addWidget(QLabel("<b>取得座標一覧</b>"))

        self._list = QListWidget()
        self._list.setFont(QFont("Courier", 11))
        vl.addWidget(self._list, 1)

        for label, fn, color in [
            ("クリップボードにコピー (全点)", self._copy_all,       "#4CAF50"),
            ("選択した点を削除",              self._delete_selected, "#757575"),
            ("全消去",                        self._clear_all,       "#e53935"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            btn.setStyleSheet(
                f"QPushButton{{background:{color};color:white;"
                f"padding:6px;border:none;border-radius:3px;}}"
                f"QPushButton:hover{{background:{color};opacity:0.9;}}"
            )
            vl.addWidget(btn)

        note = QLabel("ズーム: スクロール / + −\n全体表示: キー 0\nパン: 左ドラッグ")
        note.setStyleSheet("color:#888;font-size:10px;")
        vl.addWidget(note)

        splitter.addWidget(side)
        splitter.setSizes([1040, 240])

        self.statusBar().showMessage("SVGをクリックして座標を取得")

    def _load_svg(self):
        self._svg_item = QGraphicsSvgItem(self.svg_path)
        self._scene.addItem(self._svg_item)
        self._scene.setSceneRect(self._svg_item.boundingRect())
        # ウィンドウ表示後に全体フィット
        QTimer.singleShot(100, self._view.fit_all)

    # ------------------------------------------------------------------
    # ピン描画
    # ------------------------------------------------------------------

    def _draw_pin(self, sx: float, sy: float, n: int):
        r = PIN_R
        pen_w = QPen(PIN_OUTLINE, 2)
        pen_r = QPen(PIN_FILL, 2)

        line = self._scene.addLine(sx, sy - r - 8, sx, sy - r, pen_r)
        line.setZValue(10)

        circle = self._scene.addEllipse(sx - r, sy - r, r * 2, r * 2,
                                        pen_w, QBrush(PIN_FILL))
        circle.setZValue(10)

        text = self._scene.addSimpleText(str(n))
        text.setPos(sx + r + 2, sy - 8)
        text.setBrush(QBrush(PIN_TEXT))
        text.setFont(QFont("Helvetica", 8, QFont.Bold))
        text.setZValue(10)

    # ------------------------------------------------------------------
    # クリック
    # ------------------------------------------------------------------

    def _on_click(self, sx: float, sy: float):
        # SVG範囲外は無視
        if not self._svg_item.boundingRect().contains(sx, sy):
            return

        self.points.append((sx, sy))
        n = len(self.points)
        self._draw_pin(sx, sy, n)

        self._list.addItem(f"{n:>3}: {sx:>10.3f}, {sy:>10.3f}")
        self._list.scrollToBottom()
        self._copy_all()
        self.statusBar().showMessage(
            f"点 {n} 追加 → クリップボードにコピー済み  (x={sx:.3f}, y={sy:.3f})"
        )

    # ------------------------------------------------------------------
    # クリップボード (タブ区切り → スプレッドシートに2列ペースト)
    # ------------------------------------------------------------------

    def _copy_all(self):
        if not self.points:
            return
        text = "\n".join(f"{x:.3f}\t{y:.3f}" for x, y in self.points)
        QApplication.clipboard().setText(text)

    # ------------------------------------------------------------------
    # リスト操作
    # ------------------------------------------------------------------

    def _delete_selected(self):
        row = self._list.currentRow()
        if row < 0:
            return
        self.points.pop(row)
        self._redraw_all()
        self._rebuild_list()
        self._copy_all()

    def _clear_all(self):
        self.points.clear()
        self._redraw_all()
        self._list.clear()
        QApplication.clipboard().clear()
        self.statusBar().showMessage("全消去しました")

    def _redraw_all(self):
        for item in list(self._scene.items()):
            if item is not self._svg_item:
                self._scene.removeItem(item)
        for i, (sx, sy) in enumerate(self.points, 1):
            self._draw_pin(sx, sy, i)

    def _rebuild_list(self):
        self._list.clear()
        for i, (x, y) in enumerate(self.points, 1):
            self._list.addItem(f"{i:>3}: {x:>10.3f}, {y:>10.3f}")


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)

    if len(sys.argv) > 1:
        svg_path = sys.argv[1]
    else:
        svg_path, _ = QFileDialog.getOpenFileName(
            None, "SVGファイルを選択", "",
            "SVG files (*.svg);;All files (*)"
        )
        if not svg_path:
            sys.exit(0)

    win = MainWindow(svg_path)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
