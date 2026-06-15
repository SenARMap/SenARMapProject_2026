import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';
import '../models/graph.dart';

/// /api/graph から屋外グラフを取得する。
class GraphApi {
  /// 取得済みデータをキャッシュ（毎回叩かない）。
  GraphData? _cache;

  GraphData? get cached => _cache;

  Future<GraphData> fetch({bool force = false}) async {
    if (!force && _cache != null) return _cache!;
    final res = await http
        .get(Uri.parse(AppConfig.graphEndpoint))
        .timeout(const Duration(seconds: 15));
    if (res.statusCode != 200) {
      throw Exception('graph取得失敗: HTTP ${res.statusCode}');
    }
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final data = GraphData.fromGraphJson(json);
    _cache = data;
    return data;
  }
}
