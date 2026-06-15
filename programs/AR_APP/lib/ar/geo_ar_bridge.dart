import 'package:flutter/services.dart';

import '../models/graph.dart';

/// ネイティブの Geospatial AR セッション（Android: ARCore Geospatial API /
/// iOS: ARKit + ARGeoTrackingConfiguration）と Flutter を繋ぐブリッジ。
///
/// ネイティブ側で以下を実装する（README参照）:
///   - MethodChannel  "iku_navi/geo_ar"
///   - EventChannel   "iku_navi/geo_ar/events"
///   - PlatformView   "iku_navi/geo_ar_view"  （ARカメラ描画面）
class GeoArBridge {
  static const MethodChannel _method = MethodChannel('iku_navi/geo_ar');
  static const EventChannel _events = EventChannel('iku_navi/geo_ar/events');

  /// PlatformView の viewType。ar_screen の AndroidView/UiKitView から使う。
  static const String viewType = 'iku_navi/geo_ar_view';

  /// 端末が Geospatial AR に対応しているか（ARCore対応 + VPS利用可能か等）。
  static Future<bool> isSupported() async {
    try {
      final ok = await _method.invokeMethod<bool>('isSupported');
      return ok ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false; // ネイティブ未実装
    }
  }

  /// Geospatial セッションを開始し、屋外ノード・エッジをジオアンカーとして渡す。
  ///
  /// ノードは lat/lng のみ渡し、高度はネイティブ側の Terrain Anchor
  /// （地表高を自動解決）で配置する想定。
  static Future<void> startSession({
    required String apiKey,
    required GraphData graph,
  }) async {
    final payload = {
      'apiKey': apiKey,
      'nodes': [
        for (final n in graph.nodes)
          {'id': n.id, 'lat': n.lat, 'lng': n.lng},
      ],
      'edges': [
        for (final e in graph.edges) {'from': e.fromId, 'to': e.toId},
      ],
    };
    await _method.invokeMethod('startSession', payload);
  }

  static Future<void> stopSession() async {
    try {
      await _method.invokeMethod('stopSession');
    } on PlatformException {
      // セッション未開始でも握りつぶす
    }
  }

  /// 測位・トラッキング状態の通知ストリーム。
  /// ネイティブからは {state, accuracyHorizontal, accuracyHeading, ...} を流す。
  static Stream<GeoArStatus> statusStream() {
    return _events.receiveBroadcastStream().map((e) {
      final m = (e as Map).cast<String, dynamic>();
      return GeoArStatus.fromMap(m);
    });
  }
}

/// ネイティブから流れてくる Geospatial の測位状態。
class GeoArStatus {
  /// "tracking" / "localizing" / "unavailable" / "error" など。
  final String state;
  final double? horizontalAccuracyM;
  final double? headingAccuracyDeg;
  final String? message;

  const GeoArStatus({
    required this.state,
    this.horizontalAccuracyM,
    this.headingAccuracyDeg,
    this.message,
  });

  bool get isTracking => state == 'tracking';

  factory GeoArStatus.fromMap(Map<String, dynamic> m) => GeoArStatus(
        state: (m['state'] as String?) ?? 'unknown',
        horizontalAccuracyM: (m['accuracyHorizontal'] as num?)?.toDouble(),
        headingAccuracyDeg: (m['accuracyHeading'] as num?)?.toDouble(),
        message: m['message'] as String?,
      );
}
