// ================================================================
// AR Outdoor Integration
// Three.js + カメラ + ジャイロ を #ar-area 内で動かす。
// 屋外ステップ到達時に arShowView()、屋内に戻ったら arHideView() を呼ぶ。
// ================================================================
const AR_THREE_CDN  = "https://cdn.jsdelivr.net/npm/three@0.137.0/build/three.min.js";
const AR_EYE_HEIGHT = 1.6;
const AR_NODE_R     = 0.5;
const AR_EDGE_R     = 0.12;
const AR_NODE_COLOR = 0x22D3EE;
const AR_EDGE_COLOR = 0x3B82F6;
const AR_CAMERA_FOV = 65;
const AR_TILT_DEG   = 5;

let arPermissionsRequested = false;
let arCamWanted      = false;  // カメラストリームを保持してよいか（解放後の遅延取得を防ぐ）
let arCamRequesting  = false;  // getUserMedia 実行中フラグ（二重取得を防ぐ）
let arOrientAttached = false;
let arHaveAbsolute   = false;
let arGOrient        = null;

let arStream       = null;
let arRenderer     = null;
let arScene3       = null;
let arCamera3      = null;
let arWorldGroup   = null;
let arRefLat       = null;
let arRefLng       = null;
let arUserLat      = null;
let arUserLng      = null;
let arGpsWatchId   = null;
let arRunning      = false;
let arBooting      = false;
let arMarkersBuilt = false;

let _arMeshes = [];   // { mesh, type: "node"|"edge", idx } — per-step color update

let _arZee, _arEuler, _arQ0, _arQ1;

function arLoadThree() {
  return new Promise((resolve, reject) => {
    if (typeof THREE !== "undefined") { resolve(); return; }
    const s = document.createElement("script");
    s.src = AR_THREE_CDN;
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

function arAttachOrientation() {
  if (arOrientAttached) return;
  arOrientAttached = true;
  const onAbsolute = (e) => {
    if (e.alpha == null) return;
    arHaveAbsolute = true;
    arGOrient = e;
  };
  const onRelative = (e) => {
    if (arHaveAbsolute && typeof e.webkitCompassHeading !== "number") return;
    arGOrient = e;
  };
  window.addEventListener("deviceorientationabsolute", onAbsolute);
  window.addEventListener("deviceorientation",         onRelative);
}

// 検索ボタン押下（ユーザー操作コンテキスト）で呼ぶ。
// iOS の DeviceOrientationEvent.requestPermission は同期的に
// ユーザー操作内で呼ばないと許可ダイアログが出ないため、ここで先取りする。
// カメラはこの時点では取得しない（ルート確定後、屋外AR区間がある場合のみ
// arPrefetchCameraIfNeeded() で取得する）。
function arRequestPermissionsEarly() {
  if (arPermissionsRequested) return;
  arPermissionsRequested = true;

  // Three.js を並行ロード（画面切り替え時のもたつきを減らす）
  arLoadThree().catch(() => {});

  // iOS 向け向きセンサー許可（ユーザー操作コンテキスト内で同期呼び出し必須）
  if (typeof DeviceOrientationEvent !== "undefined" &&
      typeof DeviceOrientationEvent.requestPermission === "function") {
    DeviceOrientationEvent.requestPermission()
      .then(state => { if (state === "granted") arAttachOrientation(); })
      .catch(() => {});
  } else {
    arAttachOrientation();
  }
}

// ルートに屋外AR区間が含まれる場合のみカメラを先取りしてストリームを温める。
// 屋内のみのルートではカメラを一切起動しない。initRoute() から呼ばれる。
function arPrefetchCameraIfNeeded() {
  let hasOutdoorAR = false;
  for (let i = 0; i < pathCoords.length - 1; i++) {  // 最終ステップは到着画面なのでAR不要
    const n = pathCoords[i];
    if (n && n.building === 0 && n.lat != null) { hasOutdoorAR = true; break; }
  }
  if (!hasOutdoorAR) return;

  arCamWanted = true;
  if (arStream || arCamRequesting) return;
  if (!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)) return;
  arCamRequesting = true;
  navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
    .then(stream => {
      arCamRequesting = false;
      // 取得完了前に解放済みならすぐ止める
      if (!arCamWanted) { stream.getTracks().forEach(t => t.stop()); return; }
      arStream = stream;
    })
    .catch(() => { arCamRequesting = false; });
}

function arEnsureRenderer() {
  if (arRenderer || typeof THREE === "undefined") return;

  const canvas = document.getElementById("ar-gl-canvas");
  arRenderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  arRenderer.setClearColor(0x000000, 0);

  arScene3 = new THREE.Scene();
  arCamera3 = new THREE.PerspectiveCamera(AR_CAMERA_FOV, 1, 0.1, 5000);
  arCamera3.position.set(0, AR_EYE_HEIGHT, 0);

  arWorldGroup = new THREE.Group();
  arScene3.add(arWorldGroup);
  arScene3.add(new THREE.AmbientLight(0xffffff, 1.0));

  _arZee  = new THREE.Vector3(0, 0, 1);
  _arEuler = new THREE.Euler();
  _arQ0   = new THREE.Quaternion();
  _arQ1   = new THREE.Quaternion(-Math.sqrt(0.5), 0, 0, Math.sqrt(0.5));

  window.addEventListener("resize",            arResizeCanvas);
  window.addEventListener("orientationchange", () => setTimeout(arResizeCanvas, 300));
  arResizeCanvas();
}

function arResizeCanvas() {
  if (!arRenderer || !arCamera3) return;
  const area = document.getElementById("ar-area");
  if (!area) return;
  const w = area.clientWidth, h = area.clientHeight;
  if (!w || !h) return;
  arRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  arRenderer.setSize(w, h, false);
  arCamera3.aspect = w / h;
  arCamera3.updateProjectionMatrix();
}

function arEnuFromRef(lat, lng) {
  const north = (lat - arRefLat) * 111320;
  const east  = (lng - arRefLng) * 111320 * Math.cos(arRefLat * Math.PI / 180);
  return { east, north };
}

function arUpdateWorldPosition(lat, lng) {
  if (arRefLat == null || !arWorldGroup) return;
  const { east, north } = arEnuFromRef(lat, lng);
  arWorldGroup.position.set(-east, 0, north);
}

// pathCoords から屋外区間のノード・エッジを Three.js シーンに配置する
function arBuildRouteMarkers() {
  if (!arWorldGroup || typeof THREE === "undefined") return;
  while (arWorldGroup.children.length) arWorldGroup.remove(arWorldGroup.children[0]);
  _arMeshes = [];

  const outdoorNodes = pathCoords.filter(
    n => n.building === 0 && n.lat != null && n.lng != null
  );
  if (!outdoorNodes.length) return;

  arRefLat = outdoorNodes[0].lat;
  arRefLng = outdoorNodes[0].lng;

  const pos       = {};
  const sphereGeo = new THREE.SphereGeometry(AR_NODE_R, 24, 16);

  outdoorNodes.forEach((n, localIdx) => {
    const globalIdx = pathCoords.indexOf(n);
    const { east, north } = arEnuFromRef(n.lat, n.lng);
    const x = east, z = -north;
    pos[n.id] = { x, z };
    const mat    = new THREE.MeshBasicMaterial({ color: AR_NODE_COLOR });
    const sphere = new THREE.Mesh(sphereGeo, mat);
    sphere.position.set(x, 0, z);
    arWorldGroup.add(sphere);
    _arMeshes.push({ mesh: sphere, mat, type: "node", idx: globalIdx });
  });

  const up = new THREE.Vector3(0, 1, 0);
  for (let i = 0; i < pathCoords.length - 1; i++) {
    const a = pathCoords[i], b = pathCoords[i + 1];
    if (a.building !== 0 || b.building !== 0 || a.lat == null || b.lat == null) continue;
    const pa = pos[a.id], pb = pos[b.id];
    if (!pa || !pb) continue;
    const dx = pb.x - pa.x, dz = pb.z - pa.z;
    const len = Math.hypot(dx, dz);
    if (len < 0.01) continue;
    const geo = new THREE.CylinderGeometry(AR_EDGE_R, AR_EDGE_R, len, 12);
    const mat = new THREE.MeshBasicMaterial({
      color: AR_EDGE_COLOR, transparent: true, opacity: 0.85
    });
    const cyl = new THREE.Mesh(geo, mat);
    cyl.position.set(pa.x + dx / 2, 0, pa.z + dz / 2);
    cyl.quaternion.setFromUnitVectors(up, new THREE.Vector3(dx, 0, dz).normalize());
    arWorldGroup.add(cyl);
    _arMeshes.push({ mesh: cyl, mat, type: "edge", idx: i });
  }

  if (arUserLat != null) arUpdateWorldPosition(arUserLat, arUserLng);
  arMarkersBuilt = true;
}

// 現在ステップに合わせてノード・エッジを通過済み(グレー) / これから(青) に塗り替える
function arUpdateRouteColors(step) {
  const PASSED_NODE = 0x9E9E9E;
  const AHEAD_NODE  = AR_NODE_COLOR;     // 0x22D3EE
  const PASSED_EDGE = 0x9E9E9E;
  const AHEAD_EDGE  = AR_EDGE_COLOR;     // 0x3B82F6
  const PASSED_OPACITY = 0.35;
  const AHEAD_OPACITY  = 0.85;

  _arMeshes.forEach(({ mat, type, idx }) => {
    const passed = idx < step;
    if (type === "node") {
      mat.color.setHex(passed ? PASSED_NODE : AHEAD_NODE);
    } else {
      mat.color.setHex(passed ? PASSED_EDGE : AHEAD_EDGE);
      mat.opacity = passed ? PASSED_OPACITY : AHEAD_OPACITY;
    }
  });
}

function arScreenAngle() {
  const a = screen.orientation && screen.orientation.angle;
  return ((a != null ? a : window.orientation) || 0) * Math.PI / 180;
}

function arUpdateCameraOrientation() {
  const e = arGOrient;
  if (!e || !arCamera3) return;

  let headingDeg;
  if (typeof e.webkitCompassHeading === "number") {
    headingDeg = 360 - e.webkitCompassHeading;
  } else {
    headingDeg = e.alpha || 0;
  }

  const alpha  = headingDeg * Math.PI / 180;
  const beta   = ((e.beta  || 0) + AR_TILT_DEG) * Math.PI / 180;
  const gamma  = (e.gamma  || 0) * Math.PI / 180;
  const orient = arScreenAngle();

  _arEuler.set(beta, alpha, -gamma, "YXZ");
  const q = arCamera3.quaternion;
  q.setFromEuler(_arEuler);
  q.multiply(_arQ1);
  q.multiply(_arQ0.setFromAxisAngle(_arZee, -orient));
}

function arAnimate() {
  if (!arRunning) return;
  requestAnimationFrame(arAnimate);
  arUpdateCameraOrientation();
  arRenderer.render(arScene3, arCamera3);
}

async function arShowView() {
  if (arRunning || arBooting) return;
  arCamWanted = true;
  arBooting = true;

  try {
    await arLoadThree();
  } catch {
    arBooting = false;
    return;
  }
  if (!arBooting) return;

  arEnsureRenderer();

  const video = document.getElementById("ar-bg-video");
  if (!video.srcObject) {
    if (arStream) {
      video.srcObject = arStream;
    } else {
      try {
        const s = await navigator.mediaDevices.getUserMedia(
          { video: { facingMode: "environment" } }
        );
        if (!arBooting) { s.getTracks().forEach(t => t.stop()); return; }
        arStream = s;
        video.srcObject = s;
      } catch { /* カメラ利用不可 */ }
    }
  }
  if (!arBooting) return;

  // AR用GPS継続追跡（初回のみ開始）
  if (!arGpsWatchId && navigator.geolocation) {
    arGpsWatchId = navigator.geolocation.watchPosition(
      pos => {
        arUserLat = pos.coords.latitude;
        arUserLng = pos.coords.longitude;
        arUpdateWorldPosition(arUserLat, arUserLng);
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 0, timeout: 27000 }
    );
  }

  document.getElementById("ar-bg-video").style.display = "block";
  document.getElementById("ar-gl-canvas").style.display = "block";

  if (!arMarkersBuilt) arBuildRouteMarkers();
  arResizeCanvas();

  arRunning = true;
  arBooting = false;
  arAnimate();
}

function arHideView() {
  arBooting = false;
  if (!arRunning) return;
  arRunning = false;
  document.getElementById("ar-bg-video").style.display = "none";
  document.getElementById("ar-gl-canvas").style.display = "none";
}

// カメラストリームと GPS 監視を完全に停止する。
// 再度屋外区間に入れば arShowView() が取得し直す（許可ダイアログは再表示されない）。
function arReleaseHardware() {
  arCamWanted = false;
  arHideView();
  if (arStream) {
    arStream.getTracks().forEach(t => t.stop());
    arStream = null;
  }
  const video = document.getElementById("ar-bg-video");
  if (video.srcObject) video.srcObject = null;
  if (arGpsWatchId != null && navigator.geolocation) {
    navigator.geolocation.clearWatch(arGpsWatchId);
    arGpsWatchId = null;
  }
}
