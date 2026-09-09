#!/usr/bin/env python3
"""
IKU NAVI Event Editor — エントリーポイント

data/event.csv（イベントモードの検索候補「教室名/ノードID/エッジID」への紐付け）を
GUIで編集するツール。使い方は同ディレクトリの README.md を参照。

Usage:
  python main.py

依存:
  pip install -r requirements.txt
"""

import sys

from PyQt6.QtWidgets import QApplication

from app_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
