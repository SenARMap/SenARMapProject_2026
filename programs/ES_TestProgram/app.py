from flask import Flask, render_template, request
import networkx as nx
import pandas as pd
import plotly.graph_objects as go

app = Flask(__name__)

# =========================
# データの事前読み込み
# =========================
df_nodes = pd.read_csv("nodes.csv")
df_edges = pd.read_csv("edge.csv")

G = nx.Graph()
pos_3d = {}

# ノードの読み込み (XYZ座標を復活！)
for _, row in df_nodes.iterrows():
    node_id = str(row['id'])
    pos_3d[node_id] = (row['x'], row['y'], row['z'])
    G.add_node(node_id)

# エッジの読み込み
for _, row in df_edges.iterrows():
    src, dst = str(row['source']), str(row['target'])
    w_val = row['weight']
    G.add_edge(src, dst, weight=w_val)

# =========================
# グラフ生成関数 (3Dモダンマップ版)
# =========================
def generate_graph_html(start_node=None, goal_node=None):
    path = []
    error_msg = ""

    # 1. 最短経路の計算
    if start_node and goal_node:
        try:
            path = nx.dijkstra_path(G, start_node, goal_node, weight='weight')
        except nx.NetworkXNoPath:
            error_msg = f"経路が見つかりません: {start_node} -> {goal_node}"
        except nx.NodeNotFound:
            error_msg = f"指定されたノードが存在しません。"

    path_edges = list(zip(path, path[1:])) if path else []

    # 2. Plotly用のデータ作成
    edge_x, edge_y, edge_z = [], [], []
    for u, v in G.edges():
        x0, y0, z0 = pos_3d[u]
        x1, y1, z1 = pos_3d[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        edge_z.extend([z0, z1, None])

    # 通常のエッジ（薄いグレー）
    edge_trace = go.Scatter3d(
        x=edge_x, y=edge_y, z=edge_z,
        mode='lines',
        line=dict(color='#cccccc', width=2),
        hoverinfo='none'
    )

    path_x, path_y, path_z = [], [], []
    for u, v in path_edges:
        x0, y0, z0 = pos_3d[u]
        x1, y1, z1 = pos_3d[v]
        path_x.extend([x0, x1, None])
        path_y.extend([y0, y1, None])
        path_z.extend([z0, z1, None])

    # 最短経路のエッジ（太い赤）
    path_trace = go.Scatter3d(
        x=path_x, y=path_y, z=path_z,
        mode='lines',
        line=dict(color='#ff4b4b', width=8),
        hoverinfo='none'
    )

    node_x, node_y, node_z, node_text, node_color, node_size = [], [], [], [], [], []
    for node in G.nodes():
        x, y, z = pos_3d[node]
        node_x.append(x)
        node_y.append(y)
        node_z.append(z)
        node_text.append(node)
        
        # 経路上のノードは赤く大きく、それ以外は青く小さく
        if node in path:
            node_color.append('#ff4b4b')
            node_size.append(8)
        else:
            node_color.append('#97c2fc')
            node_size.append(5)

    node_trace = go.Scatter3d(
        x=node_x, y=node_y, z=node_z,
        mode='markers+text',
        text=node_text,
        textposition='top center',
        marker=dict(size=node_size, color=node_color),
        textfont=dict(color='#333333', size=11),
        hoverinfo='text'
    )

    fig = go.Figure(data=[edge_trace, path_trace, node_trace])

    # ★ここが最大のキモ：グラフ感を消して「空間」にする設定
    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        scene=dict(
            # X, Y, Zの軸、グリッド、背景の壁などをすべて非表示！
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title='', showbackground=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title='', showbackground=False, visible=False),
            zaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title='', showbackground=False, visible=False),
            # XYZの実際の距離比率を維持する（変に伸び縮みしない）
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        showlegend=False,
        hovermode='closest'
    )

    # HTML出力 (iframeが不要になる設定)
    graph_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    return graph_html, error_msg, path

# =========================
# Flaskのルーティング
# =========================
@app.route('/', methods=['GET', 'POST'])
def index():
    start_node = ""
    goal_node = ""
    graph_html = ""
    error_msg = ""
    path = []

    node_list = sorted(list(G.nodes()))

    if request.method == 'POST':
        start_node = request.form.get('start_node', '').strip()
        goal_node = request.form.get('goal_node', '').strip()

    graph_html, error_msg, path = generate_graph_html(start_node, goal_node)

    path_text = " → ".join(path) if path else ""

    return render_template(
        'index.html',
        graph_html=graph_html,
        start_node=start_node,
        goal_node=goal_node,
        error_msg=error_msg,
        node_list=node_list,
        path_text=path_text
    )

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5001)