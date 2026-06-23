#!/usr/bin/env python3
"""IKU NAVI 画像チェッカー — 全グラフエッジの経路画像 存在確認ツール

/api/graph でグラフ上の全エッジを取得し、その両方向を網羅的に確認する。
/api/edge_images で登録済み URL を取得し、実際に CDN へアクセスして判定。

カードの状態:
  ok           … CSV 登録済み + CDN に実在
  missing      … CSV 登録済み + CDN に存在しない
  unregistered … グラフ上にエッジがあるが edge_image.csv に未登録
"""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea,
    QFrame, QProgressBar, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPixmap, QPainter, QPen


# ── 設定 ──────────────────────────────────────────────────────────────────────
DEFAULT_API = "http://localhost:5001"
CARD_W      = 230
CARD_H      = 215
THUMB_H     = 135
MAX_WORKERS = 6     # Cloudflare レート制限対策で抑え気味

# Accept-Encoding に "br" を入れると Cloudflare が Brotli で返し、
# brotli パッケージ未インストール環境では解凍できず空になるため除外。
# requests のデフォルト (gzip, deflate) に任せる。
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Connection":      "keep-alive",
}


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    retry = Retry(total=3, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://",  adapter)
    return s


# ── パレット ──────────────────────────────────────────────────────────────────
BG_WIN        = "#111827"
BG_BAR        = "#1F2937"
BG_CARD_OK    = "#0C2318"
BG_CARD_NG    = "#2B0F0F"
BG_CARD_UNREG = "#1A1A2A"
BG_CARD_LOAD  = "#1A2233"
BG_THUMB      = "#0D1626"
TXT_PRIMARY   = "#F1F5F9"
TXT_SECONDARY = "#94A3B8"
TXT_KEY       = "#CBD5E1"
ACCENT        = "#00B8E6"
COL_OK        = "#4ADE80"
COL_NG        = "#F87171"
COL_UNREG     = "#6B7280"
COL_WARN      = "#FBBF24"
BTN_ACTIVE    = "#0E7490"
BTN_IDLE      = "#374151"
BORDER        = "#2D3748"


# ─────────────────────────────────────────────────────────────────────────────
# ワーカー
# ─────────────────────────────────────────────────────────────────────────────

class FetchGraphWorker(QThread):
    """/api/graph と /api/edge_images を取得する"""
    # nodes_map: {node_id: {building, floor, ...}}
    # edges_list: [{id, from, to, building, floor, ...}]
    # edge_images: {"from_to": url}
    finished = pyqtSignal(dict, list, dict)
    error    = pyqtSignal(str)

    def __init__(self, api_url: str):
        super().__init__()
        self.api_url = api_url.rstrip("/")

    def run(self):
        session = _make_session()
        session.headers["Accept"] = "application/json"
        try:
            graph_data  = self._get(session, f"{self.api_url}/api/graph")
            edge_images = self._get(session, f"{self.api_url}/api/edge_images")
        except Exception as e:
            self.error.emit(str(e))
            return

        nodes_map  = {int(n["id"]): n for n in graph_data.get("nodes", [])}
        edges_list = graph_data.get("edges", [])
        self.finished.emit(nodes_map, edges_list, edge_images)

    def _get(self, session: requests.Session, url: str) -> dict:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        if "text/html" in ct:
            raise RuntimeError(
                f"HTML が返りました（Cloudflare チャレンジ？）\n"
                f"URL: {url}  HTTP {r.status_code}"
            )
        return r.json()


class ImageFetchWorker(QThread):
    """登録済みエッジ画像を並列フェッチして結果を emit する"""
    image_ready = pyqtSignal(str, bytes)   # key, bytes (空 = 欠損)
    progress    = pyqtSignal(int, int)     # done, total

    def __init__(self, tasks: list):
        super().__init__()
        self._tasks = tasks   # [(key, url), ...]
        self._done  = 0
        self._lock  = threading.Lock()

    def run(self):
        total = len(self._tasks)
        tls   = threading.local()

        def get_session() -> requests.Session:
            if not hasattr(tls, "s"):
                tls.s = _make_session()
                tls.s.headers["Accept"] = "image/*,*/*;q=0.8"
            return tls.s

        def fetch_one(task):
            key, url = task
            try:
                r    = get_session().get(url, timeout=12)
                data = r.content if r.status_code == 200 else b""
            except Exception:
                data = b""
            with self._lock:
                self._done += 1
                n = self._done
            self.image_ready.emit(key, data)
            self.progress.emit(n, total)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            list(pool.map(fetch_one, self._tasks))


# ─────────────────────────────────────────────────────────────────────────────
# 画像カード
# ─────────────────────────────────────────────────────────────────────────────

class ImageCard(QFrame):
    """1 directed-edge = 1 カード"""

    _BG = {
        "loading":      BG_CARD_LOAD,
        "ok":           BG_CARD_OK,
        "missing":      BG_CARD_NG,
        "unregistered": BG_CARD_UNREG,
    }

    def __init__(self, key: str, url: str | None,
                 building: int, floor: int, initial_state: str = "loading",
                 parent=None):
        super().__init__(parent)
        self.key      = key
        self.url      = url
        self.building = building
        self.floor    = floor
        self._state   = initial_state
        self.setFixedSize(CARD_W, CARD_H)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._build_ui()
        self._apply_style()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 6)
        root.setSpacing(0)

        # サムネイル
        self._thumb = QLabel()
        self._thumb.setFixedSize(CARD_W, THUMB_H)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            f"background: {BG_THUMB}; border-radius: 8px 8px 0 0;"
        )
        self._draw_thumb_for_state()
        root.addWidget(self._thumb)

        # 情報
        info = QWidget()
        info.setStyleSheet("background: transparent;")
        vb = QVBoxLayout(info)
        vb.setContentsMargins(8, 5, 8, 0)
        vb.setSpacing(2)

        parts    = self.key.split("_")
        key_lbl  = QLabel(f"{parts[0]} →\n{parts[1]}")
        key_lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        key_lbl.setStyleSheet(f"color: {TXT_KEY}; background: transparent;")
        vb.addWidget(key_lbl)

        bldg_txt = "屋外" if self.building == 0 else f"{self.building}号館 {self.floor}階"
        bldg_lbl = QLabel(bldg_txt)
        bldg_lbl.setFont(QFont("", 11))
        bldg_lbl.setStyleSheet(f"color: {TXT_SECONDARY}; background: transparent;")
        vb.addWidget(bldg_lbl)

        root.addWidget(info)

        # ステータス
        self._status = QLabel()
        self._status.setFont(QFont("", 11, QFont.Weight.Bold))
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_status_label()
        root.addWidget(self._status)

    def _apply_style(self):
        bg = self._BG.get(self._state, BG_CARD_LOAD)
        self.setStyleSheet(f"""
            ImageCard {{
                background: {bg};
                border-radius: 8px;
                border: 1px solid {BORDER};
            }}
        """)

    def _update_status_label(self):
        conf = {
            "loading":      ("読み込み中...",      COL_WARN),
            "ok":           ("✔  OK",              COL_OK),
            "missing":      ("✕  CDN に存在しない", COL_NG),
            "unregistered": ("—  CSV 未登録",       COL_UNREG),
        }
        text, color = conf.get(self._state, ("", TXT_SECONDARY))
        self._status.setText(text)
        self._status.setStyleSheet(
            f"color: {color}; background: transparent; padding-bottom: 2px;"
        )

    # ── サムネイル描画 ────────────────────────────────────────────────────────

    def _draw_thumb_for_state(self):
        if self._state == "loading":
            self._draw_text_thumb("取得中...", TXT_SECONDARY, BG_THUMB)
        elif self._state == "missing":
            self._draw_text_thumb("✕  画像なし", COL_NG, "#180808")
        elif self._state == "unregistered":
            self._draw_text_thumb("—  未登録", COL_UNREG, "#111120")
        # ok はセット時に上書き

    def _draw_text_thumb(self, text: str, color: str, bg: str):
        pix = QPixmap(CARD_W, THUMB_H)
        pix.fill(QColor(bg))
        p = QPainter(pix)
        p.setPen(QPen(QColor(color), 2))
        p.setFont(QFont("", 14, QFont.Weight.Bold))
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text)
        p.end()
        self._thumb.setPixmap(pix)

    # ── 外部 API ─────────────────────────────────────────────────────────────

    def set_image(self, data: bytes):
        """ImageFetchWorker から呼ばれる（必ず登録済みカードのみ）"""
        if data:
            pix = QPixmap()
            if pix.loadFromData(data) and not pix.isNull():
                scaled = pix.scaled(
                    CARD_W, THUMB_H,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = max(0, (scaled.width()  - CARD_W)  // 2)
                y = max(0, (scaled.height() - THUMB_H) // 2)
                self._thumb.setPixmap(scaled.copy(x, y, CARD_W, THUMB_H))
                self._state = "ok"
                self._update_status_label()
                self._apply_style()
                return

        self._state = "missing"
        self._draw_text_thumb("✕  画像なし", COL_NG, "#180808")
        self._update_status_label()
        self._apply_style()

    @property
    def state(self) -> str:
        return self._state


# ─────────────────────────────────────────────────────────────────────────────
# メインウィンドウ
# ─────────────────────────────────────────────────────────────────────────────

# フィルタ定数
FILTER_ALL   = "all"
FILTER_NG    = "missing"       # CDN 欠損
FILTER_UNREG = "unregistered"  # CSV 未登録
FILTER_ATTN  = "attention"     # 欠損 + 未登録まとめて


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IKU NAVI 画像チェッカー")
        self.setMinimumSize(980, 680)
        self.resize(1280, 820)

        self._cards:            dict[str, ImageCard] = {}
        self._buildings:        list[int] = []
        self._bldg_btn_map:     dict[int, QPushButton] = {}
        self._current_building: int = -1
        self._filter_state:     str = FILTER_ALL

        self._fetch_worker: FetchGraphWorker  | None = None
        self._img_worker:   ImageFetchWorker  | None = None

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._refresh_grid)

        self._build_ui()
        self._apply_theme()

    # ── テーマ ────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget  {{ background: {BG_WIN}; color: {TXT_PRIMARY}; }}
            QScrollArea           {{ background: {BG_WIN}; border: none; }}
            QScrollBar:vertical   {{ background: {BG_BAR}; width: 8px; border-radius: 4px; }}
            QScrollBar::handle:vertical {{
                background: #4B5563; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar:horizontal {{ background: {BG_BAR}; height: 8px; border-radius: 4px; }}
            QScrollBar::handle:horizontal {{
                background: #4B5563; border-radius: 4px; min-width: 20px;
            }}
            QLineEdit {{
                background: #374151; color: {TXT_PRIMARY};
                border: 1px solid #4B5563; border-radius: 6px;
                padding: 5px 10px; font-size: 15px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
            QProgressBar {{
                background: #374151; border: none; border-radius: 4px;
                color: transparent;
            }}
            QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
        """)

    # ── UI 構築 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self._build_topbar())
        vbox.addWidget(self._build_filterbar())
        vbox.addWidget(self._build_scroll(), stretch=1)

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(62)
        bar.setStyleSheet(f"background: {BG_BAR}; border-bottom: 1px solid {BORDER};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(10)

        title = QLabel("IKU NAVI 画像チェッカー")
        title.setFont(QFont("", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT};")
        row.addWidget(title)

        row.addSpacing(12)
        lbl = QLabel("API URL:")
        lbl.setStyleSheet(f"color: {TXT_SECONDARY}; font-size: 16px;")
        row.addWidget(lbl)

        self._api_edit = QLineEdit(DEFAULT_API)
        self._api_edit.setFixedWidth(260)
        self._api_edit.returnPressed.connect(self._start_fetch)
        row.addWidget(self._api_edit)

        self._fetch_btn = QPushButton("取得開始")
        self._fetch_btn.setFixedSize(100, 34)
        self._fetch_btn.setFont(QFont("", 13, QFont.Weight.Bold))
        self._fetch_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #001A22; border-radius: 6px;
            }}
            QPushButton:hover    {{ background: #22D4FF; }}
            QPushButton:pressed  {{ background: #0099BB; }}
            QPushButton:disabled {{ background: #374151; color: {TXT_SECONDARY}; }}
        """)
        self._fetch_btn.clicked.connect(self._start_fetch)
        row.addWidget(self._fetch_btn)

        row.addSpacing(6)

        self._progress = QProgressBar()
        self._progress.setFixedSize(180, 8)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        row.addWidget(self._progress)

        row.addStretch()

        self._status_lbl = QLabel("API URL を入力して「取得開始」")
        self._status_lbl.setStyleSheet(f"color: {TXT_SECONDARY}; font-size: 16px;")
        row.addWidget(self._status_lbl)

        return bar

    def _build_filterbar(self) -> QWidget:
        self._filterbar = QWidget()
        self._filterbar.setFixedHeight(48)
        self._filterbar.setStyleSheet(
            f"background: {BG_BAR}; border-bottom: 1px solid {BORDER};"
        )
        self._filterbar_row = QHBoxLayout(self._filterbar)
        self._filterbar_row.setContentsMargins(16, 0, 16, 0)
        self._filterbar_row.setSpacing(6)
        self._filterbar_row.addStretch()
        return self._filterbar

    def _rebuild_filterbar(self):
        while self._filterbar_row.count():
            item = self._filterbar_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._bldg_btn_map = {}

        # ── 号館フィルタ ─────────────────────────────────────────────────────
        lbl1 = QLabel("号館:")
        lbl1.setStyleSheet(f"color: {TXT_SECONDARY}; font-size: 16px;")
        self._filterbar_row.addWidget(lbl1)

        all_bldg = self._make_pill("全て", True)
        all_bldg.clicked.connect(lambda: self._filter_building(-1))
        self._filterbar_row.addWidget(all_bldg)
        self._bldg_btn_map[-1] = all_bldg

        for bldg in self._buildings:
            label = "屋外" if bldg == 0 else f"{bldg}号館"
            btn   = self._make_pill(label, False)
            btn.clicked.connect(lambda _=False, b=bldg: self._filter_building(b))
            self._filterbar_row.addWidget(btn)
            self._bldg_btn_map[bldg] = btn

        # ── セパレータ ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(24)
        sep.setStyleSheet(f"color: {BORDER};")
        self._filterbar_row.addSpacing(8)
        self._filterbar_row.addWidget(sep)
        self._filterbar_row.addSpacing(8)

        # ── 状態フィルタ ──────────────────────────────────────────────────────
        lbl2 = QLabel("表示:")
        lbl2.setStyleSheet(f"color: {TXT_SECONDARY}; font-size: 16px;")
        self._filterbar_row.addWidget(lbl2)

        self._state_btns: dict[str, QPushButton] = {}
        filters = [
            (FILTER_ALL,   "全て"),
            (FILTER_NG,    "欠損"),
            (FILTER_UNREG, "未登録"),
            (FILTER_ATTN,  "要対応"),
        ]
        for fkey, flabel in filters:
            btn = self._make_pill(flabel, fkey == FILTER_ALL)
            btn.clicked.connect(lambda _=False, k=fkey: self._filter_state_set(k))
            self._filterbar_row.addWidget(btn)
            self._state_btns[fkey] = btn

        self._filterbar_row.addStretch()

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: {TXT_SECONDARY}; font-size: 16px;")
        self._filterbar_row.addWidget(self._count_lbl)

    def _make_pill(self, text: str, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.setFont(QFont("", 12))
        self._set_pill(btn, active)
        return btn

    def _set_pill(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BTN_ACTIVE}; color: #FFF;
                    border-radius: 5px; padding: 0 12px; border: none;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BTN_IDLE}; color: {TXT_PRIMARY};
                    border-radius: 5px; padding: 0 12px; border: none;
                }}
                QPushButton:hover {{ background: #4B5563; }}
            """)

    def _build_scroll(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)

        gw = QWidget()
        gw.setStyleSheet(f"background: {BG_WIN};")
        gl = QGridLayout(gw)
        gl.setContentsMargins(16, 16, 16, 16)
        gl.setSpacing(12)
        gl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        ph = QLabel("API URL を入力して「取得開始」をクリックしてください")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet(f"color: {TXT_SECONDARY}; font-size: 16px;")
        gl.addWidget(ph, 0, 0)

        self._grid_widget = gw
        self._grid_layout = gl
        self._scroll.setWidget(gw)
        return self._scroll

    # ── フェッチ ──────────────────────────────────────────────────────────────

    def _start_fetch(self):
        api_url = self._api_edit.text().strip()
        if not api_url:
            QMessageBox.warning(self, "エラー", "API URL を入力してください。")
            return

        self._cards.clear()
        self._buildings.clear()
        self._current_building = -1
        self._filter_state     = FILTER_ALL

        self._fetch_btn.setEnabled(False)
        self._set_status("API に接続中...", TXT_SECONDARY)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)

        self._fetch_worker = FetchGraphWorker(api_url)
        self._fetch_worker.finished.connect(self._on_graph_data)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.start()

    def _on_fetch_error(self, msg: str):
        self._fetch_btn.setEnabled(True)
        self._set_status(f"エラー: {msg}", COL_NG)
        QMessageBox.critical(
            self, "取得エラー",
            f"API への接続に失敗しました:\n\n{msg}\n\n"
            "サーバーが起動しているか確認してください。"
        )

    def _on_graph_data(self, nodes_map: dict, edges_list: list, edge_images: dict):
        """グラフ上の全エッジ（両方向）を網羅してカードを生成する"""

        self._set_status("グラフを解析中...", TXT_SECONDARY)

        buildings_set: set[int] = set()
        tasks: list[tuple[str, str]] = []   # 登録済みエッジの (key, url) リスト
        seen:  set[str] = set()

        # 全エッジ × 両方向を処理
        for edge in edges_list:
            from_id  = int(edge["from"])
            to_id    = int(edge["to"])
            # エッジのノードが nodes_map になければ from_id を参照
            nf       = nodes_map.get(from_id, {})
            building = nf.get("building", edge.get("building", -1))
            floor    = nf.get("floor",    edge.get("floor",    1))
            buildings_set.add(building)

            for f, t in [(from_id, to_id), (to_id, from_id)]:
                key = f"{f}_{t}"
                if key in seen:
                    continue
                seen.add(key)

                # 方向を反転した場合は to_id の建物情報を使う
                if f == to_id:
                    nt       = nodes_map.get(to_id, {})
                    building = nt.get("building", edge.get("building", -1))
                    floor    = nt.get("floor",    edge.get("floor",    1))
                    buildings_set.add(building)

                url = edge_images.get(key)
                if url:
                    card = ImageCard(key, url, building, floor, "loading")
                    tasks.append((key, url))
                else:
                    card = ImageCard(key, None, building, floor, "unregistered")

                self._cards[key] = card

        self._buildings = sorted(buildings_set)
        self._rebuild_filterbar()
        self._refresh_grid()

        total_edges = len(self._cards)
        registered  = len(tasks)
        unreg       = total_edges - registered
        self._set_status(
            f"全 {total_edges} エッジ  登録済 {registered}  未登録 {unreg}  — 画像取得中...",
            TXT_SECONDARY,
        )
        self._progress.setRange(0, max(1, registered))
        self._progress.setValue(0)

        if not tasks:
            self._fetch_btn.setEnabled(True)
            self._set_status(
                f"全 {total_edges} エッジ中、CSV 登録済みが 0 件でした", COL_WARN
            )
            return

        self._img_worker = ImageFetchWorker(tasks)
        self._img_worker.image_ready.connect(self._on_image_ready)
        self._img_worker.progress.connect(self._on_progress)
        self._img_worker.finished.connect(self._on_images_done)
        self._img_worker.start()

    def _on_image_ready(self, key: str, data: bytes):
        card = self._cards.get(key)
        if card:
            card.set_image(data)
            self._update_count_lbl()

    def _on_progress(self, done: int, total: int):
        self._progress.setValue(done)
        self._set_status(f"画像取得中... {done} / {total}", TXT_SECONDARY)

    def _on_images_done(self):
        self._fetch_btn.setEnabled(True)
        ok      = sum(1 for c in self._cards.values() if c.state == "ok")
        missing = sum(1 for c in self._cards.values() if c.state == "missing")
        unreg   = sum(1 for c in self._cards.values() if c.state == "unregistered")
        total   = len(self._cards)

        if missing or unreg:
            self._set_status(
                f"完了: 全 {total} エッジ  ✔ {ok}  ✕ 欠損 {missing}  — 未登録 {unreg}",
                COL_NG,
            )
        else:
            self._set_status(f"完了: 全 {total} エッジ  ✔ 全て OK", COL_OK)

        self._update_count_lbl()
        if self._filter_state != FILTER_ALL:
            self._refresh_grid()

    # ── グリッド制御 ──────────────────────────────────────────────────────────

    def _visible_cards(self) -> list[ImageCard]:
        def match_state(c: ImageCard) -> bool:
            if self._filter_state == FILTER_ALL:   return True
            if self._filter_state == FILTER_NG:    return c.state == "missing"
            if self._filter_state == FILTER_UNREG: return c.state == "unregistered"
            if self._filter_state == FILTER_ATTN:  return c.state in ("missing", "unregistered")
            return True

        cards = [
            c for c in self._cards.values()
            if (self._current_building == -1 or c.building == self._current_building)
            and match_state(c)
        ]
        # (building, floor, from_id) 順に並べる
        return sorted(cards, key=lambda c: (c.building, c.floor, int(c.key.split("_")[0])))

    def _refresh_grid(self):
        for card in self._cards.values():
            card.setParent(None)

        old = self._scroll.takeWidget()
        if old:
            old.deleteLater()

        gw = QWidget()
        gw.setStyleSheet(f"background: {BG_WIN};")
        gl = QGridLayout(gw)
        gl.setContentsMargins(16, 16, 16, 16)
        gl.setSpacing(12)
        gl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._grid_widget = gw
        self._grid_layout = gl

        visible = self._visible_cards()

        if not visible and not self._cards:
            lbl = QLabel("API URL を入力して「取得開始」をクリックしてください")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TXT_SECONDARY}; font-size: 16px;")
            gl.addWidget(lbl, 0, 0)
        elif not visible:
            lbl = QLabel("該当するエッジがありません")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TXT_SECONDARY}; font-size: 16px;")
            gl.addWidget(lbl, 0, 0)
        else:
            vw   = max(1, self._scroll.viewport().width() - 32)
            cols = max(1, vw // (CARD_W + 12))
            for i, card in enumerate(visible):
                gl.addWidget(card, i // cols, i % cols)

        self._scroll.setWidget(gw)
        self._update_count_lbl()

    def _filter_building(self, building: int):
        self._current_building = building
        for b, btn in self._bldg_btn_map.items():
            self._set_pill(btn, b == building)
        self._refresh_grid()

    def _filter_state_set(self, fkey: str):
        self._filter_state = fkey
        for k, btn in self._state_btns.items():
            self._set_pill(btn, k == fkey)
        self._refresh_grid()

    # ── ユーティリティ ────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 16px;")

    def _update_count_lbl(self):
        if not hasattr(self, "_count_lbl"):
            return

        total   = len(self._cards)
        ok      = sum(1 for c in self._cards.values() if c.state == "ok")
        missing = sum(1 for c in self._cards.values() if c.state == "missing")
        unreg   = sum(1 for c in self._cards.values() if c.state == "unregistered")
        loading = total - ok - missing - unreg
        visible = len(self._visible_cards())

        parts = [f"全 {total} エッジ"]
        if loading:
            parts.append(f"読込中 {loading}")
        parts += [f"✔ {ok}", f"✕ 欠損 {missing}", f"— 未登録 {unreg}"]

        if self._current_building != -1:
            bldg_cards  = [c for c in self._cards.values() if c.building == self._current_building]
            bldg_total  = len(bldg_cards)
            bldg_ok     = sum(1 for c in bldg_cards if c.state == "ok")
            bldg_miss   = sum(1 for c in bldg_cards if c.state == "missing")
            bldg_unreg  = sum(1 for c in bldg_cards if c.state == "unregistered")
            bldg_name   = "屋外" if self._current_building == 0 else f"{self._current_building}号館"
            parts.append(
                f"[{bldg_name}: 全 {bldg_total}  ✔ {bldg_ok}  ✕ {bldg_miss}  — {bldg_unreg}  表示 {visible}]"
            )
        else:
            parts.append(f"[表示 {visible}]")

        color = COL_NG if (missing or unreg) else (TXT_SECONDARY if loading else COL_OK)
        self._count_lbl.setText("  ".join(parts))
        self._count_lbl.setStyleSheet(f"color: {color}; font-size: 16px;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._cards:
            self._resize_timer.start(180)


# ─────────────────────────────────────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
