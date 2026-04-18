import os
import pandas as pd
import networkx as nx
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NODE_CSV = os.path.join(BASE_DIR, "node - シート1.csv")
EDGE_CSV = os.path.join(BASE_DIR, "edge - シート1.csv")

# Building color palette (up to 10 buildings)
BUILDING_COLORS = [
    "#4C9BE8", "#E8774C", "#4CE87A", "#E8D44C",
    "#C44CE8", "#4CE8D4", "#E84C7A", "#9BE84C",
    "#E8A44C", "#4C74E8",
]


def load_data():
    nodes_df = pd.read_csv(NODE_CSV)
    edges_df = pd.read_csv(EDGE_CSV)
    nodes_df.columns = nodes_df.columns.str.strip()
    edges_df.columns = edges_df.columns.str.strip()
    # name列が空のエッジは空文字で統一
    edges_df["name"] = edges_df["name"].fillna("").astype(str)
    return nodes_df, edges_df


def build_graph(nodes_df, edges_df):
    G = nx.Graph()
    for _, row in nodes_df.iterrows():
        G.add_node(
            int(row["id"]),
            x=float(row["x"]),
            y=float(row["y"]),
            z=float(row["z"]),
            building=int(row["building"]),
            floor=int(row["floor"]),
            node_type=int(row["type"]),
        )
    for _, row in edges_df.iterrows():
        G.add_edge(
            int(row["from"]),
            int(row["to"]),
            edge_id=int(row["id"]),
            name=str(row["name"]),
            building=int(row["building"]),
            floor=int(row["floor"]),
            weight=float(row["weight"]),
            length=float(row["length"]),
            edge_type=str(row["type"]),
        )
    return G


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
        path_coords.append({"id": node_id, "x": n["x"], "y": n["y"], "z": n["z"]})

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

@app.route("/")
def index():
    nodes_df, edges_df = load_data()
    node_ids  = sorted(nodes_df["id"].tolist())
    buildings = sorted(nodes_df["building"].unique().tolist())
    return render_template("index.html", node_ids=node_ids, buildings=buildings)


@app.route("/api/graph")
def api_graph():
    nodes_df, edges_df = load_data()

    nodes = []
    for _, row in nodes_df.iterrows():
        color_idx = (int(row["building"]) - 1) % len(BUILDING_COLORS)
        nodes.append({
            "id":       int(row["id"]),
            "x":        float(row["x"]),
            "y":        float(row["y"]),
            "z":        float(row["z"]),
            "building": int(row["building"]),
            "floor":    int(row["floor"]),
            "type":     int(row["type"]),
            "color":    BUILDING_COLORS[color_idx],
            "label":    f"Node {int(row['id'])}<br>Building {int(row['building'])} / Floor {int(row['floor'])}",
        })

    edges = [_edge_to_dict(row, nodes_df) for _, row in edges_df.iterrows()]

    return jsonify({"nodes": nodes, "edges": edges, "building_colors": BUILDING_COLORS})


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

    _, edges_df = load_data()

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

    nodes_df, edges_df = load_data()
    G = build_graph(nodes_df, edges_df)

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
                    p = nx.dijkstra_path(G, s_node, g_node, weight="weight")
                    l = nx.dijkstra_path_length(G, s_node, g_node, weight="weight")
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
#  ノード間最短経路 API（従来通り）
# ------------------------------------------------------------------ #

@app.route("/api/shortest_path")
def api_shortest_path():
    start = request.args.get("start", type=int)
    goal  = request.args.get("goal",  type=int)

    if start is None or goal is None:
        return jsonify({"error": "start と goal のノードIDを指定してください"}), 400

    nodes_df, edges_df = load_data()
    G = build_graph(nodes_df, edges_df)

    if start not in G.nodes:
        return jsonify({"error": f"ノード {start} が存在しません"}), 404
    if goal not in G.nodes:
        return jsonify({"error": f"ノード {goal} が存在しません"}), 404

    try:
        path   = nx.dijkstra_path(G, start, goal, weight="weight")
        length = nx.dijkstra_path_length(G, start, goal, weight="weight")
        return jsonify(_path_result(G, path, length))
    except nx.NetworkXNoPath:
        return jsonify({"error": f"ノード {start} から {goal} への経路が見つかりません"}), 404
    except nx.NodeNotFound as e:
        return jsonify({"error": str(e)}), 404


if __name__ == "__main__":
    app.run(debug=True, port=5001)
