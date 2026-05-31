import os
import glob
import json
import math
import re
import pandas as pd
import networkx as nx
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
DATA_DIR        = os.path.join(BASE_DIR, "../../data")
BUILDINGS_JSON  = os.path.join(DATA_DIR, "buildings.json")
CONNECT_EDGE_CSV = os.path.join(DATA_DIR, "connect_edge.csv")
GLOBAL_NODE_CSV  = os.path.join(DATA_DIR, "global_node.csv")
GLOBAL_EDGE_CSV  = os.path.join(DATA_DIR, "global_edge.csv")

# グローバルID = building_id * ID_OFFSET + ローカルID
ID_OFFSET          = 100_000
GLOBAL_NODE_OFFSET = 9_000_000   # 屋外ノードIDのオフセット
OUTDOOR_COLOR      = "#5AFF5A"

# Building color palette (up to 10 buildings)
BUILDING_COLORS = [
    "#4C9BE8", "#E8774C", "#4CE87A", "#E8D44C",
    "#C44CE8", "#4CE8D4", "#E84C7A", "#9BE84C",
    "#E8A44C", "#4C74E8",
]


def _load_transform_config():
    if os.path.exists(BUILDINGS_JSON):
        with open(BUILDINGS_JSON) as f:
            return json.load(f)
    return {}


def _calc_transforms_from_anchors():
    """
    global_node.csv と anchors.csv から各建物の変換パラメータを自動計算する。
    2点アンカー: 回転+平行移動を自動計算。
    1点アンカー: 平行移動のみ自動計算、rot_deg は buildings.json から取得（なければ 0）。
    tz_offset が buildings.json にあれば加算する。
    """
    anchor_path = os.path.join(DATA_DIR, "anchors.csv")

    if not os.path.exists(GLOBAL_NODE_CSV) or not os.path.exists(anchor_path):
        return {}

    gn = pd.read_csv(GLOBAL_NODE_CSV)
    gn.columns = gn.columns.str.strip()
    if gn.empty:
        return {}
    gn = gn.set_index("id")

    anchors = pd.read_csv(anchor_path)
    anchors.columns = anchors.columns.str.strip()
    if anchors.empty:
        return {}

    config = _load_transform_config()
    transforms = {}
    for bldg_id, group in anchors.groupby("building"):
        if len(group) < 1:
            continue

        bldg_cfg = config.get(str(int(bldg_id)), {})
        r0 = group.iloc[0]

        bldg_dir = os.path.join(DATA_DIR, f"{int(bldg_id)}_bldg")
        local_nodes = pd.read_csv(os.path.join(bldg_dir, "node.csv"))
        local_nodes.columns = local_nodes.columns.str.strip()
        local_nodes = local_nodes.set_index("id")

        lx1 = float(local_nodes.loc[int(r0["local_node_id"]), "x"])
        ly1 = float(local_nodes.loc[int(r0["local_node_id"]), "y"])
        lz1 = float(local_nodes.loc[int(r0["local_node_id"]), "z"])

        gx1 = float(gn.loc[int(r0["global_node_id"]), "x"])
        gy1 = float(gn.loc[int(r0["global_node_id"]), "y"])
        gz1 = float(gn.loc[int(r0["global_node_id"]), "z"])

        if len(group) >= 2:
            r1 = group.iloc[1]
            lx2 = float(local_nodes.loc[int(r1["local_node_id"]), "x"])
            ly2 = float(local_nodes.loc[int(r1["local_node_id"]), "y"])
            gx2 = float(gn.loc[int(r1["global_node_id"]), "x"])
            gy2 = float(gn.loc[int(r1["global_node_id"]), "y"])
            θ = math.atan2(gy2 - gy1, gx2 - gx1) - math.atan2(ly2 - ly1, lx2 - lx1)
        else:
            # 1点アンカー: buildings.json の rot_deg を回転として使用
            θ = math.radians(bldg_cfg.get("rot_deg", 0.0))

        cos_θ, sin_θ = math.cos(θ), math.sin(θ)
        tx = gx1 - (cos_θ * lx1 - sin_θ * ly1)
        ty = gy1 - (sin_θ * lx1 + cos_θ * ly1)
        tz = gz1 - lz1 + bldg_cfg.get("tz_offset", 0.0)

        transforms[str(int(bldg_id))] = {
            "tx": tx, "ty": ty, "tz": tz,
            "rot_deg": math.degrees(θ),
        }

    return transforms


def _apply_transform(nodes_df, cfg):
    """変換パラメータをノード座標に適用する"""
    θ  = math.radians(cfg.get("rot_deg", 0.0))
    tx = cfg.get("tx", 0.0)
    ty = cfg.get("ty", 0.0)
    tz = cfg.get("tz", 0.0)
    nodes_df = nodes_df.copy()
    if θ != 0:
        cos_θ, sin_θ = math.cos(θ), math.sin(θ)
        lx, ly = nodes_df["x"].copy(), nodes_df["y"].copy()
        nodes_df["x"] = cos_θ * lx - sin_θ * ly + tx
        nodes_df["y"] = sin_θ * lx + cos_θ * ly + ty
    else:
        nodes_df["x"] += tx
        nodes_df["y"] += ty
    nodes_df["z"] += tz
    return nodes_df


def load_data():
    # buildings.json をベースに、anchors.csv がある建物は自動計算で上書き
    config = _load_transform_config()
    config.update(_calc_transforms_from_anchors())
    all_nodes, all_edges = [], []

    for bldg_dir in sorted(glob.glob(os.path.join(DATA_DIR, "*_bldg"))):
        m = re.match(r'(\d+)_bldg', os.path.basename(bldg_dir))
        if not m:
            continue
        bldg_id = int(m.group(1))

        nodes_df = pd.read_csv(os.path.join(bldg_dir, "node.csv"))
        edges_df = pd.read_csv(os.path.join(bldg_dir, "edge.csv"))
        nodes_df.columns = nodes_df.columns.str.strip()
        edges_df.columns = edges_df.columns.str.strip()

        if nodes_df.empty:
            continue

        # ローカルID → グローバルID (building * ID_OFFSET + local_id)
        offset = bldg_id * ID_OFFSET
        nodes_df["id"]   += offset
        edges_df["id"]   += offset
        edges_df["from"] += offset
        edges_df["to"]   += offset

        # 座標変換 (平行移動 + Z軸回転)
        nodes_df = _apply_transform(nodes_df, config.get(str(bldg_id), {}))

        all_nodes.append(nodes_df)
        all_edges.append(edges_df)

    # 建物間接続CSV: グローバルIDで記述、存在する場合のみ読み込む
    if os.path.exists(CONNECT_EDGE_CSV):
        conn_df = pd.read_csv(CONNECT_EDGE_CSV)
        conn_df.columns = conn_df.columns.str.strip()
        if not conn_df.empty:
            all_edges.append(conn_df)

    # 屋外ノード (global_node.csv) — building=0 として追加
    global_node_ids: set = set()
    if os.path.exists(GLOBAL_NODE_CSV):
        gn_raw = pd.read_csv(GLOBAL_NODE_CSV)
        gn_raw.columns = gn_raw.columns.str.strip()
        gn_raw = gn_raw.dropna(subset=["id", "x", "y", "z"])
        if not gn_raw.empty:
            global_node_ids = set(gn_raw["id"].astype(int))
            gn_raw = gn_raw.copy()
            gn_raw["id"] = gn_raw["id"].astype(int) + GLOBAL_NODE_OFFSET
            gn_raw["building"] = 0
            for col, default in [("floor", 1), ("type", 1)]:
                if col not in gn_raw.columns:
                    gn_raw[col] = default
            all_nodes.append(gn_raw)

    # 屋外エッジ (global_edge.csv) — from/to の小さいIDはグローバルノードローカルID
    if os.path.exists(GLOBAL_EDGE_CSV):
        ge_raw = pd.read_csv(GLOBAL_EDGE_CSV)
        ge_raw.columns = ge_raw.columns.str.strip()
        ge_raw = ge_raw.dropna(subset=["id", "from", "to"])
        if not ge_raw.empty:
            _gni = global_node_ids
            def _resolve(x, _ids=_gni):
                xi = int(x)
                return xi + GLOBAL_NODE_OFFSET if xi in _ids else xi
            ge_raw = ge_raw.copy()
            ge_raw["from"] = ge_raw["from"].astype(int).apply(_resolve)
            ge_raw["to"]   = ge_raw["to"].astype(int).apply(_resolve)
            for col, default in [("building", 0), ("name", ""), ("floor", 1),
                                  ("type", 1), ("weight", 1.0), ("length", 0.0)]:
                if col not in ge_raw.columns:
                    ge_raw[col] = default
            all_edges.append(ge_raw)

    # anchors.csvから、グローバルノードとローカルノードを繋ぐエッジを生成
    anchor_path = os.path.join(DATA_DIR, "anchors.csv")
    if os.path.exists(anchor_path):
        anchors_df = pd.read_csv(anchor_path)
        anchors_df.columns = anchors_df.columns.str.strip()
        if not anchors_df.empty:
            anchor_edges = []
            for idx, row in anchors_df.iterrows():
                bldg_id = int(row["building"])
                l_id = int(row["local_node_id"])
                g_id = int(row["global_node_id"])
                
                local_global_id = bldg_id * ID_OFFSET + l_id
                outdoor_global_id = g_id + GLOBAL_NODE_OFFSET
                
                anchor_edges.append({
                    "id": 8000000 + idx,
                    "from": local_global_id,
                    "to": outdoor_global_id,
                    "building": 0,
                    "floor": 1,
                    "weight": 1.0,
                    "length": 0.0,
                    "type": 1,
                    "name": ""
                })
            if anchor_edges:
                all_edges.append(pd.DataFrame(anchor_edges))

    if not all_nodes:
        return pd.DataFrame(), pd.DataFrame()

    nodes_combined = pd.concat(all_nodes, ignore_index=True)
    edges_combined = pd.concat(all_edges, ignore_index=True)

    # NaN・座標欠損行のみ除外（building=0 = 屋外ノードは許容）
    nodes_combined = nodes_combined.dropna(subset=["id", "x", "y", "z", "building", "floor"])
    valid_ids = set(nodes_combined["id"])
    edges_combined = edges_combined[
        edges_combined["from"].isin(valid_ids) & edges_combined["to"].isin(valid_ids)
    ]

    edges_combined["name"] = edges_combined["name"].fillna("").astype(str)
    # 空行によりfloat化したtype列を整数に正規化 ("1.0" → "1" となるよう)
    edges_combined["type"] = pd.to_numeric(edges_combined["type"], errors="coerce").fillna(1).astype(int)
    return nodes_combined, edges_combined


_DIRECTED_EDGE_TYPES = {"5", "6"}  # 上りエスカレータ(5)・下りエスカレータ(6)は一方向のみ


def build_graph(nodes_df, edges_df, use_elevator=True):
    G = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        node_attrs = dict(
            x=float(row["x"]),
            y=float(row["y"]),
            z=float(row["z"]),
            building=int(row["building"]),
            floor=int(row["floor"]),
            node_type=int(row["type"]),
        )
        if "lat" in row and pd.notna(row["lat"]):
            node_attrs["lat"] = float(row["lat"])
        if "lng" in row and pd.notna(row["lng"]):
            node_attrs["lng"] = float(row["lng"])
        if "svg_x" in row and pd.notna(row["svg_x"]):
            node_attrs["svg_x"] = float(row["svg_x"])
            node_attrs["svg_y"] = float(row["svg_y"])
        G.add_node(int(row["id"]), **node_attrs)
    for _, row in edges_df.iterrows():
        edge_type = str(row["type"]).strip()
        if not use_elevator and edge_type == "4":
            continue
        u, v = int(row["from"]), int(row["to"])
        edge_attrs = dict(
            edge_id=int(row["id"]),
            name=str(row["name"]),
            building=int(row["building"]),
            floor=int(row["floor"]),
            weight=float(row["weight"]) * float(row["length"]),
            length=float(row["length"]),
            edge_type=edge_type,
        )
        if edge_type == "5":
            # 上りESC: z が低い→高い方向のみ通行可
            lo, hi = (u, v) if G.nodes[u]["z"] <= G.nodes[v]["z"] else (v, u)
            G.add_edge(lo, hi, **edge_attrs)
        elif edge_type == "6":
            # 下りESC: z が高い→低い方向のみ通行可
            hi, lo = (u, v) if G.nodes[u]["z"] >= G.nodes[v]["z"] else (v, u)
            G.add_edge(hi, lo, **edge_attrs)
        else:
            G.add_edge(u, v, **edge_attrs)
            if edge_type not in _DIRECTED_EDGE_TYPES:
                G.add_edge(v, u, **edge_attrs)
    return G


# ------------------------------------------------------------------ #
#  Cache Mechanism
# ------------------------------------------------------------------ #
_cached_nodes_df = None
_cached_edges_df = None
_cached_graph_with_ev = None
_cached_graph_without_ev = None

def get_cached_data():
    global _cached_nodes_df, _cached_edges_df
    if _cached_nodes_df is None or _cached_edges_df is None:
        _cached_nodes_df, _cached_edges_df = load_data()
    return _cached_nodes_df, _cached_edges_df

def get_cached_graph(use_elevator=True):
    global _cached_graph_with_ev, _cached_graph_without_ev
    nodes_df, edges_df = get_cached_data()
    if use_elevator:
        if _cached_graph_with_ev is None:
            _cached_graph_with_ev = build_graph(nodes_df, edges_df, use_elevator=True)
        return _cached_graph_with_ev
    else:
        if _cached_graph_without_ev is None:
            _cached_graph_without_ev = build_graph(nodes_df, edges_df, use_elevator=False)
        return _cached_graph_without_ev

def clear_cache():
    global _cached_nodes_df, _cached_edges_df, _cached_graph_with_ev, _cached_graph_without_ev
    _cached_nodes_df = None
    _cached_edges_df = None
    _cached_graph_with_ev = None
    _cached_graph_without_ev = None


def _edge_to_dict(row, nodes_df):
    """edgeの行を座標付きdictに変換するヘルパー"""
    from_node = nodes_df[nodes_df["id"] == int(row["from"])].iloc[0]
    to_node   = nodes_df[nodes_df["id"] == int(row["to"])].iloc[0]
    return {
        "id":       int(row["id"]),
        "name":     str(row["name"]),
        "from":     int(row["from"]),
        "to":       int(row["to"]),
        "building": int(row["building"]),
        "floor":    int(row["floor"]),
        "weight":   float(row["weight"]),
        "length":   float(row["length"]),
        "type":     str(row["type"]),
        "x0": float(from_node["x"]), "y0": float(from_node["y"]), "z0": float(from_node["z"]),
        "x1": float(to_node["x"]),   "y1": float(to_node["y"]),   "z1": float(to_node["z"]),
    }


def _path_result(G, path, length):
    """Dijkstraの結果をJSON用dictに整形するヘルパー"""
    path_coords = []
    for node_id in path:
        n = G.nodes[node_id]
        coord_dict = {"id": node_id, "x": n["x"], "y": n["y"], "z": n["z"],
                      "building": n["building"], "floor": n["floor"]}
        if "lat" in n:
            coord_dict["lat"] = n["lat"]
        if "lng" in n:
            coord_dict["lng"] = n["lng"]
        if "svg_x" in n and n["svg_x"] == n["svg_x"]:  # NaN check
            coord_dict["svg_x"] = n["svg_x"]
            coord_dict["svg_y"] = n["svg_y"]
        path_coords.append(coord_dict)

    path_edges = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edata = G.edges[u, v]
        n0, n1 = G.nodes[u], G.nodes[v]
        path_edges.append({
            "from": u, "to": v,
            "name":   edata.get("name", ""),
            "length": edata.get("length", 0),
            "x0": n0["x"], "y0": n0["y"], "z0": n0["z"],
            "x1": n1["x"], "y1": n1["y"], "z1": n1["z"],
        })
    return {"path": path, "total_weight": length,
            "path_coords": path_coords, "path_edges": path_edges}


# ------------------------------------------------------------------ #
#  Routes
# ------------------------------------------------------------------ #

@app.route("/3d/viewer")
def viewer():
    return render_template("viewer.html")


@app.route("/3d/")
@app.route("/3d")
def index():
    nodes_df, edges_df = get_cached_data()
    node_ids  = sorted(nodes_df["id"].tolist())
    buildings = sorted(nodes_df["building"].unique().tolist())
    return render_template("index.html", node_ids=node_ids, buildings=buildings)


@app.route("/api/graph")
def api_graph():
    nodes_df, edges_df = get_cached_data()

    nodes = []
    for _, row in nodes_df.iterrows():
        if any(pd.isna(row[c]) for c in ["id", "x", "y", "z", "building", "floor"]):
            continue
        bldg = int(row["building"])
        if bldg == 0:
            color = OUTDOOR_COLOR
        else:
            color = BUILDING_COLORS[(bldg - 1) % len(BUILDING_COLORS)]
        node_dict = {
            "id":       int(row["id"]),
            "x":        float(row["x"]),
            "y":        float(row["y"]),
            "z":        float(row["z"]),
            "building": bldg,
            "floor":    int(row["floor"]),
            "type":     int(row["type"]),
            "color":    color,
            "label":    f"Node {int(row['id'])}<br>{'屋外' if bldg == 0 else f'Building {bldg}'} / Floor {int(row['floor'])}",
        }
        if "lat" in row and pd.notna(row["lat"]):
            node_dict["lat"] = float(row["lat"])
        if "lng" in row and pd.notna(row["lng"]):
            node_dict["lng"] = float(row["lng"])
        nodes.append(node_dict)

    valid_edges = edges_df.dropna(subset=["id", "from", "to", "building", "floor", "weight", "length"])
    edges = [_edge_to_dict(row, nodes_df) for _, row in valid_edges.iterrows()]

    config = _load_transform_config()
    config.update(_calc_transforms_from_anchors())

    return jsonify({"nodes": nodes, "edges": edges, "building_colors": BUILDING_COLORS, "config": config})


# ------------------------------------------------------------------ #
#  教室検索 API
# ------------------------------------------------------------------ #

@app.route("/api/rooms")
def api_rooms():
    """
    教室名の一覧を返す。
    ?building=10  建物IDで絞り込み（省略時は全建物）
    ?q=101        前方一致の絞り込み（省略時は全件）
    返却形式: [ { "room": "101A", "building": 10, "edge_id": 5, "floor": 1 }, ... ]
    """
    building_filter = request.args.get("building", type=int)
    query           = request.args.get("q", "").strip().lower()

    _, edges_df = get_cached_data()

    rooms = []
    seen  = set()  # 重複排除 (room + building)

    for _, row in edges_df.iterrows():
        if building_filter and int(row["building"]) != building_filter:
            continue
        raw_name = str(row["name"]).strip()
        if not raw_name or raw_name == "nan":
            continue
        for room in raw_name.split(";"):
            room = room.strip()
            if not room:
                continue
            if query and query not in room.lower():
                continue
            key = (room, int(row["building"]))
            if key in seen:
                continue
            seen.add(key)
            rooms.append({
                "room":     room,
                "building": int(row["building"]),
                "floor":    int(row["floor"]),
                "edge_id":  int(row["id"]),
                "from":     int(row["from"]),
                "to":       int(row["to"]),
            })

    rooms.sort(key=lambda r: (r["building"], r["room"]))
    return jsonify(rooms)


@app.route("/api/all")
def api_all():
    """
    全教室・全ノード・建物一覧をまとめて返す。パラメータなし。
    返却形式:
      {
        "rooms":     [ { "room", "building", "floor", "edge_id", "from", "to" }, ... ],
        "nodes":     [ { "id", "building", "floor", "type" }, ... ],
        "buildings": [ 1, 2, ... ]
      }
    """
    nodes_df, edges_df = get_cached_data()

    rooms = []
    seen = set()
    for _, row in edges_df.iterrows():
        raw_name = str(row["name"]).strip()
        if not raw_name or raw_name == "nan":
            continue
        for room in raw_name.split(";"):
            room = room.strip()
            if not room:
                continue
            key = (room, int(row["building"]))
            if key in seen:
                continue
            seen.add(key)
            rooms.append({
                "room":     room,
                "building": int(row["building"]),
                "floor":    int(row["floor"]),
                "edge_id":  int(row["id"]),
                "from":     int(row["from"]),
                "to":       int(row["to"]),
            })
    rooms.sort(key=lambda r: (r["building"], r["room"]))

    nodes = []
    for _, row in nodes_df.iterrows():
        if any(pd.isna(row[c]) for c in ["id", "building", "floor", "type"]):
            continue
        nd = {
            "id":       int(row["id"]),
            "building": int(row["building"]),
            "floor":    int(row["floor"]),
            "type":     int(row["type"]),
        }
        if "lat" in row and pd.notna(row["lat"]):
            nd["lat"] = float(row["lat"])
        if "lng" in row and pd.notna(row["lng"]):
            nd["lng"] = float(row["lng"])
        nodes.append(nd)
    nodes.sort(key=lambda n: n["id"])

    buildings = sorted(nodes_df["building"].dropna().astype(int).unique().tolist())

    return jsonify({"rooms": rooms, "nodes": nodes, "buildings": buildings})


def _find_edges_for_room(edges_df, room_name, building):
    """教室名が含まれるエッジ行のリストを返す"""
    matched = []
    for _, row in edges_df.iterrows():
        if int(row["building"]) != building:
            continue
        if room_name in [r.strip() for r in str(row["name"]).split(";")]:
            matched.append(row)
    return matched


@app.route("/api/navigate_to_room")
def api_navigate_to_room():
    """
    教室名から教室名への最短経路を返す。

    出発点の指定方法（いずれか）:
      A) start_room=101A&start_building=10  ← 出発教室名
      B) start=1                            ← 出発ノードID（後方互換）

    必須:
      room=101A&building=10  ← 目的教室名

    教室はエッジの属性なので、各教室エッジの両端点を候補ノードとし、
    全組み合わせ中で最短のパスを採用する。
    レスポンスには経路情報に加え start_edge / destination_edge も含む。
    """
    room_name      = request.args.get("room",           "").strip()
    building       = request.args.get("building",       type=int)
    start_room     = request.args.get("start_room",     "").strip()
    start_building = request.args.get("start_building", type=int)
    start_node     = request.args.get("start",          type=int)  # 後方互換

    if not room_name or building is None:
        return jsonify({"error": "room と building を指定してください"}), 400
    if not start_room and start_node is None:
        return jsonify({"error": "start_room（＋start_building）または start を指定してください"}), 400

    use_elevator = request.args.get("use_elevator", "1") != "0"
    nodes_df, edges_df = get_cached_data()
    G = get_cached_graph(use_elevator=use_elevator)

    # --- 目的教室のエッジを検索 ---
    dest_edges = _find_edges_for_room(edges_df, room_name, building)
    if not dest_edges:
        return jsonify({"error": f"建物 {building} に教室 '{room_name}' が見つかりません"}), 404

    # --- 出発点の候補ノードを決定 ---
    start_candidates = []  # (node_id, start_edge_row or None)
    start_edge_row = None

    if start_room and start_building is not None:
        s_edges = _find_edges_for_room(edges_df, start_room, start_building)
        if not s_edges:
            return jsonify({"error": f"建物 {start_building} に出発教室 '{start_room}' が見つかりません"}), 404
        for row in s_edges:
            for nid in (int(row["from"]), int(row["to"])):
                if nid in G.nodes:
                    start_candidates.append((nid, row))
    else:
        # ノードID指定（後方互換）
        if start_node not in G.nodes:
            return jsonify({"error": f"ノード {start_node} が存在しません"}), 404
        start_candidates = [(start_node, None)]

    # --- 全組み合わせでDijkstra、最短を採用 ---
    best_path   = None
    best_length = float("inf")
    best_dest_edge   = None
    best_start_edge  = None

    for (s_node, s_edge_row) in start_candidates:
        for d_row in dest_edges:
            for g_node in (int(d_row["from"]), int(d_row["to"])):
                if g_node not in G.nodes:
                    continue
                try:
                    l, p = nx.bidirectional_dijkstra(G, s_node, g_node, weight="weight")
                    if l < best_length:
                        best_length     = l
                        best_path       = p
                        best_dest_edge  = d_row
                        best_start_edge = s_edge_row
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue

    if best_path is None:
        label = f"'{start_room}'" if start_room else f"ノード {start_node}"
        return jsonify({"error": f"{label} から教室 '{room_name}' への経路が見つかりません"}), 404

    result = _path_result(G, best_path, best_length)
    result["destination_room"] = room_name
    result["destination_edge"] = _edge_to_dict(best_dest_edge, nodes_df)
    if best_start_edge is not None:
        result["start_room"] = start_room
        result["start_edge"] = _edge_to_dict(best_start_edge, nodes_df)
    return jsonify(result)


# ------------------------------------------------------------------ #
#  統合ルーティング API
# ------------------------------------------------------------------ #

@app.route("/api/route")
def api_route():
    """
    出発点と目的地を指定して最短経路をJSONで返す。

    出発点（いずれか）:
      from_room=101A&from_building=10  ← 教室名
      from_node=100001                 ← ノードID

    目的地（いずれか）:
      to_room=202B&to_building=10      ← 教室名
      to_node=100050                   ← ノードID

    条件:
      use_elevator=0/1  （省略時 1）
    """
    use_elevator = request.args.get("use_elevator", "1") != "0"

    from_room     = request.args.get("from_room",     "").strip()
    from_building = request.args.get("from_building", type=int)
    from_node_id  = request.args.get("from_node",     type=int)

    to_room       = request.args.get("to_room",       "").strip()
    to_building   = request.args.get("to_building",   type=int)
    to_node_id    = request.args.get("to_node",       type=int)

    if not from_room and from_node_id is None:
        return jsonify({"error": "from_room（＋from_building）または from_node を指定してください"}), 400
    if not to_room and to_node_id is None:
        return jsonify({"error": "to_room（＋to_building）または to_node を指定してください"}), 400

    nodes_df, edges_df = get_cached_data()
    G = get_cached_graph(use_elevator=use_elevator)

    # --- 出発候補ノード ---
    if from_room:
        if from_building is None:
            return jsonify({"error": "from_building を指定してください"}), 400
        s_edges = _find_edges_for_room(edges_df, from_room, from_building)
        if not s_edges:
            return jsonify({"error": f"建物 {from_building} に教室 '{from_room}' が見つかりません"}), 404
        seen_s = set()
        start_candidates = []
        for r in s_edges:
            for nid in (int(r["from"]), int(r["to"])):
                if nid in G.nodes and nid not in seen_s:
                    seen_s.add(nid)
                    start_candidates.append((nid, r))
    else:
        if from_node_id not in G.nodes:
            return jsonify({"error": f"ノード {from_node_id} が存在しません"}), 404
        start_candidates = [(from_node_id, None)]

    # --- 目的候補ノード ---
    if to_room:
        if to_building is None:
            return jsonify({"error": "to_building を指定してください"}), 400
        d_edges = _find_edges_for_room(edges_df, to_room, to_building)
        if not d_edges:
            return jsonify({"error": f"建物 {to_building} に教室 '{to_room}' が見つかりません"}), 404
        dest_candidates = [(nid, r) for r in d_edges
                           for nid in (int(r["from"]), int(r["to"]))
                           if nid in G.nodes]
    else:
        if to_node_id not in G.nodes:
            return jsonify({"error": f"ノード {to_node_id} が存在しません"}), 404
        dest_candidates = [(to_node_id, None)]

    # --- 全組み合わせでDijkstra、最短を採用 ---
    best_path, best_length = None, float("inf")
    best_start_edge = best_dest_edge = None

    for (s_node, s_row) in start_candidates:
        for (d_node, d_row) in dest_candidates:
            if s_node == d_node:
                continue
            try:
                l, p = nx.bidirectional_dijkstra(G, s_node, d_node, weight="weight")
                if l < best_length:
                    best_length, best_path = l, p
                    best_start_edge, best_dest_edge = s_row, d_row
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

    if best_path is None:
        return jsonify({"error": "指定された出発点から目的地への経路が見つかりません"}), 404

    result = _path_result(G, best_path, best_length)
    if best_start_edge is not None:
        result["from_room"]  = from_room
        result["from_edge"]  = _edge_to_dict(best_start_edge, nodes_df)
    if best_dest_edge is not None:
        result["to_room"]    = to_room
        result["to_edge"]    = _edge_to_dict(best_dest_edge, nodes_df)
    return jsonify(result)


# ------------------------------------------------------------------ #
#  最寄りトイレ検索 API
# ------------------------------------------------------------------ #

_TOILET_TYPE_MAP = {
    "M":   ["M_Toilet"],
    "F":   ["F_Toilet"],
    "C":   ["C_Toilet"],
    "ALL": ["M_Toilet", "F_Toilet", "C_Toilet"],
}
_TOILET_LABEL = {"M_Toilet": "男子トイレ", "F_Toilet": "女子トイレ", "C_Toilet": "多目的トイレ"}


@app.route("/api/nearest_toilet")
def api_nearest_toilet():
    """
    最寄りのトイレへの最短経路を返す。

    出発点（いずれか）:
      from_room=101A&from_building=10
      from_node=100001

    種別:
      type=M / F / C / all (省略時 all)

    条件:
      use_elevator=0/1 (省略時 1)
    """
    toilet_type  = request.args.get("type", "all").strip().upper()
    use_elevator = request.args.get("use_elevator", "1") != "0"
    from_room     = request.args.get("from_room",     "").strip()
    from_building = request.args.get("from_building", type=int)
    from_node_id  = request.args.get("from_node",     type=int)

    if not from_room and from_node_id is None:
        return jsonify({"error": "from_room（＋from_building）または from_node を指定してください"}), 400

    targets = _TOILET_TYPE_MAP.get(toilet_type, _TOILET_TYPE_MAP["ALL"])

    nodes_df, edges_df = get_cached_data()
    G = get_cached_graph(use_elevator=use_elevator)

    # 出発候補
    if from_room:
        if from_building is None:
            return jsonify({"error": "from_building を指定してください"}), 400
        s_edges = _find_edges_for_room(edges_df, from_room, from_building)
        if not s_edges:
            return jsonify({"error": f"建物 {from_building} に教室 '{from_room}' が見つかりません"}), 404
        seen_s = set()
        start_candidates = []
        for r in s_edges:
            for nid in (int(r["from"]), int(r["to"])):
                if nid in G.nodes and nid not in seen_s:
                    seen_s.add(nid)
                    start_candidates.append((nid, r))
    else:
        if from_node_id not in G.nodes:
            return jsonify({"error": f"ノード {from_node_id} が存在しません"}), 404
        start_candidates = [(from_node_id, None)]

    # トイレエッジを全建物から収集
    toilet_edges = []
    for _, row in edges_df.iterrows():
        names = [n.strip() for n in str(row["name"]).split(";")]
        if any(t in names for t in targets):
            toilet_edges.append(row)

    if not toilet_edges:
        return jsonify({"error": "該当するトイレがデータ内に見つかりません"}), 404

    dest_candidates = [
        (nid, row) for row in toilet_edges
        for nid in (int(row["from"]), int(row["to"]))
        if nid in G.nodes
    ]

    # 全組み合わせでDijkstra、最短を採用
    best_path, best_length = None, float("inf")
    best_start_row = best_toilet_row = None

    for (s_node, s_row) in start_candidates:
        for (d_node, d_row) in dest_candidates:
            if s_node == d_node:
                continue
            try:
                l, p = nx.bidirectional_dijkstra(G, s_node, d_node, weight="weight")
                if l < best_length:
                    best_length, best_path = l, p
                    best_start_row, best_toilet_row = s_row, d_row
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

    if best_path is None:
        return jsonify({"error": "指定された出発点から該当するトイレへの経路が見つかりません"}), 404

    t_names = [n.strip() for n in str(best_toilet_row["name"]).split(";")]
    found_key = next((t for t in ["M_Toilet", "F_Toilet", "C_Toilet"] if t in t_names), "")

    result = _path_result(G, best_path, best_length)
    result["toilet_type"]     = found_key.split("_")[0] if found_key else ""
    result["toilet_name"]     = found_key
    result["toilet_label"]    = _TOILET_LABEL.get(found_key, "トイレ")
    result["toilet_building"] = int(best_toilet_row["building"])
    result["toilet_floor"]    = int(best_toilet_row["floor"])
    result["toilet_edge"]     = _edge_to_dict(best_toilet_row, nodes_df)
    if best_start_row is not None:
        result["from_room"]   = from_room
        result["from_edge"]   = _edge_to_dict(best_start_row, nodes_df)
    return jsonify(result)


# ------------------------------------------------------------------ #
#  ノード間最短経路 API（従来通り）
# ------------------------------------------------------------------ #

@app.route("/api/shortest_path")
def api_shortest_path():
    start = request.args.get("start", type=int)
    goal  = request.args.get("goal",  type=int)

    if start is None or goal is None:
        return jsonify({"error": "start と goal のノードIDを指定してください"}), 400

    use_elevator = request.args.get("use_elevator", "1") != "0"
    nodes_df, edges_df = get_cached_data()
    G = get_cached_graph(use_elevator=use_elevator)

    if start not in G.nodes:
        return jsonify({"error": f"ノード {start} が存在しません"}), 404
    if goal not in G.nodes:
        return jsonify({"error": f"ノード {goal} が存在しません"}), 404

    try:
        length, path = nx.bidirectional_dijkstra(G, start, goal, weight="weight")
        return jsonify(_path_result(G, path, length))
    except nx.NetworkXNoPath:
        return jsonify({"error": f"ノード {start} から {goal} への経路が見つかりません"}), 404
    except nx.NodeNotFound as e:
        return jsonify({"error": str(e)}), 404


# ------------------------------------------------------------------ #
#  建物変換パラメータ API
# ------------------------------------------------------------------ #

@app.route("/api/building_config", methods=["GET"])
def api_building_config_get():
    """全建物の rot_deg / tz_offset を返す"""
    config = _load_transform_config()
    nodes_df, _ = get_cached_data()
    buildings = sorted(
        nodes_df[nodes_df["building"].astype(int) != 0]["building"]
        .dropna().astype(int).unique().tolist()
    )
    result = {}
    for b in buildings:
        cfg = config.get(str(b), {})
        result[b] = {
            "rot_deg":   cfg.get("rot_deg",   0.0),
            "tz_offset": cfg.get("tz_offset", 0.0),
            "tx":        cfg.get("tx",        0.0),
            "ty":        cfg.get("ty",        0.0),
        }
    return jsonify(result)


@app.route("/api/building_config/<int:building_id>", methods=["POST"])
def api_building_config_post(building_id):
    """建物の rot_deg / tz_offset を buildings.json に保存する"""
    data = request.get_json(force=True)
    config = _load_transform_config()
    cfg = config.get(str(building_id), {})
    if "rot_deg"   in data:
        cfg["rot_deg"]   = float(data["rot_deg"])
    if "tz_offset" in data:
        cfg["tz_offset"] = float(data["tz_offset"])
    config[str(building_id)] = cfg
    with open(BUILDINGS_JSON, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    clear_cache()
    return jsonify({"ok": True, "building": building_id, "config": cfg})


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0" , port=5001)
