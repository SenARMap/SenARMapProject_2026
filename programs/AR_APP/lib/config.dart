/// アプリ全体の設定値。
///
/// 機密値（ARCore Geospatial APIキー）は --dart-define で渡す:
///   flutter run --dart-define=ARCORE_API_KEY=xxxxx
class AppConfig {
  AppConfig._();

  /// WebView で最初に表示するURL（ナビ画面）。
  static const String webUrl = 'https://iku-navi.net/navi/';

  /// API のベースURL。
  static const String apiBase = 'https://iku-navi.net';

  /// 屋外ノード・エッジを取得するエンドポイント。
  static String get graphEndpoint => '$apiBase/api/graph';

  /// ARCore Geospatial API キー（Android）。
  /// 空のときは Geo-AR を起動せず、未設定として扱う。
  static const String arcoreApiKey =
      String.fromEnvironment('ARCORE_API_KEY', defaultValue: '');

  // ---- 屋内外判定のしきい値 -------------------------------------------

  /// この精度[m]以下なら「GPSが安定 = 屋外の可能性が高い」とみなす。
  /// 屋内ではGPS精度が大きく劣化するため、精度で一次判定する。
  static const double outdoorAccuracyThresholdM = 20.0;

  /// キャンパス境界からこの距離[m]以内なら校内とみなす（任意の追加判定）。
  static const double campusMarginM = 150.0;

  /// 屋外判定を確定させるのに必要な連続良好フィックス数（チラつき防止）。
  static const int outdoorStableCount = 3;
}
