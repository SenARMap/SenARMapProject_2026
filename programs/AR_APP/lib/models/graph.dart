/// /api/graph のレスポンスから、屋外ノードと屋外エッジを取り出したモデル。

class GeoNode {
  final int id;
  final double lat;
  final double lng;
  final int building; // 0 = 屋外
  final int floor;

  const GeoNode({
    required this.id,
    required this.lat,
    required this.lng,
    required this.building,
    required this.floor,
  });

  factory GeoNode.fromJson(Map<String, dynamic> j) => GeoNode(
        id: (j['id'] as num).toInt(),
        lat: (j['lat'] as num).toDouble(),
        lng: (j['lng'] as num).toDouble(),
        building: (j['building'] as num?)?.toInt() ?? 0,
        floor: (j['floor'] as num?)?.toInt() ?? 0,
      );
}

class GeoEdge {
  final int fromId;
  final int toId;

  const GeoEdge({required this.fromId, required this.toId});
}

class GraphData {
  /// 屋外ノード（building == 0 かつ lat/lng あり）。
  final List<GeoNode> nodes;

  /// 両端が屋外ノードのエッジ（無向・重複排除済み）。
  final List<GeoEdge> edges;

  const GraphData({required this.nodes, required this.edges});

  bool get isEmpty => nodes.isEmpty;

  /// 全屋外ノードを含む境界ボックス。屋内外判定の補助に使う。
  ({double minLat, double maxLat, double minLng, double maxLng})? get bounds {
    if (nodes.isEmpty) return null;
    var minLat = nodes.first.lat, maxLat = nodes.first.lat;
    var minLng = nodes.first.lng, maxLng = nodes.first.lng;
    for (final n in nodes) {
      if (n.lat < minLat) minLat = n.lat;
      if (n.lat > maxLat) maxLat = n.lat;
      if (n.lng < minLng) minLng = n.lng;
      if (n.lng > maxLng) maxLng = n.lng;
    }
    return (minLat: minLat, maxLat: maxLat, minLng: minLng, maxLng: maxLng);
  }

  /// /api/graph の JSON 全体からモデルを構築する。
  factory GraphData.fromGraphJson(Map<String, dynamic> json) {
    final rawNodes = (json['nodes'] as List? ?? const []);
    final outdoor = <GeoNode>[];
    for (final raw in rawNodes) {
      final m = raw as Map<String, dynamic>;
      final building = (m['building'] as num?)?.toInt() ?? -1;
      if (building != 0) continue;
      if (m['lat'] == null || m['lng'] == null) continue;
      outdoor.add(GeoNode.fromJson(m));
    }

    final byId = {for (final n in outdoor) n.id: n};

    final rawEdges = (json['edges'] as List? ?? const []);
    final seen = <String>{};
    final edges = <GeoEdge>[];
    for (final raw in rawEdges) {
      final m = raw as Map<String, dynamic>;
      final from = (m['from'] as num?)?.toInt();
      final to = (m['to'] as num?)?.toInt();
      if (from == null || to == null) continue;
      if (!byId.containsKey(from) || !byId.containsKey(to)) continue;
      final key = from < to ? '${from}_$to' : '${to}_$from';
      if (!seen.add(key)) continue;
      edges.add(GeoEdge(fromId: from, toId: to));
    }

    return GraphData(nodes: outdoor, edges: edges);
  }
}
