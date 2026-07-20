# 3D_Graph/app.py API 仕様書

`programs/3D_Graph/app.py` を実行（デフォルトポート: `5001`）することで利用できる、JSONを返すAPIエンドポイントの仕様です。

---

## 1. グラフ全体データ取得
**エンドポイント:** `GET /api/graph`
**概要:** 3Dビューアの描画などに必要な、全ノード、全エッジ、建物の色設定、および建物の変換設定（座標・回転情報）を一括で取得します。
**クエリパラメータ:** なし
**レスポンス例:**
```json
{
  "nodes": [
    {
      "id": 100001,
      "x": 1.0, "y": 2.0, "z": 0.0,
      "building": 1,
      "floor": 1,
      "type": 1,
      "color": "#4C9BE8",
      "label": "Node 100001<br>Building 1 / Floor 1"
    }
  ],
  "edges": [
    {
      "id": 1,
      "name": "101A",
      "from": 100001, "to": 100002,
      "building": 1, "floor": 1,
      "weight": 1.5, "length": 1.5, "type": "1",
      "x0": 1.0, "y0": 2.0, "z0": 0.0,
      "x1": 2.0, "y1": 2.0, "z1": 0.0
    }
  ],
  "building_colors": ["#4C9BE8", "#E8774C", "..."],
  "config": {
    "1": {
      "rot_deg": 0.0, "tz_offset": 0.0, "tx": 10.5, "ty": -5.2
    }
  }
}
```

---

## 2. 教室検索
**エンドポイント:** `GET /api/rooms`
**概要:** 登録されている教室（エッジの `name`）の一覧を返します。建物の指定や、教室名の部分一致での絞り込みが可能です。
`display` は `data/name.csv` で設定した表示名です（未設定の教室は `room` と同じ値）。
**クエリパラメータ:**
- `building` (任意, int): 絞り込む建物のID
- `q` (任意, string): 教室名の部分一致検索（大文字・小文字を区別しない）
**レスポンス例:**
```json
[
  {
    "room": "101A",
    "display": "ゼミ101A",
    "building": 10,
    "floor": 1,
    "edge_id": 5,
    "from": 100005,
    "to": 100006
  }
]
```

---

## 3. 全ノード・全教室・建物一覧の一括取得
**エンドポイント:** `GET /api/all`
**概要:** 検索画面の初期化などで利用できる、全ての教室・ノード・建物のリストをまとめて取得します。
**クエリパラメータ:** なし
**レスポンス例:**
```json
{
  "rooms": [
    {
      "room": "101A", "display": "ゼミ101A", "building": 10, "floor": 1,
      "edge_id": 5, "from": 100005, "to": 100006
    }
  ],
  "nodes": [
    {
      "id": 100001, "building": 10, "floor": 1, "type": 1
    }
  ],
  "buildings": [1, 10]
}
```

---

## 4. 教室への経路探索 (navigate_to_room)
**エンドポイント:** `GET /api/navigate_to_room`
**概要:** 指定した出発点（教室またはノード）から、目的の教室への最短経路を計算して返します。
経路は目的教室エッジの**最寄り端点で止まらず、もう一方の端点まで延長**されます（教室はエッジ区間に面しているため、区間を歩き切る案内になる）。`total_weight` には延長分のweightが加算されます。既に目的エッジを歩いて到着する経路の場合は延長されません。
**クエリパラメータ:**
- **目的地 (必須):**
  - `room` (string): 目的地の教室名
  - `building` (int): 目的地の建物ID
- **出発地 (A, Bのいずれかが必須):**
  - [A] 教室指定: `start_room` (string) & `start_building` (int)
  - [B] ノード指定: `start` (int)
- **オプション:**
  - `use_elevator` (任意, string): `"0"` の場合はエレベーター(type 4)を除外します。省略時は `"1"` (利用する)。
**レスポンス例:**
```json
{
  "path": [100001, 100002, 100005],
  "total_weight": 12.5,
  "path_coords": [
    { "id": 100001, "x": 1.0, "y": 2.0, "z": 0.0 }
  ],
  "path_edges": [
    {
      "from": 100001, "to": 100002,
      "name": "廊下", "length": 5.0,
      "x0": 1.0, "y0": 2.0, "z0": 0.0,
      "x1": 2.0, "y1": 2.0, "z1": 0.0
    }
  ],
  "destination_room": "101A",
  "destination_edge": {
    "id": 5, "name": "101A", "from": 100004, "to": 100005
  },
  "start_room": "Entrance",
  "start_edge": { 
    "id": 1, "name": "Entrance", "from": 100001, "to": 100002
  }
}
```
*(※出発地にノードを指定した場合は `start_room` および `start_edge` は含まれません)*

---

## 5. 統合経路探索 (route)
**エンドポイント:** `GET /api/route`
**概要:** 出発点と目的地をそれぞれ「教室」または「ノードID」で柔軟に指定できる汎用的な経路探索APIです。
目的地が教室の場合、経路は目的教室エッジの**もう一方の端点まで延長**されます（`/api/navigate_to_room` と同じ挙動）。目的地がノードIDの場合は延長されません。出発と目的が同一ノードを共有する場合は距離 0 の自明な経路となりますが、目的地が教室ならそこからエッジ延長が行われるため `path` は 2 ノードになります。
**クエリパラメータ:**
- **出発地 (A〜Cのいずれかが必須):**
  - [A] 教室指定: `from_room` (string) & `from_building` (int)
  - [B] ノード指定: `from_node` (int)
  - [C] イベント指定: `from_event` (string) … `data/event.csv` に登録したタイトル
- **目的地 (A〜Cのいずれかが必須):**
  - [A] 教室指定: `to_room` (string) & `to_building` (int)
  - [B] ノード指定: `to_node` (int)
  - [C] イベント指定: `to_event` (string) … `data/event.csv` に登録したタイトル
- **オプション:**
  - `use_elevator` (任意, string): `"0"` でエレベーター除外。省略時 `"1"`。

イベント指定時は、レスポンスに `from_event` / `to_event`（指定したタイトル）が含まれます。イベントがエッジ（教室・エッジID）に紐づく場合は `from_edge` / `to_edge` も返り、教室と同様に目的エッジのもう一方の端点まで経路が延長されます。ノードに紐づく場合は延長されません。
**レスポンス例:**
```json
{
  "path": [100001, 100002],
  "total_weight": 5.0,
  "path_coords": [ 
    { "id": 100001, "x": 1.0, "y": 2.0, "z": 0.0 },
    { "id": 100002, "x": 2.0, "y": 2.0, "z": 0.0 }
  ],
  "path_edges": [
    {
      "from": 100001, "to": 100002,
      "name": "廊下", "length": 5.0,
      "x0": 1.0, "y0": 2.0, "z0": 0.0,
      "x1": 2.0, "y1": 2.0, "z1": 0.0
    }
  ],
  "from_room": "Entrance",
  "from_edge": { 
    "id": 1, "name": "Entrance", "from": 100001, "to": 100002 
  },
  "to_room": "101A",
  "to_edge": { 
    "id": 5, "name": "101A", "from": 100004, "to": 100005 
  }
}
```

---

## 6. 最寄りトイレ検索
**エンドポイント:** `GET /api/nearest_toilet`
**概要:** 出発点から、指定された種別の最寄りトイレへの最短経路を計算して返します。経路はトイレエッジのもう一方の端点まで延長されます（`/api/navigate_to_room` と同じ挙動）。
**クエリパラメータ:**
- **出発地 (A〜Cのいずれかが必須):**
  - [A] 教室指定: `from_room` (string) & `from_building` (int)
  - [B] ノード指定: `from_node` (int)
  - [C] イベント指定: `from_event` (string) … `data/event.csv` に登録したタイトル
- **トイレ種別:**
  - `type` (任意, string): `"M"` (男子), `"F"` (女子), `"C"` (多目的), `"ALL"` (すべて)。省略時は `"ALL"`。
- **オプション:**
  - `use_elevator` (任意, string): `"0"` でエレベーター除外。省略時 `"1"`。
**レスポンス例:**
```json
{
  "path": [100001, 100003],
  "total_weight": 8.0,
  "path_coords": [ 
    { "id": 100001, "x": 1.0, "y": 2.0, "z": 0.0 },
    { "id": 100003, "x": 3.0, "y": 2.0, "z": 0.0 }
  ],
  "path_edges": [
    {
      "from": 100001, "to": 100003,
      "name": "廊下", "length": 8.0,
      "x0": 1.0, "y0": 2.0, "z0": 0.0,
      "x1": 3.0, "y1": 2.0, "z1": 0.0
    }
  ],
  "toilet_type": "M",
  "toilet_name": "M_Toilet",
  "toilet_label": "男子トイレ",
  "toilet_building": 10,
  "toilet_floor": 1,
  "toilet_edge": { 
    "id": 3, "name": "M_Toilet", "from": 100002, "to": 100003 
  },
  "from_room": "Entrance",
  "from_edge": { 
    "id": 1, "name": "Entrance", "from": 100001, "to": 100002 
  }
}
```

---

## 7. ノード間最短経路探索
**エンドポイント:** `GET /api/shortest_path`
**概要:** 2つのノードIDを直接指定し、それらをつなぐ最短経路を計算する従来仕様のAPIです。
**クエリパラメータ:**
- `start` (必須, int): 出発ノードID
- `goal` (必須, int): 目的ノードID
- `use_elevator` (任意, string): `"0"` でエレベーター除外。省略時 `"1"`。
**レスポンス例:**
```json
{
  "path": [100001, 100002, 100005],
  "total_weight": 12.5,
  "path_coords": [ 
    { "id": 100001, "x": 1.0, "y": 2.0, "z": 0.0 },
    { "id": 100002, "x": 2.0, "y": 2.0, "z": 0.0 },
    { "id": 100005, "x": 5.0, "y": 2.0, "z": 0.0 }
  ],
  "path_edges": [
    {
      "from": 100001, "to": 100002,
      "name": "廊下", "length": 5.0,
      "x0": 1.0, "y0": 2.0, "z0": 0.0,
      "x1": 2.0, "y1": 2.0, "z1": 0.0
    },
    {
      "from": 100002, "to": 100005,
      "name": "廊下", "length": 7.5,
      "x0": 2.0, "y0": 2.0, "z0": 0.0,
      "x1": 5.0, "y1": 2.0, "z1": 0.0
    }
  ]
}
```

---

## 8. エッジ画像マッピング取得
**エンドポイント:** `GET /api/edge_images`
**概要:** エッジ（隣接ノード間）に対応する AR 経路画像の URL マッピングを返します。キー形式は `"fromNodeId_toNodeId"`、値は Cloudflare R2 CDN の完全 URL です。
**クエリパラメータ:** なし
**レスポンス例:**
```json
{
  "1000001_1000002": "https://cdn.iku-navi.net/1000001_to_1000002.jpg",
  "1000002_1000001": "https://cdn.iku-navi.net/1000002_to_1000001.jpg"
}
```
*(※ `data/edge_image.csv` に `from`, `to`, `image_name` が未登録のエッジはキーが含まれません)*

---

## 9. 食堂一覧取得
**エンドポイント:** `GET /api/cafeterias`
**概要:** `data/cafeteria_edge.csv` に登録された食堂の一覧を返します。フロントエンドの食堂検索ドロップダウンの初期化に使用します。
**クエリパラメータ:** なし
**レスポンス例:**
```json
[
  { "name": "Sky_Terrace", "building": "10", "display_name": "スカイテラス" },
  { "name": "SUBWAY",      "building": "10", "display_name": "サブウェイ" }
]
```

---

## 10. 最寄り食堂検索
**エンドポイント:** `GET /api/nearest_cafeteria`
**概要:** 出発点から、指定された食堂（または全食堂）への最短経路を計算して返します。経路は食堂エッジのもう一方の端点まで延長されます（`/api/navigate_to_room` と同じ挙動）。
**クエリパラメータ:**
- **出発地 (A〜Cのいずれかが必須):**
  - [A] 教室指定: `from_room` (string) & `from_building` (int)
  - [B] ノード指定: `from_node` (int)
  - [C] イベント指定: `from_event` (string) … `data/event.csv` に登録したタイトル
- **食堂指定:**
  - `name` (任意, string): 食堂の `name`（`/api/cafeterias` で取得できる値）。省略または `"all"` ですべての食堂を対象に最短を探索。
- **オプション:**
  - `use_elevator` (任意, string): `"0"` でエレベーター除外。省略時 `"1"`。
**レスポンス例:**
```json
{
  "path": [100001, 100002, 100010],
  "total_weight": 20.0,
  "path_coords": [
    { "id": 100001, "x": 1.0, "y": 2.0, "z": 0.0 }
  ],
  "path_edges": [
    {
      "from": 100001, "to": 100010,
      "name": "廊下", "length": 20.0,
      "x0": 1.0, "y0": 2.0, "z0": 0.0,
      "x1": 10.0, "y1": 2.0, "z1": 0.0
    }
  ],
  "cafeteria_building": 10,
  "cafeteria_floor": 1,
  "cafeteria_edge": {
    "id": 20, "name": "Sky_Terrace", "from": 100009, "to": 100010
  },
  "from_room": "101A",
  "from_edge": {
    "id": 1, "name": "101A", "from": 100001, "to": 100002
  }
}
```
*(※出発地にノードを指定した場合は `from_room` および `from_edge` は含まれません)*

---

## 11. イベント一覧取得
**エンドポイント:** `GET /api/events`
**概要:** `data/event.csv` に登録されたイベント（屋台など）の一覧を返します。ナビ画面はイベントモード（`navi/?event=1`）のときだけこのAPIを呼び、イベント名を検索候補に加えます。event.csv が無い・空の場合は `[]` を返します。
**クエリパラメータ:** なし
**レスポンス例:**
```json
[
  { "title": "たこ焼き屋台", "building": 10, "floor": 1 }
]
```