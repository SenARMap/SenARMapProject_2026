# 技術説明書 — SenARMap 2026

> 作成: 2026-06-02

---

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [システム全体構成](#2-システム全体構成)
3. [バックエンド](#3-バックエンド)
4. [フロントエンド](#4-フロントエンド)
5. [データ構造](#5-データ構造)
6. [CDN](#6-cdn)
7. [インフラ・デプロイ](#7-インフラデプロイ)
8. [経路探索アルゴリズム](#8-経路探索アルゴリズム)

---

## 1. プロジェクト概要

大学構内を対象にした AR 対応ナビゲーション Web アプリ。  
屋外は Google Maps、屋内は SVG フロアマップでルートを表示し、スマートフォンの GPS と組み合わせてステップ ナビゲーションを行う。  
下半分の AR 領域には将来的にカメラ映像・経路画像を重畳表示する予定。

---

## 2. システム全体構成

```
ブラウザ
  |
  | HTTPS
  v
Cloudflare Tunnel  ←  TUNNEL_TOKEN (.env)
  |
  v
Nginx (Docker)  :443
  |
  |-- /          → 静的ファイル配信 (programs/html/)
  |-- /api/*     → リバースプロキシ → Flask (Docker) :8000
  |-- /3d/*      → リバースプロキシ → Flask (Docker) :8000
  |
  v
Flask / Gunicorn (Docker)  :8000
  |
  +-- data/ (CSV, JSON)
  +-- programs/html/svg/ (SVG フロアマップ)

CDN (cdn.iku-navi.net)
  |
  +-- エッジ画像 (JPG)  ← フロントエンドが直接参照
```

---

## 3. バックエンド

### 言語・フレームワーク

| 項目 | 内容 |
|------|------|
| 言語 | Python 3 |
| Web フレームワーク | Flask |
| WSGI サーバー | Gunicorn (`-w 3`) — ワーカー 3 プロセス |
| エントリポイント | `programs/3D_Graph/app.py` |

### 主なライブラリ

| ライブラリ | 用途 |
|-----------|------|
| `pandas` | CSV 読み込み・データ整形 |
| `networkx` | グラフ構築・Dijkstra 経路探索 |
| `Flask` | REST API サーバー |
| `gunicorn` | 本番 WSGI サーバー |
| `plotly` / `pyvis` | 3D グラフビューア（`/3d/` パス） |

### API エンドポイント一覧

| エンドポイント | 概要 |
|--------------|------|
| `GET /api/all` | 全教室・全ノード・建物一覧を一括取得（フロントの初期化用） |
| `GET /api/rooms` | 教室一覧（`building`・`q` でフィルタ可） |
| `GET /api/route` | 統合経路探索（教室名またはノード ID で出発/目的を指定） |
| `GET /api/navigate_to_room` | 教室→教室の経路探索（後方互換エンドポイント） |
| `GET /api/nearest_toilet` | 最寄りトイレへの経路探索（M/F/C/ALL） |
| `GET /api/shortest_path` | ノード ID 直指定の経路探索 |
| `GET /api/graph` | 3D ビューア用全グラフデータ |
| `GET /api/edge_images` | エッジ→画像 URL マッピング（CDN URL を返す） |
| `GET /api/building_config` | 建物の座標変換パラメータ取得 |
| `POST /api/building_config/<id>` | 建物の変換パラメータ更新 |

詳細なリクエスト/レスポンス仕様は [`API_Destination.md`](./API_Destination.md) を参照。

### キャッシュ

起動後の初回リクエスト時に CSV をすべてロードしてメモリにキャッシュする（モジュールレベルのグローバル変数）。  
エレベーター有り/無しのグラフを別々にキャッシュし、切り替えコストをゼロにしている。  
`POST /api/building_config` でパラメータ更新時はキャッシュをクリアして再構築する。

```
_cached_nodes_df           — pandas DataFrame
_cached_edges_df           — pandas DataFrame
_cached_graph_with_ev      — networkx.DiGraph（エレベーターあり）
_cached_graph_without_ev   — networkx.DiGraph（エレベーターなし）
```

---

## 4. フロントエンド

### 言語・ライブラリ

| 項目 | 内容 |
|------|------|
| 言語 | HTML / CSS / Vanilla JavaScript（フレームワークなし） |
| マップ | Google Maps JavaScript API（CDN 経由） |
| SVG マップ | インライン SVG（`/svg/{建物}_{階}F.svg` を `fetch` してインジェクト） |
| API キー | `programs/html/script/config.js` に `CONFIG.GOOGLE_MAPS_API_KEY` として記述 |

### Google Maps CDN の読み込み方法

フレームワークを使わず、JS でスクリプトタグを動的生成して読み込んでいる。  
`CONFIG.GOOGLE_MAPS_API_KEY` は `config.js` から取得するため、HTML に API キーをハードコードしない。

```javascript
const _ms = document.createElement("script");
_ms.src   = `https://maps.googleapis.com/maps/api/js?key=${CONFIG.GOOGLE_MAPS_API_KEY}&callback=initMap`;
_ms.async = true;
_ms.defer = true;
document.body.appendChild(_ms);
```

### レスポンシブレイアウト

| ブレークポイント | レイアウト |
|----------------|-----------|
| `< 768px`（スマートフォン） | 縦積み：検索パネル → マップ → ナビバー → AR 領域 |
| `>= 768px`（PC・タブレット） | 2カラム：左サイドバー 340px（検索 + ナビ + AR）/ 右マップ全高 |

モバイルでは `#sidebar` に `display: contents` を適用して CSS フレックスの `order` でレイアウトを制御。  
PC では `#sidebar` が通常の `display: flex` に切り替わる。

### 屋内/屋外の自動切り替え

`pathCoords` の各ノードの `building` フィールドで判定する。

- `building === 0` → 屋外 → Google Maps を表示、マーカーを配置、行き先方向に `map.setHeading()` で地図を回転
- `building !== 0` → 屋内 → SVG フロアマップを表示、Dijkstra パスをオーバーレイ描画

### 経路ナビゲーション UI

- 左右矢印ボタンでステップ単位に移動
- SVG マップ：灰色のベースルート → 現在地まで青でハイライト → 赤い三角矢印で進行方向を表示
- Google Maps：行き先方向の方位角（`bearingDeg` 関数）を計算して `setHeading()` に渡す
- SVG の viewBox はルートの範囲から自動計算したウィンドウサイズで `panSvgTo()` によりスクロール追従

### カスタムオートコンプリート

`datalist` は使わず、`<div class="suggestions">` による独自ドロップダウンを実装。  
`mousedown` + `e.preventDefault()` で `blur` より先に選択イベントを処理し、クリックが無効になるバグを回避している。

### GPS

`navigator.geolocation.getCurrentPosition` で取得。精度（`accuracy`）が 30m を超えた場合は案内板を参照するよう警告を表示する。GPS 取得後は最近傍の屋外ノードを Haversine 距離で探索し、`from_node` パラメータとして API に渡す。

---

## 5. データ構造

### ノード ID の体系

```
屋内ノード  = building_id × 100,000 + local_id
屋外ノード  = local_id + 9,000,000
```

### node.csv（建物ごと）

| カラム | 説明 |
|--------|------|
| `id` | ローカル ID（ロード時にグローバル ID へ変換） |
| `x, y, z` | 建物ローカル座標（メートル） |
| `building` | 建物 ID |
| `floor` | 階数 |
| `type` | ノード種別（1: 通路, 2: エントランス など） |
| `svg_x, svg_y` | SVG フロアマップ上のピクセル座標 |

### global_node.csv（屋外）

| カラム | 説明 |
|--------|------|
| `id` | 屋外ノード ID（ローカル） |
| `x, y, z` | グローバル座標 |
| `lat, lng` | GPS 座標（WGS84） |
| `floor, type` | 屋外ノードは `floor=0`、`building=0` として扱う |

### edge.csv（建物ごと）

| カラム | 説明 |
|--------|------|
| `id` | エッジ ID |
| `name` | 教室名（複数の場合は `;` 区切り）、空欄は通路 |
| `from, to` | 接続ノード ID |
| `building, floor` | 所属建物・階 |
| `weight` | 探索コスト係数 |
| `length` | 実距離（メートル）。コスト = `weight × length` |
| `type` | エッジ種別（下表参照） |

### エッジ種別

| type | 意味 | 方向性 |
|------|------|--------|
| 1 | 通路 | 双方向 |
| 4 | エレベーター | 双方向（`use_elevator=0` で除外） |
| 5 | 上りエスカレーター | 一方向（Z 低→高） |
| 6 | 下りエスカレーター | 一方向（Z 高→低） |

### 座標系の変換

各建物のローカル座標は `anchors.csv` の 2 点アンカーから回転角 θ と平行移動量 (tx, ty, tz) を自動計算し、グローバル座標系に変換する。1 点アンカーの場合は `buildings.json` の `rot_deg` を使用。

```
X_global = cos(θ)·X_local - sin(θ)·Y_local + tx
Y_global = sin(θ)·X_local + cos(θ)·Y_local + ty
Z_global = Z_local + tz
```

### edge_image.csv

| カラム | 説明 |
|--------|------|
| `from, to` | エッジの両端ノード ID |
| `image_name` | CDN 上の画像ファイル名（例: `1000001_to_1000002.jpg`） |

---

## 6. CDN

| 項目 | 内容 |
|------|------|
| ベース URL | `https://cdn.iku-navi.net` |
| 用途 | エッジ間の経路画像（JPG）の配信 |
| 参照方法 | バックエンドの `GET /api/edge_images` がキー `"fromId_toId"` → URL のマッピングを返す。フロントエンドはこれを受け取り、現在のステップに対応する画像を AR 領域に表示する。 |
| アップロード管理 | `data/edge_image.csv` に `from`, `to`, `image_name` を記載して管理 |

CDN の URL は `app.py` の `CDN_BASE` 定数で一元管理している。

```python
CDN_BASE = "https://cdn.iku-navi.net"
```

---

## 7. インフラ・デプロイ

### Docker 構成（`deploy_env/docker-compose.yml`）

```
python    — Flask + Gunicorn（ポート 8000、内部のみ）
nginx     — Nginx リバースプロキシ（ポート 8080:80 / 4430:443）
cloudflared — Cloudflare Tunnel（外部公開）
```

### Nginx の役割

- HTTP (80) → HTTPS (443) リダイレクト
- TLS 終端（自己署名証明書を `/etc/nginx/certs/` に配置）
- 静的ファイル配信：`/` → `/project/programs/html/` を `try_files` で提供
- API・3D プロキシ：`/api/*` `/3d/*` → `http://python:8000` へ転送
- カスタムエラーページ：400/401/403/404/500/502/503/504

### Cloudflare Tunnel

`TUNNEL_TOKEN` を `.env` に設定するだけで外部からのアクセスが可能になる。  
ポートを直接インターネットに公開しないため、ファイアウォール設定が不要。

```
# enviroments/.env
TUNNEL_TOKEN=<Cloudflare Tunnel のトークン>
```

### ローカル開発環境

`enviroments/` ディレクトリに開発用の Docker 構成がある（`deploy_env/` は本番用）。  
Flask を直接起動する場合はポート 5001 を使用する。

```bash
cd programs/3D_Graph
python app.py   # localhost:5001 で起動
```

---

## 8. 経路探索アルゴリズム

### グラフ構造

NetworkX の `DiGraph`（有向グラフ）を使用。  
エスカレーターは一方向エッジのみ追加。それ以外のエッジは順・逆の 2 方向を追加することで無向グラフと等価に扱う。

### Dijkstra（双方向）

経路探索には `networkx.bidirectional_dijkstra` を使用。  
エッジのコストは `weight × length`（係数 × 実距離メートル）で定義される。

教室はノードではなくエッジの属性として管理されているため、教室に対応するエッジの両端ノード（from/to）を候補として全組み合わせを探索し、最短のものを採用する。

```
candidates = [
  (from_node_A, from_node_B),   ← 出発教室エッジの両端
  ...
] × [
  (to_node_X, to_node_Y),       ← 目的教室エッジの両端
  ...
]
→ 全組み合わせで bidirectional_dijkstra → 最短パスを採用
```

### 屋内-屋外の接続

`anchors.csv` に記録されたアンカーポイントをもとに、屋内ノードと屋外ノードを繋ぐエッジを自動生成する。これにより建物をまたぐ経路を 1 つのグラフで探索できる。
