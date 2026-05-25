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
**クエリパラメータ:**
- `building` (任意, int): 絞り込む建物のID
- `q` (任意, string): 教室名の部分一致検索（大文字・小文字を区別しない）
**レスポンス例:**
```json
[
  {
    "room": "101A",
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
      "room": "101A", "building": 10, "floor": 1,
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
**クエリパラメータ:**
- **出発地 (A, Bのいずれかが必須):**
  - [A] 教室指定: `from_room` (string) & `from_building` (int)
  - [B] ノード指定: `from_node` (int)
- **目的地 (A, Bのいずれかが必須):**
  - [A] 教室指定: `to_room` (string) & `to_building` (int)
  - [B] ノード指定: `to_node` (int)
- **オプション:**
  - `use_elevator` (任意, string): `"0"` でエレベーター除外。省略時 `"1"`。
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
**概要:** 出発点から、指定された種別の最寄りトイレへの最短経路を計算して返します。
**クエリパラメータ:**
- **出発地 (A, Bのいずれかが必須):**
  - [A] 教室指定: `from_room` (string) & `from_building` (int)
  - [B] ノード指定: `from_node` (int)
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

## 8. 建物変換パラメータ取得
**エンドポイント:** `GET /api/building_config`
**概要:** すべての建物の座標変換パラメータ（回転、Z軸オフセット等）を取得します。
**クエリパラメータ:** なし
**レスポンス例:**
```json
{
  "1": {
    "rot_deg": 0.0,
    "tz_offset": 0.0,
    "tx": 10.0,
    "ty": 20.0
  },
  "10": {
    "rot_deg": 90.0,
    "tz_offset": 1.5,
    "tx": 0.0,
    "ty": 0.0
  }
}
```

---

## 9. 建物変換パラメータ更新
**エンドポイント:** `POST /api/building_config/<int:building_id>`
**概要:** 指定した建物IDの変換パラメータ（回転、Z軸オフセット）を更新し、`buildings.json` に保存します。更新後はキャッシュがクリアされます。
**パスパラメータ:**
- `building_id` (必須, int): 対象の建物ID
**リクエストボディ (JSON形式):**
```json
{
  "rot_deg": 45.0,
  "tz_offset": -1.0
}
```
*(※更新したい項目のみの指定で構いません)*
**レスポンス例:**
```json
{
  "ok": true,
  "building": 10,
  "config": {
    "rot_deg": 45.0,
    "tz_offset": -1.0,
    "tx": 0.0,
    "ty": 0.0
  }
}
```