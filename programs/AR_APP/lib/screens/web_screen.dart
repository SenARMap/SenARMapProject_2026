import 'dart:async';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../config.dart';
import '../models/graph.dart';
import '../services/graph_api.dart';
import '../services/location_service.dart';
import 'ar_screen.dart';

/// メイン画面。iku-navi.net を WebView で表示しつつ、GPSで屋内外を監視する。
/// 屋外を検知している間だけ「ARで見る」ボタンを表示する。
class WebScreen extends StatefulWidget {
  const WebScreen({super.key});

  @override
  State<WebScreen> createState() => _WebScreenState();
}

class _WebScreenState extends State<WebScreen> {
  late final WebViewController _web;
  final GraphApi _graphApi = GraphApi();
  LocationService? _location;
  StreamSubscription<LocationState>? _locSub;

  LocationState _loc = const LocationState(environment: Environment.unknown);
  bool _loadingWeb = true;

  @override
  void initState() {
    super.initState();
    _initWeb();
    _initLocation();
  }

  void _initWeb() {
    _web = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (_) => setState(() => _loadingWeb = true),
          onPageFinished: (_) => setState(() => _loadingWeb = false),
        ),
      )
      ..loadRequest(Uri.parse(AppConfig.webUrl));
  }

  Future<void> _initLocation() async {
    // 屋外グラフを先読み（キャンパス境界 + AR配置に使う）。失敗しても続行。
    GraphData? graph;
    try {
      graph = await _graphApi.fetch();
    } catch (_) {
      graph = null;
    }

    _location = LocationService(
      campusBounds: LocationService.boundsFromGraph(graph),
    );
    _locSub = _location!.stream.listen((s) {
      if (mounted) setState(() => _loc = s);
    });
    await _location!.start();
  }

  Future<void> _openAr() async {
    GraphData graph;
    try {
      graph = _graphApi.cached ?? await _graphApi.fetch();
    } catch (e) {
      _snack('ARデータの取得に失敗しました: $e');
      return;
    }
    if (graph.isEmpty) {
      _snack('屋外ノードが登録されていません');
      return;
    }
    if (!mounted) return;
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ArScreen(graph: graph)),
    );
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  void dispose() {
    _locSub?.cancel();
    _location?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          WebViewWidget(controller: _web),
          if (_loadingWeb)
            const LinearProgressIndicator(minHeight: 2),
          Positioned(
            left: 12,
            bottom: 12 + MediaQuery.of(context).padding.bottom,
            child: _EnvBadge(loc: _loc),
          ),
        ],
      ),
      floatingActionButton: _loc.isOutdoor
          ? FloatingActionButton.extended(
              onPressed: _openAr,
              icon: const Icon(Icons.view_in_ar),
              label: const Text('ARで見る'),
            )
          : null,
    );
  }
}

/// 現在の屋内外状態を示す小さなバッジ。
class _EnvBadge extends StatelessWidget {
  const _EnvBadge({required this.loc});
  final LocationState loc;

  @override
  Widget build(BuildContext context) {
    final (label, color, icon) = switch (loc.environment) {
      Environment.outdoor => ('屋外', Colors.green, Icons.wb_sunny),
      Environment.indoor => ('屋内', Colors.blueGrey, Icons.meeting_room),
      Environment.unknown => ('測位中', Colors.grey, Icons.gps_not_fixed),
    };
    final acc = loc.accuracy != null ? ' ±${loc.accuracy!.round()}m' : '';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: color.withOpacity(0.9),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white, size: 16),
          const SizedBox(width: 6),
          Text('$label$acc',
              style: const TextStyle(color: Colors.white, fontSize: 12)),
        ],
      ),
    );
  }
}
