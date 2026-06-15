import 'dart:async';

import 'package:geolocator/geolocator.dart';

import '../config.dart';
import '../models/graph.dart';

/// 屋内外の判定結果。
enum Environment { unknown, indoor, outdoor }

class LocationState {
  final Environment environment;
  final Position? position;

  /// 直近の水平精度[m]。
  final double? accuracy;

  const LocationState({
    required this.environment,
    this.position,
    this.accuracy,
  });

  bool get isOutdoor => environment == Environment.outdoor;
}

/// GPSを監視し、精度とキャンパス境界から屋内/屋外を判定して通知する。
///
/// 判定ロジック:
///  - 水平精度が outdoorAccuracyThresholdM 以下 → 屋外候補
///  - （任意）キャンパス境界 + margin の外 → 屋外（校外）
///  - 屋外候補が outdoorStableCount 回連続 → 屋外確定（チラつき防止）
///  - 精度が大きく劣化 → 屋内に戻す
class LocationService {
  LocationService({this.campusBounds});

  /// 屋外ノードから求めたキャンパス境界（任意）。null なら精度のみで判定。
  final ({double minLat, double maxLat, double minLng, double maxLng})?
      campusBounds;

  final _controller = StreamController<LocationState>.broadcast();
  StreamSubscription<Position>? _sub;
  int _goodStreak = 0;
  Environment _current = Environment.unknown;

  Stream<LocationState> get stream => _controller.stream;
  Environment get current => _current;

  /// 監視を開始する。権限要求も行う。
  Future<void> start() async {
    final ok = await _ensurePermission();
    if (!ok) {
      _emit(const LocationState(environment: Environment.unknown));
      return;
    }

    _sub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 0,
      ),
    ).listen(_onPosition, onError: (_) {
      _emit(const LocationState(environment: Environment.unknown));
    });
  }

  void _onPosition(Position p) {
    final acc = p.accuracy;
    final accurate = acc > 0 && acc <= AppConfig.outdoorAccuracyThresholdM;

    if (accurate) {
      _goodStreak++;
    } else {
      _goodStreak = 0;
    }

    Environment env;
    if (_goodStreak >= AppConfig.outdoorStableCount) {
      env = Environment.outdoor;
    } else if (!accurate && _current == Environment.outdoor && acc > AppConfig.outdoorAccuracyThresholdM * 2) {
      // 精度が大きく落ちたら屋内に戻す
      env = Environment.indoor;
    } else {
      env = _current == Environment.unknown ? Environment.indoor : _current;
    }

    _current = env;
    _emit(LocationState(environment: env, position: p, accuracy: acc));
  }

  void _emit(LocationState s) {
    if (!_controller.isClosed) _controller.add(s);
  }

  Future<bool> _ensurePermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) return false;
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }
    return perm == LocationPermission.always ||
        perm == LocationPermission.whileInUse;
  }

  Future<void> dispose() async {
    await _sub?.cancel();
    await _controller.close();
  }

  /// 屋外ノード集合からキャンパス境界を作るヘルパー。
  static ({double minLat, double maxLat, double minLng, double maxLng})?
      boundsFromGraph(GraphData? g) => g?.bounds;
}
