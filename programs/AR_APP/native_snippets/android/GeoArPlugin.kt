package net.iku_navi.iku_navi_ar

/**
 * ARCore Geospatial API を Flutter に繋ぐネイティブ実装の雛形。
 *
 * このファイルは native_snippets 内の参考実装。`flutter create` 後に
 * android/app/src/main/kotlin/.../ へ配置し、MainActivity から登録する。
 *
 * 依存（android/app/build.gradle）:
 *   implementation 'com.google.ar:core:1.42.0'
 *   // 描画は Sceneform 後継 or 自前OpenGL。ここではチャネル配線のみ示す。
 *
 * チャネル名は lib/ar/geo_ar_bridge.dart と一致させること。
 */

import android.content.Context
import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.StandardMessageCodec
import io.flutter.plugin.platform.PlatformView
import io.flutter.plugin.platform.PlatformViewFactory

class GeoArPlugin : FlutterPlugin, MethodChannel.MethodCallHandler,
    EventChannel.StreamHandler {

    private lateinit var method: MethodChannel
    private lateinit var events: EventChannel
    private var eventSink: EventChannel.EventSink? = null

    // TODO: ARCore Session / Earth を保持する
    // private var session: com.google.ar.core.Session? = null

    override fun onAttachedToEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        method = MethodChannel(binding.binaryMessenger, "iku_navi/geo_ar")
        method.setMethodCallHandler(this)

        events = EventChannel(binding.binaryMessenger, "iku_navi/geo_ar/events")
        events.setStreamHandler(this)

        binding.platformViewRegistry.registerViewFactory(
            "iku_navi/geo_ar_view",
            GeoArViewFactory(),
        )
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "isSupported" -> {
                // TODO: ArCoreApk.getInstance().checkAvailability(...) と
                //       Earth の Geospatial 対応状況を確認して返す
                result.success(false)
            }
            "startSession" -> {
                val apiKey = call.argument<String>("apiKey")
                val nodes = call.argument<List<Map<String, Any>>>("nodes") ?: emptyList()
                val edges = call.argument<List<Map<String, Any>>>("edges") ?: emptyList()
                // TODO:
                //  1. Session を Config.GeospatialMode.ENABLED で構成
                //  2. APIキーを設定（Cloud Anchors/Geospatial の認証）
                //  3. earth.trackingState == TRACKING を待つ
                //  4. 各ノードを earth.resolveAnchorOnTerrainAsync(lat, lng, ...) で設置
                //  5. edges はノード間に線（OpenGL/フィルメント）を描画
                //  6. 測位状態を sendStatus() で随時通知
                result.success(null)
            }
            "stopSession" -> {
                // TODO: session?.close()
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    /** ネイティブ → Flutter へ測位状態を流す */
    private fun sendStatus(
        state: String,
        accuracyHorizontal: Double? = null,
        accuracyHeading: Double? = null,
        message: String? = null,
    ) {
        eventSink?.success(
            mapOf(
                "state" to state,
                "accuracyHorizontal" to accuracyHorizontal,
                "accuracyHeading" to accuracyHeading,
                "message" to message,
            ),
        )
    }

    override fun onListen(arguments: Any?, sink: EventChannel.EventSink?) {
        eventSink = sink
    }

    override fun onCancel(arguments: Any?) {
        eventSink = null
    }

    override fun onDetachedFromEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        method.setMethodCallHandler(null)
        events.setStreamHandler(null)
    }
}

/** ARカメラ描画面（PlatformView）の生成ファクトリ。 */
class GeoArViewFactory : PlatformViewFactory(StandardMessageCodec.INSTANCE) {
    override fun create(context: Context, viewId: Int, args: Any?): PlatformView {
        return GeoArView(context)
    }
}

class GeoArView(context: Context) : PlatformView {
    // TODO: GLSurfaceView 等で ARCore のカメラ＋アンカーを描画する
    private val view = android.view.View(context)

    override fun getView(): android.view.View = view
    override fun dispose() {}
}
