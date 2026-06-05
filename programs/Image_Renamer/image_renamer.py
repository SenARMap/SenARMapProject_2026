#!/usr/bin/env python3
"""画像バッチリネーマー — 左にD&D、右に名前をペーストするだけ"""

import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout,
    QLabel, QTextEdit, QListWidget, QPushButton,
    QAbstractItemView, QListWidgetItem,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QKeySequence, QShortcut

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp',
              '.tiff', '.tif', '.webp', '.heic', '.heif'}


class DropListWidget(QListWidget):
    """画像ファイルのドロップ先リスト"""

    def __init__(self, on_change=None, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._paths: list[str] = []
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    # ── drag & drop ──────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and self._has_images(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        added = False
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path not in self._paths and self._is_image(path):
                self._paths.append(path)
                self.addItem(QListWidgetItem(os.path.basename(path)))
                added = True
        if added:
            event.acceptProposedAction()
            self._notify()

    # ── empty-state hint ─────────────────────────────────────────────

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() == 0:
            p = QPainter(self.viewport())
            p.setPen(QColor("#aaaaaa"))
            p.setFont(QFont("", 12))
            p.drawText(
                self.viewport().rect(),
                Qt.AlignmentFlag.AlignCenter,
                "画像ファイルをここに\nドラッグ＆ドロップ\n\n.jpg .png .gif .bmp .tiff .webp .heic",
            )

    # ── public API ───────────────────────────────────────────────────

    def paths(self) -> list[str]:
        return list(self._paths)

    def clear_all(self):
        self.clear()
        self._paths.clear()
        self._notify()

    def remove_selected(self):
        rows = sorted({self.row(i) for i in self.selectedItems()}, reverse=True)
        for row in rows:
            self.takeItem(row)
            self._paths.pop(row)
        self._notify()

    # ── helpers ──────────────────────────────────────────────────────

    def _has_images(self, mime_data) -> bool:
        return any(self._is_image(u.toLocalFile()) for u in mime_data.urls())

    def _is_image(self, path: str) -> bool:
        return os.path.isfile(path) and Path(path).suffix.lower() in IMAGE_EXTS

    def _notify(self):
        if self._on_change:
            self._on_change()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("画像リネーマー")
        self.setMinimumSize(960, 660)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("画像リネーマー")
        title.setFont(QFont("", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        sub = QLabel("①左に画像をドロップ　②右に名前リストをペースト　③「名前を変更する」をクリック")
        sub.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(sub)

        panels = QHBoxLayout()
        panels.setSpacing(16)
        panels.addLayout(self._left_panel(), stretch=1)
        panels.addLayout(self._right_panel(), stretch=1)
        layout.addLayout(panels)

        layout.addWidget(self._preview_section())
        layout.addWidget(self._rename_button())

        QShortcut(QKeySequence.StandardKey.Delete, self).activated.connect(
            self.drop_list.remove_selected
        )

    def _left_panel(self) -> QVBoxLayout:
        vbox = QVBoxLayout()

        lbl = QLabel("① 画像をドラッグ＆ドロップ")
        lbl.setFont(QFont("", 11, QFont.Weight.Bold))
        vbox.addWidget(lbl)

        hint = QLabel("複数まとめてドロップ可。Deleteキーで選択行を削除。")
        hint.setStyleSheet("color: #777; font-size: 11px;")
        vbox.addWidget(hint)

        self.drop_list = DropListWidget(on_change=self._refresh_preview)
        self.drop_list.setStyleSheet("""
            QListWidget {
                border: 2px dashed #bbb;
                border-radius: 10px;
                background: #f5f5f5;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background: #bbdefb;
                color: #000;
            }
        """)
        vbox.addWidget(self.drop_list)

        clear_btn = QPushButton("リストをクリア")
        clear_btn.setStyleSheet("padding: 6px; font-size: 12px;")
        clear_btn.clicked.connect(self.drop_list.clear_all)
        vbox.addWidget(clear_btn)
        return vbox

    def _right_panel(self) -> QVBoxLayout:
        vbox = QVBoxLayout()

        lbl = QLabel("② 新しい名前をペースト（1行 = 1ファイル）")
        lbl.setFont(QFont("", 11, QFont.Weight.Bold))
        vbox.addWidget(lbl)

        hint = QLabel("スプレッドシートからそのままコピペ。拡張子は自動で補完。")
        hint.setStyleSheet("color: #777; font-size: 11px;")
        vbox.addWidget(hint)

        self.name_edit = QTextEdit()
        self.name_edit.setPlaceholderText(
            "例:\n田中太郎\n山田花子\n佐藤次郎\n\n※ スプレッドシートの列をコピーしてここにペーストするだけでOK"
        )
        self.name_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #ddd;
                border-radius: 10px;
                background: #fff;
                color: #000;
                font-size: 13px;
                padding: 8px;
            }
        """)
        self.name_edit.textChanged.connect(self._refresh_preview)
        vbox.addWidget(self.name_edit)

        clear_btn = QPushButton("名前リストをクリア")
        clear_btn.setStyleSheet("padding: 6px; font-size: 12px;")
        clear_btn.clicked.connect(self.name_edit.clear)
        vbox.addWidget(clear_btn)
        return vbox

    def _preview_section(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        self._preview_label = QLabel("プレビュー")
        self._preview_label.setFont(QFont("", 11, QFont.Weight.Bold))
        vbox.addWidget(self._preview_label)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["変更前", "変更後"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMaximumHeight(160)
        self.table.setStyleSheet("font-size: 13px;")
        vbox.addWidget(self.table)
        return w

    def _rename_button(self) -> QPushButton:
        btn = QPushButton("名前を変更する")
        btn.setFont(QFont("", 13, QFont.Weight.Bold))
        btn.setMinimumHeight(52)
        btn.setStyleSheet("""
            QPushButton {
                background: #1976D2;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover   { background: #1565C0; }
            QPushButton:pressed { background: #0D47A1; }
        """)
        btn.clicked.connect(self._do_rename)
        return btn

    # ── logic ────────────────────────────────────────────────────────

    def _names(self) -> list[str]:
        return [ln.strip() for ln in self.name_edit.toPlainText().splitlines() if ln.strip()]

    def _resolve_new_name(self, orig_path: str, raw_name: str) -> str:
        """拡張子が省略されていれば元の拡張子を付ける。"""
        if Path(raw_name).suffix:
            return raw_name
        return raw_name + Path(orig_path).suffix

    def _refresh_preview(self):
        all_paths = self.drop_list.paths()
        names = self._names()
        matched = min(len(all_paths), len(names))

        self._preview_label.setText(
            f"プレビュー　{matched} 件がリネーム対象"
            + (f"　（名前不足: {len(all_paths) - matched} 件スキップ）"
               if len(all_paths) > len(names) else "")
        )

        self.table.setRowCount(len(all_paths))
        for i, path in enumerate(all_paths):
            orig_item = QTableWidgetItem(os.path.basename(path))

            if i < len(names):
                new_name = self._resolve_new_name(path, names[i])
                new_item = QTableWidgetItem(new_name)
                new_path = Path(path).parent / new_name
                if new_path.exists() and str(new_path) != path:
                    new_item.setBackground(QColor("#FFCDD2"))
                    new_item.setToolTip("同名ファイルが既に存在します — スキップされます")
                else:
                    new_item.setBackground(QColor("#C8E6C9"))
            else:
                new_item = QTableWidgetItem("— 名前なし（スキップ）")
                new_item.setBackground(QColor("#FFF9C4"))
                new_item.setForeground(QColor("#888"))

            self.table.setItem(i, 0, orig_item)
            self.table.setItem(i, 1, new_item)

    def _do_rename(self):
        all_paths = self.drop_list.paths()
        names = self._names()

        pairs: list[tuple[str, str]] = []
        for i, path in enumerate(all_paths):
            if i >= len(names):
                break
            pairs.append((path, self._resolve_new_name(path, names[i])))

        if not pairs:
            QMessageBox.warning(self, "警告",
                "変更できるファイルがありません。\n画像をドロップして名前リストを入力してください。")
            return

        reply = QMessageBox.question(
            self, "確認",
            f"{len(pairs)} 件のファイル名を変更します。よろしいですか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, errors = 0, []
        for orig_path, new_name in pairs:
            new_path = Path(orig_path).parent / new_name
            if new_path.exists() and str(new_path) != orig_path:
                errors.append(f"{os.path.basename(orig_path)}: 同名ファイルが既に存在します（スキップ）")
                continue
            try:
                Path(orig_path).rename(new_path)
                ok += 1
            except OSError as e:
                errors.append(f"{os.path.basename(orig_path)}: {e}")

        if errors:
            QMessageBox.warning(self, "完了（エラーあり）",
                f"{ok} 件成功 / {len(errors)} 件失敗:\n\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "完了", f"{ok} 件のファイルをリネームしました。")

        self.drop_list.clear_all()
        self.name_edit.clear()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
