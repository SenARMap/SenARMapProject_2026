// ARKit (ARGeoTrackingConfiguration) を Flutter に繋ぐネイティブ実装の雛形。
//
// native_snippets 内の参考実装。`flutter create` 後に ios/Runner/ へ配置し、
// AppDelegate から GeoArPlugin.register(with:) を呼ぶ。
//
// チャネル名は lib/ar/geo_ar_bridge.dart と一致させること。

import Foundation
import Flutter
import ARKit

public class GeoArPlugin: NSObject, FlutterPlugin, FlutterStreamHandler {

    private var eventSink: FlutterEventSink?
    // TODO: ARView / ARSession を保持

    public static func register(with registrar: FlutterPluginRegistrar) {
        let instance = GeoArPlugin()

        let method = FlutterMethodChannel(
            name: "iku_navi/geo_ar", binaryMessenger: registrar.messenger())
        registrar.addMethodCallDelegate(instance, channel: method)

        let events = FlutterEventChannel(
            name: "iku_navi/geo_ar/events", binaryMessenger: registrar.messenger())
        events.setStreamHandler(instance)

        registrar.register(
            GeoArViewFactory(messenger: registrar.messenger()),
            withId: "iku_navi/geo_ar_view")
    }

    public func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        switch call.method {
        case "isSupported":
            // 対応端末・対応都市かを確認
            ARGeoTrackingConfiguration.checkAvailability { available, _ in
                result(available)
            }
        case "startSession":
            // let args = call.arguments as? [String: Any]
            // let nodes = args?["nodes"] as? [[String: Any]] ?? []
            // let edges = args?["edges"] as? [[String: Any]] ?? []
            // TODO:
            //  1. ARGeoTrackingConfiguration でセッション開始
            //  2. geoTrackingStatus.state == .localized を待つ
            //  3. 各ノードを ARGeoAnchor(coordinate:) で設置（高度は省略で地表）
            //  4. edges はノード間に線ジオメトリを描画
            //  5. session(_:didChange:) で測位状態を sendStatus() で通知
            result(nil)
        case "stopSession":
            // TODO: session.pause()
            result(nil)
        default:
            result(FlutterMethodNotImplemented)
        }
    }

    private func sendStatus(state: String,
                            accuracyHorizontal: Double? = nil,
                            accuracyHeading: Double? = nil,
                            message: String? = nil) {
        eventSink?([
            "state": state,
            "accuracyHorizontal": accuracyHorizontal as Any,
            "accuracyHeading": accuracyHeading as Any,
            "message": message as Any,
        ])
    }

    public func onListen(withArguments _: Any?,
                         eventSink events: @escaping FlutterEventSink) -> FlutterError? {
        eventSink = events
        return nil
    }

    public func onCancel(withArguments _: Any?) -> FlutterError? {
        eventSink = nil
        return nil
    }
}

// ARカメラ描画面（PlatformView）。
class GeoArViewFactory: NSObject, FlutterPlatformViewFactory {
    private let messenger: FlutterBinaryMessenger
    init(messenger: FlutterBinaryMessenger) { self.messenger = messenger }

    func create(withFrame frame: CGRect, viewIdentifier viewId: Int64,
                arguments _: Any?) -> FlutterPlatformView {
        return GeoArView(frame: frame)
    }

    func createArgsCodec() -> FlutterMessageCodec & NSObjectProtocol {
        return FlutterStandardMessageCodec.sharedInstance()
    }
}

class GeoArView: NSObject, FlutterPlatformView {
    private let _view: UIView
    init(frame: CGRect) {
        // TODO: ARSCNView / ARView を生成して ARGeoAnchor を描画
        _view = UIView(frame: frame)
        super.init()
    }
    func view() -> UIView { _view }
}
