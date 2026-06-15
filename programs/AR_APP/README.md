# IKU NAVI AR （Flutter ハイブリッドアプリ）

`iku-navi.net` を WebView で表示し、**GPSで屋外を検知したときだけ**高精度な
ジオAR（ARCore Geospatial API / ARKit Geo-tracking）を起動するハイブリッドアプリ。

屋内は従来どおり Web のナビ（写真ベース）を使い、屋外は端末ネイティブの
Geospatial AR で「ノードと経路の線」を実風景に正確に重ねる、という役割分担。

```
┌─────────────────────────────────────────────┐
│  WebScreen (Flutter)                        │
│   ├─ WebView … iku-navi.net/navi/           │
│   ├─ LocationService … GPSで屋内/屋外を判定 │
│   └─ 屋外のとき [ARで見る] ボタン           │
│                    │                        │
│                    ▼ 屋外 + タップ          │
│  ArScreen (Flutter)                         │
│   └─ GeoArBridge → ネイティブGeo-AR         │
│        ├─ Android: ARCore Geospatial API    │
│        └─ iOS:     ARKit ARGeoTracking      │
└─────────────────────────────────────────────┘
```

AR に出すノード／エッジは Web と同じ `GET /api/graph` から取得し、
`building == 0`（屋外）かつ `lat/lng` を持つノードと、その両端を結ぶ
エッジだけを使う。

---

## 構成

| パス | 役割 |
|------|------|
| `lib/main.dart` | アプリ起点 |
| `lib/config.dart` | URL・APIキー・屋内外しきい値 |
| `lib/models/graph.dart` | `/api/graph` のパース（屋外ノード/エッジ抽出） |
| `lib/services/graph_api.dart` | グラフ取得（キャッシュ付き） |
| `lib/services/location_service.dart` | GPS監視＋屋内外判定 |
| `lib/ar/geo_ar_bridge.dart` | ネイティブARとのチャネル定義 |
| `lib/screens/web_screen.dart` | メイン（WebView + 屋外バッジ + ARボタン） |
| `lib/screens/ar_screen.dart` | AR画面（PlatformView + HUD） |
| `native_snippets/` | Android/iOS のネイティブ実装の雛形 |

`android/` `ios/` フォルダはこのリポジトリには含めない（`flutter create` で生成）。

---

## セットアップ手順

### 1. プラットフォームフォルダを生成

このディレクトリで:

```bash
cd programs/AR_APP
flutter create --org net.iku-navi --project-name iku_navi_ar --platforms=android,ios .
flutter pub get
```

`lib/` `pubspec.yaml` は既存のものが使われ、`android/` `ios/` だけが生成される。

### 2. 権限の追加

`native_snippets/android/AndroidManifest_additions.xml` と
`native_snippets/ios/Info_plist_additions.txt` の内容を、生成された
`android/app/src/main/AndroidManifest.xml` / `ios/Runner/Info.plist` に反映する。

- カメラ（AR）
- 位置情報（屋内外判定 + Geospatial測位）
- Android: ARCore を必須機能として宣言

### 3. ARCore Geospatial APIキー（Android）

1. Google Cloud Console で **ARCore API** を有効化
2. APIキーを発行（Androidアプリ制限を推奨）
3. 実行時に渡す:

```bash
flutter run --dart-define=ARCORE_API_KEY=AIza...
```

キーが空のときは AR 画面は「APIキー未設定」と表示してフォールバックする。

### 4. iOS（ARKit Geo-tracking）

- Xcode で最低デプロイ先 iOS 14+（Geo-tracking は対応都市のみ）
- `ARGeoTrackingConfiguration.isSupported` で対応端末/地域を確認
- 署名・カメラ/位置の Usage Description を設定

### 5. ネイティブARの実装

`native_snippets/android/GeoArPlugin.kt` と
`native_snippets/ios/GeoArPlugin.swift` が、Flutterと繋ぐ
**MethodChannel / EventChannel / PlatformView** の雛形。
ここに ARCore Geospatial / ARKit のセッションとアンカー描画を実装する。
チャネル名は `lib/ar/geo_ar_bridge.dart` と一致させること。

---

## Flutter ↔ ネイティブの取り決め（GeoArBridge）

- MethodChannel `iku_navi/geo_ar`
  - `isSupported() -> bool` … ARCore対応＋VPS/Geo利用可否
  - `startSession({apiKey, nodes[], edges[]})` … セッション開始＋アンカー設置
  - `stopSession()`
- EventChannel `iku_navi/geo_ar/events`
  - `{state, accuracyHorizontal, accuracyHeading, message}` を流す
  - `state`: `localizing` / `tracking` / `unavailable` / `error`
- PlatformView `iku_navi/geo_ar_view` … ARカメラ描画面

ノードは `lat/lng` のみ渡し、高度はネイティブの **Terrain Anchor**
（地表高を自動解決）で配置する想定。エッジはノード間に線を引く。

---

## 屋内外判定（LocationService）

- 水平精度が `outdoorAccuracyThresholdM`(20m) 以下 → 屋外候補
- 屋外候補が `outdoorStableCount`(3) 回連続 → 屋外確定（チラつき防止）
- 精度が大きく劣化 → 屋内に戻す

しきい値は `lib/config.dart` で調整。GPSは掴み始めの精度が悪いので、
連続良好フィックスで確定させている。

---

## 現状と残作業

- [x] WebView 表示、GPS監視、屋内外判定、ARデータ取得、AR画面の枠とHUD
- [x] Flutter↔ネイティブのチャネル定義とフォールバック
- [ ] **ネイティブの Geospatial AR 本体**（`native_snippets/` を各プロジェクトへ実装）
  - ARCore Geospatial: `Earth` の取得 → `createAnchor`/`createTerrainAnchor` → 描画
  - ARKit: `ARGeoTrackingConfiguration` → `ARGeoAnchor` → 描画
- [ ] ノード間の線（エッジ）の3D描画
- [ ] 到着判定・経路ハイライト等のナビ連携

Web版AR（`programs/html/navi/ar-outdoor.html`）は方位精度の限界があったため、
本アプリではGPS+VPSで世界座標に正確に合わせる Geospatial 方式へ移行する位置づけ。
