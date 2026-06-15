import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

import '../ar/geo_ar_bridge.dart';
import '../config.dart';
import '../models/graph.dart';

/// 屋外Geo-ARの画面。
///
/// ネイティブの Geospatial AR セッション（PlatformView）を全画面で表示し、
/// 上に測位状態のHUDを重ねる。ネイティブ未実装/非対応の場合はフォールバック表示。
class ArScreen extends StatefulWidget {
  const ArScreen({super.key, required this.graph});

  final GraphData graph;

  @override
  State<ArScreen> createState() => _ArScreenState();
}

class _ArScreenState extends State<ArScreen> {
  bool? _supported;
  String _statusText = 'AR初期化中...';
  StreamSubscription<GeoArStatus>? _statusSub;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    // カメラ権限
    final cam = await Permission.camera.request();
    if (!cam.isGranted) {
      setState(() {
        _supported = false;
        _statusText = 'カメラの許可が必要です';
      });
      return;
    }

    if (AppConfig.arcoreApiKey.isEmpty) {
      setState(() {
        _supported = false;
        _statusText = 'ARCore Geospatial APIキーが未設定です\n'
            '--dart-define=ARCORE_API_KEY=... で渡してください';
      });
      return;
    }

    final ok = await GeoArBridge.isSupported();
    if (!ok) {
      setState(() {
        _supported = false;
        _statusText = 'この端末はGeospatial ARに対応していません';
      });
      return;
    }

    _statusSub = GeoArBridge.statusStream().listen(_onStatus);

    try {
      await GeoArBridge.startSession(
        apiKey: AppConfig.arcoreApiKey,
        graph: widget.graph,
      );
      setState(() {
        _supported = true;
        _statusText = '空を含む周囲を映してください（測位中）';
      });
    } on PlatformException catch (e) {
      setState(() {
        _supported = false;
        _statusText = 'AR開始エラー: ${e.message}';
      });
    }
  }

  void _onStatus(GeoArStatus s) {
    setState(() {
      switch (s.state) {
        case 'tracking':
          final acc = s.horizontalAccuracyM?.toStringAsFixed(1) ?? '?';
          _statusText = '測位完了（誤差 約${acc}m）';
          break;
        case 'localizing':
          _statusText = '測位中... 周囲（建物・空）をゆっくり映してください';
          break;
        case 'unavailable':
          _statusText = 'この場所はVPS未対応です。GPSのみで概略表示します';
          break;
        default:
          _statusText = s.message ?? s.state;
      }
    });
  }

  @override
  void dispose() {
    _statusSub?.cancel();
    GeoArBridge.stopSession();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          if (_supported == true) _buildArView() else _buildFallback(),
          _buildHud(context),
        ],
      ),
    );
  }

  Widget _buildArView() {
    const params = <String, dynamic>{};
    if (Platform.isAndroid) {
      return const AndroidView(
        viewType: GeoArBridge.viewType,
        creationParams: params,
        creationParamsCodec: StandardMessageCodec(),
      );
    } else if (Platform.isIOS) {
      return const UiKitView(
        viewType: GeoArBridge.viewType,
        creationParams: params,
        creationParamsCodec: StandardMessageCodec(),
      );
    }
    return _buildFallback();
  }

  Widget _buildFallback() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.view_in_ar, color: Colors.white54, size: 56),
            const SizedBox(height: 16),
            Text(
              _statusText,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white70, height: 1.6),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHud(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            CircleAvatar(
              backgroundColor: Colors.black54,
              child: IconButton(
                icon: const Icon(Icons.arrow_back, color: Colors.white),
                onPressed: () => Navigator.of(context).maybePop(),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: Colors.black54,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  _statusText,
                  style: const TextStyle(color: Colors.white, fontSize: 13),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
